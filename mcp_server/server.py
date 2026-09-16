# mcp_server/server.py
#
# Transporte: stdio — sem porta de rede, sem auth pra pensar; o cliente
# MCP sobe este processo diretamente na máquina. Configuração de
# cliente MCP: ver docs/mcp_server.md.
#
# mcp_server é instalado no venv em modo editable (ver [tool.poetry]
# packages em pyproject.toml) — por isso nenhum ajuste de sys.path é
# necessário aqui: `from mcp_server import tools` resolve via
# site-packages do venv ativo, não importa como este arquivo foi
# carregado (`-m`, MCP Inspector, script direto).
#
# host/port vêm de Settings.NETWORK_HOST/NETWORK_PORT mas são inertes
# aqui: só têm efeito quando o transporte é "streamable-http", nunca no
# stdio deste módulo. Passados no construtor porque FastMCP lê
# host/port de lá, não do run() — ver mcp_server/server_network.py, que
# importa este mesmo `mcp` (mesmas 12 tools, sem duplicar registro) e
# sobe com o outro transporte.

from mcp.server.fastmcp import FastMCP

from mcp_server import tools
from mcp_server.config import settings

mcp = FastMCP("MotoMCP-Framework", host=settings.NETWORK_HOST or "127.0.0.1", port=settings.NETWORK_PORT)

mcp.tool()(tools.get_capabilities)
mcp.tool()(tools.list_documents)
mcp.tool()(tools.read_document)
mcp.tool()(tools.search_documents)
mcp.tool()(tools.list_agents)
mcp.tool()(tools.search_web)
mcp.tool()(tools.search_semantic)
mcp.tool()(tools.reindex_search)
mcp.tool()(tools.compact_search_index)
mcp.tool()(tools.get_template)
mcp.tool()(tools.register_entry)
mcp.tool()(tools.replace_section)
mcp.tool()(tools.append_to_section)


if __name__ == "__main__":
    from mcp_server.startup import reindex_on_startup

    reindex_on_startup()
    mcp.run()
