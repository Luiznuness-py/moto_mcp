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

## Comandos rápidos

### Instalar dependências

```powershell
poetry install
ollama pull bge-m3
copy .env.example .env
```

Edite o `.env` antes de subir o servidor. Em modo `lan`, configure `MOTO_MCP_AUTH_TOKEN`.

Guia completo: [docs/guia_instalacao_busca.md](docs/guia_instalacao_busca.md).

### Subir SearXNG

Primeira vez:

```powershell
copy searxng\settings.yml.example searxng\settings.yml
python -c "import secrets; print(secrets.token_hex(32))"
notepad searxng\settings.yml
```

No `searxng/settings.yml`, troque `server.secret_key: "ultrasecretkey"` pelo valor gerado. Mantenha `search.formats` com `json`.

Subir:

```powershell
podman machine start
podman compose -p moto-mcp -f docker-compose.yml up -d searxng
```

Testar:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/search?q=teste&format=json"
```

Detalhes: [docs/mcp_server.md](docs/mcp_server.md#searxng-para-search_web).

### Subir o MCP

Local, na mesma máquina do cliente MCP:

```powershell
poetry run python -m mcp_server.server
```

Rede, para outro computador acessar:

```powershell
poetry run python -m mcp_server.server_network
```
OU

```bash
nohup poetry run python -m mcp_server.server_network > moto_mcp.log 2>&1 & disown

tail -f moto_mcp.log
```
Detalhes: [docs/mcp_server.md](docs/mcp_server.md).

### Rodar OpenCode local

```powershell
npm install -g opencode-ai@1.18.31
$env:MOTO_MCP_OPENCODE_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
opencode --model ollama/qwen3:14b
```

Guia completo: [docs/guia_opencode.md](docs/guia_opencode.md).

### Rodar OpenCode pela pasta do projeto

A pasta [opencode/](opencode/) já traz a configuração do OpenCode para usar MCP e Ollama remotos.

Crie o arquivo local do Bearer token:

```powershell
cd opencode
notepad .motomcp-token
```

Cole somente o token no arquivo, sem `Bearer` e sem aspas. Esse arquivo é ignorado pelo Git.

Rodar:

```powershell
opencode --model ollama/qwen3:14b
```

Validar:

```powershell
opencode mcp list
opencode run --model ollama/qwen3:14b --format json 'Use a tool motomcp_get_capabilities agora. Não explique. Apenas execute a tool.'
```

Configuração usada: [opencode/opencode.json](opencode/opencode.json). Guia remoto: [docs/diagnostico_opencode_remoto.md](docs/diagnostico_opencode_remoto.md).

## Segurança

- `.env` real não deve ser commitado.
- `searxng/settings.yml` real não deve ser commitado.
- Em modo `lan`, Bearer token é obrigatório.
- Escrita via MCP é restrita a `projects/`, `clients/` e `profile/`.

## Licença

MIT — ver `LICENSE`.
