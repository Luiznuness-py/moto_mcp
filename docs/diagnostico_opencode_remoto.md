# OpenCode remoto com moto_mcp e Ollama

Guia para configurar um computador cliente com OpenCode apontando para MCP e Ollama remotos.

## Endpoints

- MCP: `http://10.80.132.178:8765/mcp`
- Ollama OpenAI compatible: `http://10.80.132.178:11434/v1`
- Ollama status: `http://10.80.132.178:11434/api/ps`

## Requisitos

- OpenCode `1.18.31`.
- Servidor MCP em modo `lan` com Bearer token.
- Perfis Ollama com contexto ampliado:
  - `qwen3-14b-motomcp-32k`
  - `qwen3-8b-motomcp-16k`
  - `qwen3-4b-motomcp-16k`

## Configuração do cliente

Na pasta onde o OpenCode será executado:

1. Copie `opencode/opencode.remote.example.json` para `opencode.json`.
2. Copie `opencode/AGENTS.md` para `AGENTS.md`.
3. Configure o token no terminal que inicia o OpenCode:

```powershell
$segredo = Read-Host 'Bearer token do moto_mcp' -AsSecureString
$env:MOTO_MCP_AUTH_TOKEN = [System.Net.NetworkCredential]::new('', $segredo).Password
Remove-Variable segredo
```

O token não deve ser salvo no JSON distribuível.

## Validar conexão

```powershell
opencode --version
opencode mcp list
opencode mcp debug motomcp
```

Em OpenCode `1.18.31`, `mcp debug` verifica OAuth. Com `oauth: false`, a saída esperada indica OAuth desativado. Isso não substitui teste real de tool.

## Validar tool calling

Use sessões novas. Não use `--continue` durante comparação.

```powershell
opencode run --model ollama/qwen3:14b --format json 'Use a tool motomcp_get_capabilities agora. Não explique. Apenas execute a tool.'
opencode run --model ollama/qwen3:14b --format json 'Use motomcp_search_documents para procurar MOTO_MCP_NETWORK_MODE.'
opencode run --model ollama/qwen3:14b --format json 'Quais são os modos de rede do moto_mcp e quando o Bearer token é obrigatório? Consulte a documentação pelo MCP e cite o arquivo usado.'
```

Repita com:

```powershell
opencode run --model ollama/qwen3:8b --format json 'Use motomcp_search_documents para procurar MOTO_MCP_NETWORK_MODE.'
opencode run --model ollama/qwen3:4b --format json 'Use motomcp_search_documents para procurar MOTO_MCP_NETWORK_MODE.'
```

Critério de aceite:

- evento `tool_use` real;
- tool `motomcp_*` correta;
- status concluído;
- saída com dados reais.

`connected` isolado não comprova uso de tool.

## Conferir contexto efetivo do Ollama

Durante uma inferência:

```powershell
(Invoke-RestMethod 'http://10.80.132.178:11434/api/ps').models |
  Select-Object name, context_length, size_vram
```

O campo `limit.context` no `opencode.json` informa limite ao OpenCode, mas não altera sozinho o contexto do runtime Ollama. Use perfis Ollama com `num_ctx` configurado.
