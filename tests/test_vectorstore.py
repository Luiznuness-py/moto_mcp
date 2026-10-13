# Testes contra SQLite real em diretórios temporários.

import pytest

from mcp_server.vectorstore import SQLiteVectorStore, VectorStore

# Vetores pequenos (3 dimensões) só pra teste — dimensão real de verdade
# (1024, do bge-m3) não importa pra validar a lógica do adaptador.
DIMENSIONS = 3


@pytest.fixture
def store(tmp_path):
    return SQLiteVectorStore(db_path=str(tmp_path / "vector_index"), dimensions=DIMENSIONS)


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

    first = SQLiteVectorStore(db_path=db_path, dimensions=DIMENSIONS)
    first.upsert("chunk-1", [1.0, 0.0, 0.0], "texto", {"v": 1})

    reopened = SQLiteVectorStore(db_path=db_path, dimensions=DIMENSIONS)

    assert reopened.list_indexed() == {"chunk-1": {"v": 1}}


def test_compact_default_does_not_lose_data(store):
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "texto", {"v": 1})
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "texto atualizado", {"v": 2})  # atualiza o registro antes de compactar

    store.compact()

    assert store.list_indexed() == {"chunk-1": {"v": 2}}
    results = store.search([1.0, 0.0, 0.0], top_k=5)
    assert len(results) == 1
    assert results[0].text == "texto atualizado"


def test_compact_with_explicit_retention_does_not_lose_data(store):
    store.upsert("chunk-1", [1.0, 0.0, 0.0], "texto", {"v": 1})
    store.delete("chunk-1")
    store.upsert("chunk-2", [0.0, 1.0, 0.0], "outro", {"v": 1})

    # SQLite aceita o contrato, mas não mantém histórico por idade.
    store.compact(older_than_days=0)

    assert store.list_indexed() == {"chunk-2": {"v": 1}}


def test_search_is_cosine_not_dot_product(store):
    store.upsert("direction", [2.0, 0.0, 0.0], "direção", {})
    store.upsert("large", [100.0, 100.0, 0.0], "magnitude", {})
    results = store.search([5.0, 0.0, 0.0])
    assert [r.chunk_id for r in results] == ["direction", "large"]
    assert results[1].score == pytest.approx(2 ** -0.5)


@pytest.mark.parametrize("vector", [[1.0], [0.0, 0.0, 0.0], [float('nan'), 1, 0], [float('inf'), 1, 0], [None, 1, 0]])
def test_invalid_vectors_rejected_without_replacing_data(store, vector):
    from mcp_server.errors import VectorStoreError
    store.upsert("original", [1, 0, 0], "original", {})
    with pytest.raises(VectorStoreError):
        store.upsert("original", vector, "inválido", {})
    with pytest.raises(VectorStoreError):
        store.search(vector)
    assert store.search([1, 0, 0])[0].text == "original"


@pytest.mark.parametrize("top_k", [0, -1, 1.5])
def test_invalid_top_k_rejected(store, top_k):
    from mcp_server.errors import VectorStoreError
    with pytest.raises(VectorStoreError):
        store.search([1, 0, 0], top_k=top_k)


def test_limit_and_empty_search(store):
    assert store.search([1, 0, 0]) == []
    for i in range(4):
        store.upsert(str(i), [1, i, 0], str(i), {})
    assert [r.chunk_id for r in store.search([1, 0, 0], top_k=2)] == ["0", "1"]


def test_dimension_mismatch_on_reopen_preserves_index(tmp_path):
    from mcp_server.errors import VectorStoreError
    path = str(tmp_path / 'index')
    original = SQLiteVectorStore(path, dimensions=3)
    original.upsert('a', [1, 0, 0], 'a', {})
    with pytest.raises(VectorStoreError, match='Dimensão'):
        SQLiteVectorStore(path, dimensions=4)
    assert SQLiteVectorStore(path, dimensions=3).list_indexed() == {'a': {}}


def test_real_embedding_dimensions_and_metadata_roundtrip(tmp_path):
    store = SQLiteVectorStore(str(tmp_path), dimensions=1024)
    vector = [1.0] + [0.0] * 1023
    metadata = {'path': 'ação.md', 'nested': {'tags': ['pt-BR', 'segurança']}}
    store.upsert("x'; DROP TABLE chunks; --", vector, 'conteúdo', metadata)
    reopened = SQLiteVectorStore(str(tmp_path), dimensions=1024)
    assert reopened.search(vector)[0].metadata == metadata
    reopened.delete("x'; DROP TABLE chunks; --")
    assert reopened.list_indexed() == {}


def test_concurrent_connections_upsert_without_duplicates(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = str(tmp_path)
    store = SQLiteVectorStore(path, dimensions=3)
    def write(i):
        other = SQLiteVectorStore(path, dimensions=3)
        other.upsert('shared', [1, 0, 0], str(i), {'writer': i})
        other.upsert(str(i), [0, 1, 0], str(i), {})
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(write, range(16)))
    assert len(store.list_indexed()) == 17
    assert len(store.search([1, 0, 0], top_k=30)) == 17


def test_old_lance_index_is_not_deleted(tmp_path):
    legacy = tmp_path / 'chunks.lance'
    legacy.mkdir()
    marker = legacy / 'preserve'
    marker.write_text('old index')
    store = SQLiteVectorStore(str(tmp_path), dimensions=3)
    store.upsert('a', [1, 0, 0], 'a', {})
    store.compact()
    assert marker.read_text() == 'old index'


@pytest.mark.parametrize('name', ['chunks"; DROP TABLE chunks;--', 'vector_store_config'])
def test_invalid_table_name_rejected(tmp_path, name):
    from mcp_server.errors import VectorStoreError
    with pytest.raises(VectorStoreError):
        SQLiteVectorStore(str(tmp_path), table_name=name)


def test_unwritable_database_becomes_vectorstore_error(tmp_path):
    from mcp_server.errors import VectorStoreError
    (tmp_path / 'vectors.sqlite3').mkdir()
    with pytest.raises(VectorStoreError, match='SQLite'):
        SQLiteVectorStore(str(tmp_path), dimensions=3)


def test_1024_dimension_ranking_matches_independent_cosine_reference(tmp_path):
    import math
    import random
    rng = random.Random(42)
    vectors = {str(i): [rng.uniform(-2, 2) for _ in range(1024)] for i in range(25)}
    query = [rng.uniform(-1, 1) for _ in range(1024)]
    reference = {}
    for chunk_id, vector in vectors.items():
        dot = sum(a * b for a, b in zip(query, vector))
        norm = math.sqrt(sum(a * a for a in query) * sum(b * b for b in vector))
        reference[chunk_id] = dot / norm
    store = SQLiteVectorStore(str(tmp_path), dimensions=1024)
    for chunk_id, vector in vectors.items():
        store.upsert(chunk_id, vector, chunk_id, {})
    results = store.search(query, top_k=8)
    expected = sorted(reference, key=reference.get, reverse=True)[:8]
    assert [result.chunk_id for result in results] == expected
    assert [result.score for result in results] == pytest.approx([reference[key] for key in expected], abs=1e-12)


@pytest.mark.parametrize('dimensions', [0, -1, 1.5])
def test_invalid_dimensions_rejected(tmp_path, dimensions):
    from mcp_server.errors import VectorStoreError
    with pytest.raises(VectorStoreError):
        SQLiteVectorStore(str(tmp_path), dimensions=dimensions)


def test_negative_retention_rejected_without_losing_data(store):
    from mcp_server.errors import VectorStoreError
    store.upsert('a', [1, 0, 0], 'a', {})
    with pytest.raises(VectorStoreError):
        store.compact(older_than_days=-1)
    assert store.list_indexed() == {'a': {}}


def test_named_tables_have_separate_records_and_dimensions(tmp_path):
    first = SQLiteVectorStore(str(tmp_path), table_name='first', dimensions=3)
    second = SQLiteVectorStore(str(tmp_path), table_name='second', dimensions=2)
    first.upsert('a', [1, 0, 0], 'a', {})
    second.upsert('b', [1, 0], 'b', {})
    assert first.list_indexed() == {'a': {}}
    assert second.list_indexed() == {'b': {}}


def test_case_variant_cannot_bypass_dimension_guard(tmp_path):
    from mcp_server.errors import VectorStoreError
    store = SQLiteVectorStore(str(tmp_path), table_name='chunks', dimensions=3)
    store.upsert('a', [1, 0, 0], 'a', {})
    with pytest.raises(VectorStoreError, match='Dimensão'):
        SQLiteVectorStore(str(tmp_path), table_name='CHUNKS', dimensions=2)
    assert store.list_indexed() == {'a': {}}


def test_case_variant_of_config_table_is_reserved(tmp_path):
    from mcp_server.errors import VectorStoreError
    with pytest.raises(VectorStoreError, match='Nome de tabela'):
        SQLiteVectorStore(str(tmp_path), table_name='VECTOR_STORE_CONFIG', dimensions=3)
