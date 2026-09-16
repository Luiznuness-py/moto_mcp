# tests/test_search_tools.py
#
# Testa a lógica das tools de busca vetorial (search_semantic,
# reindex_search, compact_search_index) SEM tocar LanceDB/Ollama de
# verdade — mesmo espírito de tests/test_indexing.py: aqui não é o
# adaptador real que está sob teste (isso já é
# tests/test_vectorstore.py e tests/test_embeddings.py), é a lógica
# fina de cada tool (formatar resultado, mapear IndexingReport pra
# dict). Por isso os testes chamam direto as funções `_..._impl()`
# privadas — as tools async públicas (search_semantic etc.) só existem
# pra não vazar parâmetro de injeção de dependência (store/embedder) no
# schema exposto ao cliente MCP, então não têm lógica própria pra
# testar além de "constroem o backend real e delegam".

from __future__ import annotations

from mcp_server.indexing import IndexingReport
from mcp_server.tools import _compact_impl, _report_to_dict, _search_semantic_impl
from mcp_server.vectorstore import SearchResult


class _FakeEmbeddingProvider:
    def __init__(self):
        self.calls: list[str] = []

    def embed(self, text):
        self.calls.append(text)
        return [float(len(text))]

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


class _FakeVectorStore:
    def __init__(self, results: list[SearchResult] | None = None):
        self._results = results or []
        self.search_calls: list[tuple[list[float], int]] = []
        self.compact_calls: list[int | None] = []

    def upsert(self, chunk_id, vector, text, metadata):
        raise NotImplementedError("não usado nestes testes")

    def delete(self, chunk_id):
        raise NotImplementedError("não usado nestes testes")

    def search(self, query_vector, top_k=5):
        self.search_calls.append((query_vector, top_k))
        return self._results[:top_k]

    def list_indexed(self):
        raise NotImplementedError("não usado nestes testes")

    def compact(self, *, older_than_days=None):
        self.compact_calls.append(older_than_days)


def test_search_semantic_impl_formats_results_flattened():
    results = [
        SearchResult(
            chunk_id="agents/bill.md#Identidade e papel",
            text="Meu nome é Bill.",
            metadata={"path": "agents/bill.md", "section": "Identidade e papel", "category": "agents"},
            score=0.83,
        )
    ]
    store = _FakeVectorStore(results)
    embedder = _FakeEmbeddingProvider()

    out = _search_semantic_impl(store, embedder, "quem é o Bill", top_k=5)

    assert out == [
        {
            "chunk_id": "agents/bill.md#Identidade e papel",
            "score": 0.83,
            "path": "agents/bill.md",
            "section": "Identidade e papel",
            "category": "agents",
            "text": "Meu nome é Bill.",
        }
    ]


def test_search_semantic_impl_embeds_the_query_and_passes_top_k():
    store = _FakeVectorStore([])
    embedder = _FakeEmbeddingProvider()

    _search_semantic_impl(store, embedder, "pergunta qualquer", top_k=3)

    assert embedder.calls == ["pergunta qualquer"]
    assert store.search_calls == [([len("pergunta qualquer") * 1.0], 3)]


def test_search_semantic_impl_empty_index_returns_empty_list_not_error():
    store = _FakeVectorStore([])
    embedder = _FakeEmbeddingProvider()

    assert _search_semantic_impl(store, embedder, "qualquer coisa", top_k=5) == []


def test_report_to_dict_maps_all_fields():
    report = IndexingReport(upserted=["a.md#x", "b.md#y"], deleted=["c.md#z"], unchanged=10)

    out = _report_to_dict(report)

    assert out == {
        "chunks_atualizados": ["a.md#x", "b.md#y"],
        "chunks_removidos": ["c.md#z"],
        "chunks_sem_mudanca": 10,
        "total_no_indice": 12,  # len(upserted) + unchanged, ver IndexingReport.total_current
    }


def test_report_to_dict_empty_report():
    out = _report_to_dict(IndexingReport())

    assert out == {
        "chunks_atualizados": [],
        "chunks_removidos": [],
        "chunks_sem_mudanca": 0,
        "total_no_indice": 0,
    }


def test_compact_impl_delegates_older_than_days_and_confirms():
    store = _FakeVectorStore()

    out = _compact_impl(store, 30)

    assert store.compact_calls == [30]
    assert out == {"status": "ok", "older_than_days": 30}


def test_compact_impl_default_none_uses_lancedb_default():
    store = _FakeVectorStore()

    out = _compact_impl(store, None)

    assert store.compact_calls == [None]
    assert out == {"status": "ok", "older_than_days": None}
