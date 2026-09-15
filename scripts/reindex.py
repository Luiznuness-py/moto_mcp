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
# Nota sobre o bloco de sys.path logo abaixo: `pyproject.toml` tem
# `package-mode = false` (proposital — ver comentário em
# mcp_server/config.py sobre o `moto_mcp` não ser pensado como pacote
# instalável). Consequência prática: `mcp_server` nunca é instalado no
# venv do Poetry, então só é importável quando a raiz do repositório
# está no `sys.path` — o que acontece automaticamente com `pytest` (acha
# a raiz sozinho) ou com `python -m algo` rodado JÁ na raiz, mas NÃO
# acontece rodando `python scripts/reindex.py` direto: nesse caso o
# Python bota a pasta do PRÓPRIO script (`scripts/`) no início do
# `sys.path`, não a raiz do repo — por isso `from mcp_server import
# ...` falhava com `ModuleNotFoundError` mesmo estando na pasta certa.
# As duas linhas abaixo resolvem isso de vez, sem depender de como
# nem de onde o script é chamado.

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server.embeddings import OllamaEmbeddingProvider  # noqa: E402
from mcp_server.indexing import reindex  # noqa: E402
from mcp_server.vectorstore import LanceDBVectorStore  # noqa: E402


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
