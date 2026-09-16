# Guia — moto_mcp em máquina fraca, VPS ou notebook abandonado

Este guia é pra quem não tem GPU forte, ou quer deixar o `moto_mcp`
rodando sozinho numa máquina que sobrou (VPS barata, notebook velho) —
não é sobre o servidor MCP em si (esse já é leve por natureza, Python
puro, sem GPU), é sobre o **modelo de IA** que vai usar as tools dele.

## Perfis testados de verdade (não estimativa)

| Perfil | Modelo | Contexto (`OLLAMA_CONTEXT_LENGTH`) | Status |
|---|---|---|---|
| Fraco | `qwen3:4b` | `16384` | **Confirmado** — testado de ponta a ponta dentro do OpenCode + `moto-mcp` real, chamou a tool certa |
| Fraco/médio | `qwen3:8b` | `16384` | **Confirmado** — mesmo teste, mesmo resultado |
| Médio | `qwen3:14b` | `32768` | **Confirmado**, mas com ressalva: em GPU de 16GB (RTX 5070 Ti), já usa ~95% da VRAM — pouca margem pra conversa longa |
| Forte | modelo maior (ex: `qwen3-coder:30b` ou equivalente) | `32768`+ | **Futuro, não testado** |

**Testado e reprovado, não use**: `qwen2.5-coder:14b` (não emite
`tool_calls` estruturado neste Ollama, mesmo sendo anunciado como
"tool-capable") e `mistral-nemo:12b` (declarado `tools` nas
capabilities do Ollama, mas falhou 2x de formas diferentes dentro do
OpenCode — uma vez resposta quebrada, outra vez **inventou** uma
chamada de tool que nunca executou de verdade).

Antes de confiar num modelo novo que não está nessa tabela, rode:

```bash
poetry run python scripts/test_tool_calling.py <nome-do-modelo>
```

Isso é um filtro rápido — se falhar aqui, com certeza falha no OpenCode
também. Se passar, ainda **precisa confirmar com um teste real dentro
do OpenCode** antes de recomendar (foi exatamente assim que o
`mistral-nemo:12b` escapou de um teste isolado e falhou no uso real —
não repita esse erro).

## Como perceber que o contexto está insuficiente

Sinais reais, observados nesta sessão (não hipotéticos):

- O modelo diz que a tool "não está disponível" ou lista só ferramentas
  genéricas (`bash`, `write`, `task`...), nunca as do `moto-mcp`.
- A resposta vem completamente vazia, sem texto nem chamada de tool.
- O modelo **finge** ter chamado uma tool (escreve algo tipo
  `list_agents` num bloco de código) e inventa uma resposta plausível,
  sem o indicador de execução real (no OpenCode, aparece um `⚙` antes
  do nome da tool quando ela roda de verdade — sem esse símbolo, foi
  invenção, não execução).

Se qualquer um desses acontecer, o primeiro passo é aumentar
`OLLAMA_CONTEXT_LENGTH`, não trocar de modelo — foi a causa raiz real
na maioria dos casos testados hoje.

## Quando evitar o OpenCode "pesado"

Se sua máquina não aguenta nem o perfil fraco (`qwen3:4b` + contexto
`16384`), duas saídas sem exigir hardware nenhum:

1. **Modelo gratuito de nuvem via OpenCode** (`opencode/big-pickle` ou
   equivalente, contexto de 200k, zero custo) — o raciocínio roda fora
   da sua máquina, você só precisa do cliente OpenCode leve.
2. **Sem agente nenhum**: `scripts/ask.py` (busca semântica direto) ou
   `scripts/search_documents` via `read_document` manual — tira valor
   do `moto_mcp` sem precisar de LLM decidindo nada.

## Rodando de forma persistente (VPS/notebook abandonado)

Sem serviço systemd, sem Docker/Podman — só terminal, do jeito mais
simples que sobrevive a fechar a conexão SSH:

```bash
cd ~/moto_mcp
poetry install
export MOTO_MCP_NETWORK_MODE=lan   # ou tailscale, se preferir
export MOTO_MCP_NETWORK_HOST=<ip-da-maquina>
export MOTO_MCP_AUTH_TOKEN=<token gerado, obrigatório em modo lan>

nohup poetry run python -m mcp_server.server_network > moto_mcp.log 2>&1 &
disown
```

- `nohup` + `&` + `disown`: o processo continua rodando mesmo depois
  de você fechar o terminal/SSH.
- `moto_mcp.log` guarda a saída — confira ali se algo travou.

**Conferir se ainda está rodando** (a qualquer momento, mesmo depois de
reconectar via SSH):

```bash
ps aux | grep mcp_server.server_network
curl -s -o /dev/null -w "%{http_code}\n" http://<ip>:8765/mcp
```

`406` = está de pé (é o comportamento correto de um `GET` simples, não
é erro). Sem resposta/conexão recusada = caiu, precisa subir de novo
com o mesmo comando acima.

**Se cair sozinho** (reboot da VPS, processo morreu): não tem
reinício automático nessa abordagem simples — é rodar o comando de
novo manualmente. Se isso incomodar no dia a dia, aí sim vale
reconsiderar um `systemd`, mas comece simples; só complique quando o
simples realmente incomodar.
