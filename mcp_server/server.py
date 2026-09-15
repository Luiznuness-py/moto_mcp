# mcp_server/server.py
#
# Transporte: stdio (decisão do Yuri — sem porta de rede, sem auth pra
# pensar; o cliente MCP sobe este processo diretamente na máquina).
# Configuração de cliente MCP: ver README.md.

from mcp.server.fastmcp import FastMCP

from mcp_server import tools

mcp = FastMCP("MotoMCP-Framework")

mcp.tool()(tools.get_capabilities)
mcp.tool()(tools.list_documents)
mcp.tool()(tools.read_document)
mcp.tool()(tools.search_documents)
mcp.tool()(tools.list_agents)
mcp.tool()(tools.get_template)
mcp.tool()(tools.register_entry)
mcp.tool()(tools.replace_section)
mcp.tool()(tools.append_to_section)


if __name__ == "__main__":
    mcp.run()
