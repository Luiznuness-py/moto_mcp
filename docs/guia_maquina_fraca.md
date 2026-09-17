# Guia — modelos menores e máquinas fracas

O servidor `moto_mcp` é leve. O maior consumo costuma vir do modelo usado pelo OpenCode/Ollama.

## Perfis recomendados

| Perfil | Modelo | Contexto sugerido |
|---|---|---:|
| Fraco | `qwen3:4b` | `16384` |
| Fraco/médio | `qwen3:8b` | `16384` |
| Médio | `qwen3:14b` | `32768` |

Modelos maiores podem funcionar, mas devem ser validados no ambiente real.

## Testar tool calling antes de usar

```powershell
poetry run python scripts/test_tool_calling.py qwen3:8b
```

Esse teste é um filtro inicial. Depois valide dentro do OpenCode com uma chamada real de tool.

## Sinais de contexto insuficiente

- O modelo diz que a tool não existe.
- O modelo responde sem executar tool.
- O modelo escreve uma chamada como texto, mas não há evento real de tool.
- A resposta vem vazia ou genérica.

Ajuste o contexto do Ollama ou use um perfil de modelo menor.

## Rodar o MCP de forma simples em VPS/notebook

```bash
cd ~/moto_mcp
poetry install
cp .env.example .env
nano .env
nohup poetry run python -m mcp_server.server_network > moto_mcp.log 2>&1 &
disown
```

Conferir processo:

```bash
ps aux | grep mcp_server.server_network
```

Conferir endpoint sem token:

```bash
curl -s -o /dev/null -w "%{http_code}
" http://<ip>:8765/mcp
```

Conferir endpoint com Bearer:

```bash
curl -s -o /dev/null -w "%{http_code}
" -H "Authorization: Bearer <token>" http://<ip>:8765/mcp
```

Em modo `lan`, uma chamada sem Bearer deve retornar `401`. Uma chamada `GET` simples autenticada pode retornar `406`, pois não completa o handshake MCP.
