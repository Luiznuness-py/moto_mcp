# Moto MCP

Servidor MCP genérico para expor documentos de um repositório como ferramentas de leitura, busca e manutenção controlada.

O repositório pode ser usado como base de conhecimento local: adicione documentos em `knowledge/`, `projects/`, `clients/`, `profile/` e `agents/`, depois conecte um cliente MCP para consultar esse conteúdo.

Comece por `START_HERE.md`.

## Arquivos-ponte

- `AGENTS.md`
- `CLAUDE.md`
- `CODEX.md`
- `GEMINI.md`

## Servidor MCP

O pacote `mcp_server/` expõe tools MCP para:

- listar documentos;
- ler documentos;
- fazer busca textual;
- fazer busca semântica com `bge-m3` + LanceDB;
- fazer busca web via SearXNG local;
- criar e editar entradas permitidas em `projects/`, `clients/` e `profile/`.

Transportes disponíveis:

- stdio para uso local;
- Streamable HTTP para acesso por outro dispositivo.

Veja `docs/mcp_server.md`.

## Instalação rápida

```powershell
poetry install
ollama pull bge-m3
copy .env.example .env
poetry run python -m mcp_server.server_network
```

Guia completo: `docs/guia_instalacao_busca.md`.

## OpenCode

Para OpenCode local ou remoto, veja:

- `docs/guia_opencode.md`
- `docs/diagnostico_opencode_remoto.md`
- `opencode/opencode.remote.example.json`
- `opencode/AGENTS.md`

## Segurança

- `.env` real não deve ser commitado.
- `searxng/settings.yml` real não deve ser commitado.
- Em modo `lan`, Bearer token é obrigatório.
- Escrita via MCP é restrita a `projects/`, `clients/` e `profile/`.

## Licença

MIT — ver `LICENSE`.
