#!/usr/bin/env python
# scripts/ask.py
#
# Pergunta manual contra o índice vetorial de verdade — pra explorar/
# calibrar a busca na mão, sem precisar abrir um REPL Python (que era
# como isso era testado antes — ver to-do.md). Uso (da raiz do
# repositório, ou de qualquer lugar):
#
#   poetry run python scripts/ask.py "por que a escrita é restrita?"
#
# Sem argumento, entra em modo interativo (pergunta, mostra resultado,
# pergunta de novo — Ctrl+C ou "sair" pra encerrar):
#
#   poetry run python scripts/ask.py
#
# Pré-requisito: já ter rodado `poetry run python scripts/reindex.py`
# pelo menos uma vez. Precisa do Ollama rodando (mesma coisa que
# scripts/reindex.py e scripts/verify_search.py).
#
# mcp_server é instalado no venv em modo editable (ver [tool.poetry]
# packages em pyproject.toml) — nenhum ajuste de sys.path é necessário.

from __future__ import annotations

import sys

from mcp_server.embeddings import OllamaEmbeddingProvider
from mcp_server.vectorstore import LanceDBVectorStore

TOP_K = 5
PREVIEW_CHARS = 160


def ask(store: LanceDBVectorStore, embedder: OllamaEmbeddingProvider, question: str) -> None:
    vector = embedder.embed(question)
    results = store.search(vector, top_k=TOP_K)

    if not results:
        print("(índice vazio — rode `poetry run python scripts/reindex.py` primeiro)")
        return

    for i, r in enumerate(results, start=1):
        preview = r.text.strip().replace("\n", " ")
        if len(preview) > PREVIEW_CHARS:
            preview = preview[:PREVIEW_CHARS] + "…"
        print(f"#{i}  score {r.score:.4f}  {r.chunk_id}")
        print(f"      {preview}")


def main() -> None:
    store = LanceDBVectorStore()
    embedder = OllamaEmbeddingProvider()

    args_question = " ".join(sys.argv[1:]).strip()
    if args_question:
        ask(store, embedder, args_question)
        return

    print(f"Modo interativo — top {TOP_K} resultados por pergunta. 'sair' (ou Ctrl+C) pra encerrar.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"sair", "exit", "quit"}:
            break
        ask(store, embedder, question)
        print()


if __name__ == "__main__":
    main()
