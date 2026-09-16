# moto_mcp

Base de conhecimento e time de agentes de IA genérico e reutilizável — sem identidade de
empresa, cliente ou pessoa específica embutida. Fork/clone este repositório para um
ecossistema novo e preencha `profile/profile.md`, `ecosystem/`, `clients/` e
`projects/` com o contexto real.

Comece sempre por `START_HERE.md`.

Arquivos-ponte:

- `CLAUDE.md` para Claude.
- `AGENTS.md` / `CODEX.md` para Codex.
- `GEMINI.md` para Gemini.
- `.github/copilot-instructions.md` para Copilot.

Não armazene secrets neste repositório.

## Servidor MCP

Este repositório também **é** um servidor MCP — expõe seu próprio
conteúdo (regras, knowledge, agentes, projetos, clientes) como tools
MCP via stdio (uso na mesma máquina) ou streamable-http (outro
dispositivo — via Tailscale, rede doméstica/LAN com token obrigatório,
ou só loopback), com leitura aberta e escrita restrita a `projects/`,
`clients/` e `profile/`. `pyproject.toml` e o pacote `mcp_server/`
ficam na raiz. Detalhes, modelo de segurança, transporte de rede e
como configurar num cliente MCP: ver `docs/mcp_server.md`.

Pra usar com um agente de terminal (OpenCode) e um modelo local (Ollama)
ou de nuvem (Claude), sem precisar entender o servidor por dentro: ver
`docs/guia_opencode.md` — passo a passo do zero.

## Licença

Nenhuma licença concedida por padrão — todos os direitos reservados até definição
explícita pelo mantenedor. Ver `LICENSE` (a criar) antes de redistribuir ou reutilizar
comercialmente.
