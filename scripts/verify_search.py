#!/usr/bin/env python
# scripts/verify_search.py
#
# Roda o conjunto fixo de perguntas de mcp_server/verification_questions.py
# contra o índice vetorial de verdade (LanceDB) e confirma que o chunk
# esperado aparece entre os top-K resultados de cada pergunta — ver
# "Verificação obrigatória" em
# knowledge/vector-search/embeddings-e-busca-semantica.md. Uso (da raiz
# do repositório, ou de qualquer lugar):
#
#   poetry run python scripts/verify_search.py
#
# Pré-requisito: já ter rodado `poetry run python scripts/reindex.py`
# pelo menos uma vez (senão o índice está vazio e toda pergunta falha
# trivialmente). Precisa do Ollama rodando (mesma coisa que
# scripts/reindex.py).
#
# Importante (ver seção 4 do doc de embeddings, "calibração"): não
# existe um score de corte fixo pra "relevante" — embeddings de texto
# real não chegam perto de 0 nem pra conteúdo sem relação nenhuma. Por
# isso este script não valida um score mínimo, só SE o chunk certo
# aparece nos primeiros TOP_K resultados (por padrão 8) — é a ORDEM
# relativa que importa, não o valor absoluto.

from __future__ import annotations

import sys
from pathlib import Path

# Mesmo raciocínio do sys.path em scripts/reindex.py — ver o comentário
# lá pro porquê completo (`package-mode = false` no pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server.embeddings import OllamaEmbeddingProvider  # noqa: E402
from mcp_server.vectorstore import LanceDBVectorStore  # noqa: E402
from mcp_server.verification_questions import VERIFICATION_QUESTIONS  # noqa: E402

TOP_K = 8


def main() -> None:
    store = LanceDBVectorStore()
    embedder = OllamaEmbeddingProvider()

    indexed = store.list_indexed()
    if not indexed:
        print(
            "O índice está vazio — rode `poetry run python scripts/reindex.py` "
            "primeiro. Sem isso, toda pergunta abaixo vai falhar trivialmente."
        )
        sys.exit(1)

    passed = 0
    failed = 0

    for case in VERIFICATION_QUESTIONS:
        question = case["question"]
        expected = case["expected_chunk_id"]

        vector = embedder.embed(question)
        results = store.search(vector, top_k=TOP_K)
        result_ids = [r.chunk_id for r in results]

        if expected in result_ids:
            rank = result_ids.index(expected) + 1
            score = results[rank - 1].score
            passed += 1
            print(f"OK    (#{rank}, score {score:.4f})  {question}")
        else:
            failed += 1
            print(f"FALHA (fora do top-{TOP_K})           {question}")
            print(f"         esperado: {expected}")
            print("         top resultados:")
            for r in results:
                print(f"           #{result_ids.index(r.chunk_id) + 1} ({r.score:.4f}) {r.chunk_id}")
            if expected not in indexed:
                print(
                    "         (chunk esperado nem existe no índice atual — "
                    "arquivo/seção mudou ou foi removido; atualize "
                    "verification_questions.py ou rode reindex.py de novo)"
                )

    total = passed + failed
    print(f"\n{passed}/{total} perguntas encontraram o chunk certo no top-{TOP_K}.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
