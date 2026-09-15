# tests/test_vectorstore.py
#
# Diferente de test_embeddings.py, aqui NÃO usamos um adaptador falso —
# o LanceDB é embarcado (sem servidor, sem rede), então testamos contra a
# biblioteca de verdade, guardando os dados num tmp_path descartável, do
# mesmo jeito que tests/test_documents.py testa contra arquivos reais.
# Consequência prática: estes testes só rodam de fato numa máquina com o
# pacote `lancedb` instalado (ver knowledge/vector-search/dependencias.md)
# — no ambiente onde este arquivo foi gerado, `lancedb` não estava
# disponível (mesma limitação de PyPI bloqueado já registrada em
# projects/moto-mcp-framework-server.md), então isso foi revisado
# manualmente, não executado.

import pytest

from mcp_server.vectorstore import LanceDBVectorStore, VectorStore

# Vetores pequenos (3 dimensões) só pra teste — dimensão real de verdade
# (1024, do bge-m3) não importa pra validar a lógica do adaptador.
DIMENSIONS = 3


@pytest.fixture
def store(tmp_path):
    return LanceDBVectorStore(db_path=str(tmp_path / "vector_index"), dimensions=DIMENSIONS)


def test_store_satisfies_protocol(store):
    assert isinstance(store, VectorStore)


def test_upsert_then_search_returns_the_chunk(store):
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "conteúdo do chunk 1", {"path": "a.md"})

    results = store.search([1.0, 0.0, 0.0], top_k=5)

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-1"
    assert results[0].text == "conteúdo do chunk 1"
    assert results[0].metadata == {"path": "a.md"}
    # Vetor idêntico à busca -> cosseno = 1 (mesma direção).
    assert results[0].score == pytest.approx(1.0, abs=1e-4)


def test_search_orders_by_similarity_descending(store):
    store.upsert("parecido", [1.0, 0.0, 0.0], "parecido", {})
    store.upsert("perpendicular", [0.0, 1.0, 0.0], "perpendicular", {})
    store.upsert("oposto", [-1.0, 0.0, 0.0], "oposto", {})

    results = store.search([1.0, 0.0, 0.0], top_k=3)

    assert [r.chunk_id for r in results] == ["parecido", "perpendicular", "oposto"]
    assert results[0].score == pytest.approx(1.0, abs=1e-4)
    assert results[1].score == pytest.approx(0.0, abs=1e-4)
    assert results[2].score == pytest.approx(-1.0, abs=1e-4)


def test_upsert_same_id_overwrites_not_duplicates(store):
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "versão antiga", {"v": 1})
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "versão nova", {"v": 2})

    assert store.list_indexed() == {"chunk-1": {"v": 2}}

    results = store.search([1.0, 0.0, 0.0], top_k=10)
    assert len(results) == 1
    assert results[0].text == "versão nova"


def test_delete_removes_the_chunk(store):
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "texto", {})
    store.upsert("chunk-2", [0.0, 1.0, 0.0], "outro texto", {})

    store.delete("chunk-1")

    assert store.list_indexed() == {"chunk-2": {}}


def test_delete_id_with_single_quote_does_not_break(store):
    chunk_id = "projects/o'brien.md#Papel"
    store.upsert(chunk_id, [1.0, 0.0, 0.0], "texto", {})

    store.delete(chunk_id)

    assert store.list_indexed() == {}


def test_list_indexed_empty_store_returns_empty_dict(store):
    assert store.list_indexed() == {}


def test_reopening_existing_table_preserves_data(tmp_path):
    db_path = str(tmp_path / "vector_index")

    first = LanceDBVectorStore(db_path=db_path, dimensions=DIMENSIONS)
    first.upsert("chunk-1", [1.0, 0.0, 0.0], "texto", {"v": 1})

    reopened = LanceDBVectorStore(db_path=db_path, dimensions=DIMENSIONS)

    assert reopened.list_indexed() == {"chunk-1": {"v": 1}}


def test_compact_default_does_not_lose_data(store):
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "texto", {"v": 1})
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "texto atualizado", {"v": 2})  # gera uma versão extra pra compactar

    store.compact()

    assert store.list_indexed() == {"chunk-1": {"v": 2}}
    results = store.search([1.0, 0.0, 0.0], top_k=5)
    assert len(results) == 1
    assert results[0].text == "texto atualizado"


def test_compact_with_explicit_retention_does_not_lose_data(store):
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "texto", {"v": 1})
    store.delete("chunk-1")
    store.upsert("chunk-2", [0.0, 1.0, 0.0], "outro", {"v": 1})

    # older_than_days=0 força limpar o histórico imediatamente, não só o
    # que tem mais de 7 dias (padrão) — é o caso de "manda executar agora".
    store.compact(older_than_days=0)

    assert store.list_indexed() == {"chunk-2": {"v": 1}}
