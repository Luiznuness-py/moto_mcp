# Guia — OpenCode com moto_mcp

Este guia mostra como usar o OpenCode como cliente do `moto_mcp`.

Para OpenCode em outro computador, use também `docs/diagnostico_opencode_remoto.md` e `opencode/opencode.remote.example.json`.

## Instalar Node.js

Instale a versão LTS em <https://nodejs.org>.

Verifique:

```powershell
node --version
npm --version
```

## Instalar OpenCode

```powershell
npm install -g opencode-ai@1.18.31
opencode --version
```

## Usar Ollama local

Instale o Ollama em <https://ollama.com> e baixe um modelo compatível com tool calling:

```powershell
ollama pull qwen3:14b
```

Suba o Ollama com contexto suficiente:

```powershell
$env:OLLAMA_CONTEXT_LENGTH = "32768"
ollama serve
```

Em outro terminal, na raiz do repositório:

```powershell
$env:MOTO_MCP_OPENCODE_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
opencode --model ollama/qwen3:14b
```

## Conferir MCP local

Na raiz do repositório:

```powershell
opencode mcp list
```

Esperado: `moto-mcp` conectado.

## Testar uma tool

Dentro do OpenCode, peça:

```text
Use a tool moto-mcp_get_capabilities agora. Não explique. Apenas execute a tool.
```

O resultado precisa ser uma chamada real de tool. Texto que apenas descreve uma chamada não é validação.

## Usar provider remoto

Se o Ollama estiver em outra máquina, configure a URL OpenAI compatible:

```powershell
$env:MOTO_MCP_OPENCODE_OLLAMA_BASE_URL = "http://IP_DO_OLLAMA:11434/v1"
opencode --model ollama/qwen3:14b
```

Para MCP remoto com Bearer, use `opencode/opencode.remote.example.json`.
