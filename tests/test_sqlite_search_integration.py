"""Pipeline real de indexação/busca SQLite; embeddings determinísticos sem rede."""
import pytest

from mcp_server.vectorstore import SQLiteVectorStore
from mcp_server import tools


class Embedder:
    def embed(self, text):
        return [1.0, float('presuma' in text), 0.0]

    def embed_batch(self, texts):
        return [self.embed(text) for text in texts]


@pytest.mark.asyncio
async def test_public_semantic_tools_with_real_sqlite(fake_repo, tmp_path, monkeypatch):
    store = SQLiteVectorStore(str(tmp_path / 'index'), dimensions=3)
    embedder = Embedder()
    monkeypatch.setattr(tools, '_vector_store', lambda: store)
    monkeypatch.setattr(tools, '_embedding_provider', lambda: embedder)
    first = await tools.reindex_search()
    assert first['total_no_indice'] > 0
    result = await tools.search_semantic('não presuma', top_k=1)
    assert result[0]['path'] == 'global/rules_absolute.md'
    assert result[0]['score'] == pytest.approx(1.0)
    assert set(result[0]) == {'chunk_id', 'score', 'path', 'section', 'category', 'text'}
    second = await tools.reindex_search()
    assert second['chunks_atualizados'] == []
    (fake_repo / 'global/rules_absolute.md').unlink()
    removed = await tools.reindex_search()
    assert removed['chunks_removidos']
    assert await tools.compact_search_index() == {'status': 'ok', 'older_than_days': None}
    assert all(r['path'] != 'global/rules_absolute.md' for r in await tools.search_semantic('não presuma'))
