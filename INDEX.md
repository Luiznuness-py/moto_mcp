# Index

Entrada obrigatória: `START_HERE.md`.

## Pastas

- `global/` - perfil do usuário, workflow, regras absolutas, política de commit e padrões gerais.
- `ecosystem/` - visão geral da empresa/produto/infraestrutura do usuário (preencher).
- `agents/` - perfis/instruções de Bill, Fred, Homes, Levi, Mike e Red.
- `knowledge/` - base conceitual/técnica consultiva.
- `projects/` - memória por projeto (um arquivo por projeto).
- `clients/` - memória por cliente (um arquivo por cliente).
- `templates/` - prompts e checklists reutilizáveis.
- `handoff/` - modelos de repasse entre agentes.
- `mcp_server/` - pacote Python do servidor MCP que este repositório expõe de si mesmo (raiz também tem `pyproject.toml`/`tests/` — ver `docs/mcp_server.md`).

## Arquivos-ponte

- `AGENTS.md`
- `CLAUDE.md`
- `CODEX.md`
- `GEMINI.md`
- `.github/copilot-instructions.md`

## Projetos e clientes registrados

- `projects/moto-mcp-framework-server.md` — servidor MCP (stdio) que
  expõe o próprio moto_mcp (regras/knowledge/agentes/projetos/clientes)
  como tools MCP. Código na raiz do repositório (`mcp_server/`,
  `pyproject.toml`, `tests/`) — ver `docs/mcp_server.md` para detalhes
  técnicos. Ver o arquivo em `projects/` para decisões de arquitetura e
  pendências.
- `projects/moto-mcp-server.md` — **OBSOLETO**, código removido. Gateway
  MCP do MotoOCR que chegou a ser colocado dentro deste repositório por
  engano; removido pelo Yuri. Mantido só como registro histórico.
