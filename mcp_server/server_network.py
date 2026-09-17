# mcp_server/server_network.py
#
# Ponto de entrada do modo de rede — mesmo servidor de mcp_server/server.py
# (mesmas 13 tools, importadas de lá, sem duplicar registro), só que
# subindo com transporte streamable-http em vez de stdio. Uso:
#
#   poetry run python -m mcp_server.server_network
#
# Três modos (MOTO_MCP_NETWORK_MODE, padrão "tailscale") — ver
# mcp_server/network.py pra validação de verdade e docs/mcp_server.md,
# "Transporte de rede", pra explicação completa de cada um:
#
# - "tailscale" (padrão): só IP da faixa do Tailscale. Autenticação de
#   dispositivo já vem do próprio Tailscale; token Bearer é opcional
#   aqui (defesa em profundidade, se configurado).
# - "lan": rede doméstica. Token Bearer OBRIGATÓRIO — sem
#   MOTO_MCP_AUTH_TOKEN configurado, o servidor recusa subir
#   (ensure_safe_bind_host cuida disso).
# - "local": só 127.0.0.1/::1. Token opcional.
#
# Usa mcp.streamable_http_app() + uvicorn direto (em vez de
# mcp.run(transport=...)) especificamente pra poder acoplar o
# BearerTokenMiddleware quando há token configurado — mesmo padrão já
# usado pelo transporte Streamable HTTP do MCP.

import sys

import uvicorn

from mcp_server.config import settings
from mcp_server.errors import UnsafeBindHostError
from mcp_server.network import ensure_safe_bind_host
from mcp_server.server import mcp

if __name__ == "__main__":
    from mcp_server.startup import reindex_on_startup

    # Mensagem limpa em vez de stack trace do Python — quem roda isso
    # pela primeira vez (público que este servidor mira: pouco
    # conhecimento técnico, ver docs/guia_maquina_fraca.md) não deveria
    # ler traceback de código pra entender "esqueci de configurar uma
    # variável de ambiente".
    # comando sem nenhuma variável setada, igual quem clona o
    # repositório pela primeira vez faria.
    try:
        ensure_safe_bind_host(settings.NETWORK_HOST, settings.NETWORK_MODE, settings.AUTH_TOKEN)
    except UnsafeBindHostError as exc:
        print(f"[moto_mcp] Não foi possível subir o servidor de rede: {exc}", file=sys.stderr)
        sys.exit(1)

    reindex_on_startup()

    app = mcp.streamable_http_app()
    if settings.AUTH_TOKEN:
        from mcp_server.auth import BearerTokenMiddleware

        app.add_middleware(BearerTokenMiddleware, token=settings.AUTH_TOKEN)

    uvicorn.run(app, host=settings.NETWORK_HOST, port=settings.NETWORK_PORT)
