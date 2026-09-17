# Guia rápido — instalar, configurar e rodar buscas

Este guia instala o `moto_mcp`, sobe o servidor e valida busca textual e semântica.

## 1. Instalar requisitos

Instale:

1. Python `>=3.13,<4.0`.
2. Poetry.
3. Ollama.

Na raiz do repositório:

```powershell
poetry install
ollama pull bge-m3
```

## 2. Configurar `.env`

Copie o exemplo:

```powershell
copy .env.example .env
```

Exemplo LAN:

```env
MOTO_MCP_NETWORK_MODE=lan
MOTO_MCP_NETWORK_HOST=192.168.1.10
MOTO_MCP_NETWORK_PORT=8765
MOTO_MCP_AUTH_TOKEN=gere-um-token-com-32-ou-mais-caracteres
MOTO_MCP_OLLAMA_HOST=http://127.0.0.1:11434
MOTO_MCP_EMBEDDING_MODEL=bge-m3
MOTO_MCP_SEARXNG_BASE_URL=http://127.0.0.1:8080
```

Gerar token:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## 3. Subir SearXNG

Primeira vez:

```powershell
copy searxng\settings.yml.example searxng\settings.yml
notepad searxng\settings.yml
```

Troque o `secret_key`.

Subir:

```powershell
podman machine start
podman compose -p moto-mcp -f docker-compose.yml up -d searxng
```

Testar:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/search?q=teste&format=json"
```

## 4. Rodar o servidor MCP

Local/stdio:

```powershell
poetry run python -m mcp_server.server
```

Rede/HTTP:

```powershell
poetry run python -m mcp_server.server_network
```

## 5. Reindexar manualmente

```powershell
poetry run python scripts/reindex.py
```

O servidor também tenta reindexar ao iniciar.

## 6. Testar busca textual

Em um cliente MCP:

```text
Use search_documents para procurar "MOTO_MCP_NETWORK_MODE".
```

## 7. Testar busca semântica

```powershell
poetry run python scripts/ask.py "modo lan token bearer"
```

Ou em um cliente MCP:

```text
Use search_semantic para buscar: modo lan token bearer
```

## 8. Validar perguntas conhecidas

```powershell
poetry run python scripts/verify_search.py
```

## 9. OpenCode em outro computador

Use:

- `docs/diagnostico_opencode_remoto.md`
- `opencode/opencode.remote.example.json`
- `opencode/AGENTS.md`

Na máquina do OpenCode, configure o token no terminal:

```powershell
$segredo = Read-Host 'Bearer token do moto_mcp' -AsSecureString
$env:MOTO_MCP_AUTH_TOKEN = [System.Net.NetworkCredential]::new('', $segredo).Password
Remove-Variable segredo
```

Depois valide:

```powershell
opencode mcp list
opencode run --model ollama/qwen3:14b --format json 'Use a tool motomcp_get_capabilities agora. Não explique. Apenas execute a tool.'
opencode run --model ollama/qwen3:14b --format json 'Use motomcp_search_documents para procurar MOTO_MCP_NETWORK_MODE.'
```
