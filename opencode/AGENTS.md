# Regras deste OpenCode

O MCP `moto-mcp` é a fonte principal de contexto deste projeto.

Importante: este MCP expõe tools, não resources. Não tente usar `list_mcp_resources` para consultar o `moto-mcp`.

Antes de responder sobre arquitetura, configuração, instalação, decisões do projeto, rede, OpenCode, Ollama, busca textual, busca semântica ou segurança, chame uma destas tools do MCP:

1. `moto-mcp_get_capabilities` para descobrir as tools disponíveis *SEM ARGUMENTOS*.
2. `moto-mcp_search_documents` para procurar texto exato nos documentos.
3. `moto-mcp_search_semantic` para procurar por sentido/contexto.
4. `moto-mcp_read_document` para ler o documento encontrado.
5. `moto-mcp_list_documents` se precisar listar documentos existentes.

Fluxo padrão:

1. Use `moto-mcp_search_documents` ou `moto-mcp_search_semantic` com a pergunta do usuário.
2. Use `moto-mcp_read_document` nos arquivos retornados quando precisar de contexto completo.
3. Só depois responda ao usuário.

Se houver conflito entre conhecimento geral do modelo e documentos retornados pelo `moto-mcp`, siga os documentos retornados pelo `moto-mcp`.

Não invente configuração. Se não encontrar a informação usando as tools do `moto-mcp`, diga que não encontrou.