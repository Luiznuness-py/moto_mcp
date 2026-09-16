# mcp_server/startup.py
#
# reindex_on_startup() existe pra resolver um problema real de quem
# acabou de clonar o repositório: search_semantic devolve vazio até
# alguém lembrar de rodar scripts/reindex.py manualmente, e continua
# desatualizado depois de qualquer edição de conteúdo até rodar de novo.
# Chamado no início dos dois pontos de entrada (server.py e
# server_network.py) — reindex() já é incremental/idempotente (só
# reprocessa o que mudou, por content_hash — ver mcp_server/indexing.py),
# então rodar isso toda vez que o servidor sobe é barato depois da
# primeira vez, não um custo repetido.
#
# Falha de embedding (Ollama fora do ar, modelo não baixado, pacote
# lancedb/ollama não instalado) NUNCA deve impedir o servidor de subir —
# search_semantic é a única tool que depende disso; list_documents/
# read_document/search_documents/escrita continuam funcionando sem o
# Ollama. Por isso o erro é reportado (print, visível no log do
# processo) e engolido aqui, não propagado.
#
# store/embedder aceitos como parâmetro opcional só pra permitir
# injeção de fake nos testes (tests/test_startup.py) — mesmo padrão de
# mcp_server/tools.py (_vector_store()/_embedding_provider()): quem
# chama de verdade (server.py, server_network.py) não passa nada, os
# adaptadores reais (LanceDB/Ollama) são instanciados aqui dentro.

from __future__ import annotations

from mcp_server.embeddings import EmbeddingProvider
from mcp_server.errors import EmbeddingProviderError, VectorStoreError
from mcp_server.indexing import reindex
from mcp_server.vectorstore import VectorStore


def reindex_on_startup(store: VectorStore | None = None, embedder: EmbeddingProvider | None = None) -> None:
    """Reindexa o repositório no índice vetorial antes do servidor
    começar a aceitar chamadas. Não levanta exceção — falha aqui vira
    aviso no log, nunca impede o servidor de subir (ver comentário no
    topo do arquivo)."""
    try:
        if store is None:
            from mcp_server.vectorstore import LanceDBVectorStore

            store = LanceDBVectorStore()
        if embedder is None:
            from mcp_server.embeddings import OllamaEmbeddingProvider

            embedder = OllamaEmbeddingProvider()

        report = reindex(store, embedder)
        print(
            f"[moto_mcp] Índice semântico atualizado: "
            f"{len(report.upserted)} novo(s)/atualizado(s), "
            f"{len(report.deleted)} removido(s), "
            f"{report.unchanged} sem mudança."
        )
    except (EmbeddingProviderError, VectorStoreError) as exc:
        print(
            "[moto_mcp] Aviso: não foi possível atualizar o índice "
            f"semântico no startup ({exc}). O servidor vai subir mesmo "
            "assim — search_semantic ficará indisponível/desatualizado "
            "até isso ser resolvido (ver knowledge/vector-search/ "
            "dependencias.md) e reindex_search ser chamado, manualmente "
            "ou no próximo restart."
        )
