# mcp_server/startup.py
#
# reindex_on_startup() existe pra resolver um problema real de quem
# acabou de clonar o repositório: search_semantic devolve vazio até
# alguém lembrar de rodar scripts/reindex.py manualmente, e continua
# desatualizado depois de qualquer edição de conteúdo até rodar de novo.
# Chamado no início dos dois pontos de entrada (server.py e
# server_network.py) — reindex() já é incremental/idempotente (só
# reprocessa o que mudou, por content_hash — ver mcp_server/indexing.py),
# A atualização roda em segundo plano: inferência lenta não bloqueia
# o handshake MCP; lotes já salvos são reaproveitados no próximo início.
#
# Falha de embedding (Ollama fora do ar, modelo não baixado, pacote
# banco vetorial indisponível/ollama não instalado) NUNCA deve impedir o servidor de subir —
# search_semantic é a única tool que depende disso; list_documents/
# read_document/search_documents/escrita continuam funcionando sem o
# Ollama. Por isso o erro é reportado (print, visível no log do
# processo) e engolido aqui, não propagado.
#
# store/embedder aceitos como parâmetro opcional só pra permitir
# injeção de fake nos testes (tests/test_startup.py) — mesmo padrão de
# mcp_server/tools.py (_vector_store()/_embedding_provider()): quem
# chama de verdade (server.py, server_network.py) não passa nada, os
# adaptadores reais (LanceDB com fallback SQLite/Ollama) são instanciados aqui dentro.

from __future__ import annotations

import sys
from threading import Thread

from mcp_server.embeddings import EmbeddingProvider
from mcp_server.errors import EmbeddingProviderError, VectorStoreError
from mcp_server.indexing import reindex
from mcp_server.vectorstore import VectorStore


def reindex_on_startup(store: VectorStore | None = None, embedder: EmbeddingProvider | None = None) -> None:
    """Atualiza o índice e registra falhas esperadas em stderr.

    O ponto de entrada inicia esta função em segundo plano, sem bloquear
    a conexão MCP enquanto os embeddings são gerados.
    """
    try:
        if store is None:
            from mcp_server.vectorstore import get_vector_store

            store = get_vector_store()
        if embedder is None:
            from mcp_server.embeddings import OllamaEmbeddingProvider

            embedder = OllamaEmbeddingProvider()

        report = reindex(store, embedder)
        print(
            f"[moto_mcp] Índice semântico atualizado: "
            f"{len(report.upserted)} novo(s)/atualizado(s), "
            f"{len(report.deleted)} removido(s), "
            f"{report.unchanged} sem mudança.",
            file=sys.stderr,
        )
    except (EmbeddingProviderError, VectorStoreError) as exc:
        print(
            "[moto_mcp] Aviso: não foi possível atualizar o índice "
            f"semântico no startup ({exc}). O servidor vai subir mesmo "
            "assim — search_semantic ficará indisponível/desatualizado "
            "até isso ser resolvido (ver knowledge/vector-search/ "
            "dependencias.md) e reindex_search ser chamado, manualmente "
            "ou no próximo restart.",
            file=sys.stderr,
        )


def start_reindex_on_startup() -> Thread:
    """Atualiza o índice sem bloquear o handshake MCP em CPUs lentas."""
    worker = Thread(target=reindex_on_startup, name="semantic-index", daemon=True)
    worker.start()
    return worker
