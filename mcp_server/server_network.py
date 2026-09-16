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
# usado pelo mcp_gateway/server.py do moto_ocr.

import uvicorn

from mcp_server.config import settings
from mcp_server.network import ensure_safe_bind_host
from mcp_server.server import mcp

if __name__ == "__main__":
    from mcp_server.startup import reindex_on_startup

    ensure_safe_bind_host(settings.NETWORK_HOST, settings.NETWORK_MODE, settings.AUTH_TOKEN)
    reindex_on_startup()

    app = mcp.streamable_http_app()
    if settings.AUTH_TOKEN:
        from mcp_server.auth import BearerTokenMiddleware

        app.add_middleware(BearerTokenMiddleware, token=settings.AUTH_TOKEN)

    uvicorn.run(app, host=settings.NETWORK_HOST, port=settings.NETWORK_PORT)
