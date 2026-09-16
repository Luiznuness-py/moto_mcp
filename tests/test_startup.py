# tests/test_startup.py
#
# reindex_on_startup() nunca deve propagar exceção — falha de
# embedding/vectorstore vira aviso, o servidor tem que subir mesmo
# assim (ver mcp_server/startup.py). Fakes no mesmo espírito de
# tests/test_indexing.py.

from __future__ import annotations

import pytest

from mcp_server.errors import EmbeddingProviderError, VectorStoreError
from mcp_server.startup import reindex_on_startup


class _FakeEmbeddingProvider:
    def embed(self, text):
        return self.embed_batch([text])[0]

    def embed_batch(self, texts):
        return [[float(len(text))] for text in texts]


class _FailingEmbeddingProvider:
    def embed(self, text):
        raise EmbeddingProviderError("Ollama fora do ar (fake)")

    def embed_batch(self, texts):
        raise EmbeddingProviderError("Ollama fora do ar (fake)")


class _FakeVectorStore:
    def __init__(self):
        self._rows: dict[str, dict] = {}

    def upsert(self, chunk_id, vector, text, metadata):
        self._rows[chunk_id] = metadata

    def delete(self, chunk_id):
        self._rows.pop(chunk_id, None)

    def search(self, query_vector, top_k=5):
        return []

    def list_indexed(self):
        return dict(self._rows)

    def compact(self, *, older_than_days=None):
        pass


class _FailingVectorStore(_FakeVectorStore):
    def upsert(self, chunk_id, vector, text, metadata):
        raise VectorStoreError("LanceDB indisponível (fake)")


class TestReindexOnStartup:
    def test_succeeds_with_working_store_and_embedder(self, fake_repo, capsys):
        reindex_on_startup(store=_FakeVectorStore(), embedder=_FakeEmbeddingProvider())
        out = capsys.readouterr().out
        assert "[moto_mcp]" in out
        assert "Aviso" not in out

    def test_embedding_failure_does_not_raise(self, fake_repo, capsys):
        reindex_on_startup(store=_FakeVectorStore(), embedder=_FailingEmbeddingProvider())
        out = capsys.readouterr().out
        assert "Aviso" in out

    def test_vectorstore_failure_does_not_raise(self, fake_repo, capsys):
        reindex_on_startup(store=_FailingVectorStore(), embedder=_FakeEmbeddingProvider())
        out = capsys.readouterr().out
        assert "Aviso" in out

    def test_no_unexpected_exception_propagates(self, fake_repo):
        # Garantia central deste módulo: independente do que falhar
        # (embedding ou vectorstore), reindex_on_startup nunca deve
        # deixar uma exceção escapar — é isso que garante que o
        # servidor sempre sobe.
        try:
            reindex_on_startup(store=_FailingVectorStore(), embedder=_FailingEmbeddingProvider())
        except (EmbeddingProviderError, VectorStoreError):
            pytest.fail("reindex_on_startup não deveria propagar exceção")
