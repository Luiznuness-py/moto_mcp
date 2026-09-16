#!/usr/bin/env python
# scripts/reindex.py
#
# Ponto de entrada de linha de comando pra (re)indexação do repositório
# no banco vetorial. Uso (da raiz do repositório, ou de qualquer lugar):
#
#   poetry run python scripts/reindex.py
#
# Idempotente por natureza (ver mcp_server/indexing.py): rodar de novo
# sem nada ter mudado não reprocessa nenhum chunk, só confirma que
# content_hash bate. Precisa do Ollama rodando localmente (modelo
# `bge-m3` já baixado — `ollama pull bge-m3`) e do pacote `lancedb`
# instalado (ver knowledge/vector-search/dependencias.md).
#
# mcp_server é instalado no venv em modo editable (ver [tool.poetry]
# packages em pyproject.toml) — por isso `from mcp_server import ...`
# funciona rodando este script de qualquer jeito (`poetry run python
# scripts/reindex.py`, de qualquer diretório), sem ajuste de sys.path.

from __future__ import annotations

from mcp_server.embeddings import OllamaEmbeddingProvider
from mcp_server.indexing import reindex
from mcp_server.vectorstore import LanceDBVectorStore


def main() -> None:
    store = LanceDBVectorStore()
    embedder = OllamaEmbeddingProvider()

    report = reindex(store, embedder)

    print(f"Chunks novos/atualizados: {len(report.upserted)}")
    for chunk_id in report.upserted:
        print(f"  + {chunk_id}")

    print(f"Chunks removidos: {len(report.deleted)}")
    for chunk_id in report.deleted:
        print(f"  - {chunk_id}")

    print(f"Chunks sem mudança (pulados, sem chamar o Ollama): {report.unchanged}")
    print(f"Total no índice agora: {report.total_current}")


if __name__ == "__main__":
    main()
