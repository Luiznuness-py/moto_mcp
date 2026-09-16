# mcp_server/server_network.py
#
# Ponto de entrada do modo de rede — mesmo servidor de mcp_server/server.py
# (mesmas 12 tools, importadas de lá, sem duplicar registro), só que
# subindo com transporte streamable-http em vez de stdio. Uso:
#
#   poetry run python -m mcp_server.server_network
#
# Pré-requisito: MOTO_MCP_NETWORK_HOST configurado com o IP da interface
# do Tailscale desta máquina (`tailscale ip -4`) — ensure_safe_bind_host
# recusa subir sem isso, ou com qualquer host fora da faixa do Tailscale.
#
# Modelo de segurança deste modo: o Tailscale é a fronteira de confiança
# (device auth do próprio tailnet) — este servidor não tem autenticação
# própria (sem token/Bearer). Qualquer dispositivo já aprovado no
# tailnet do usuário que alcança essa porta tem acesso total às 12 tools
# (leitura do repositório inteiro, escrita em projects/clients/profile).
# Aceitável enquanto for só dispositivo do próprio usuário — ver
# to-do.md, "Transporte de rede", pra a decisão completa e a condição
# que tornaria isso insuficiente (um consumidor fora do controle do
# usuário alcançando a porta).

from mcp_server.config import settings
from mcp_server.network import ensure_safe_bind_host
from mcp_server.server import mcp

if __name__ == "__main__":
    from mcp_server.startup import reindex_on_startup

    ensure_safe_bind_host(settings.NETWORK_HOST)
    reindex_on_startup()
    mcp.run(transport="streamable-http")
