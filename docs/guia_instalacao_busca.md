# Guia rápido — instalar, configurar e rodar buscas

Este guia é o caminho curto para rodar o `moto_mcp` em uma máquina nova e
confirmar que as duas buscas funcionam:

- busca textual, por palavra exata (`search_documents`);
- busca por sentido/cosseno, usando embeddings `bge-m3` + LanceDB
  (`search_semantic`).

## 1. Instalar o básico

Instale:

1. Python `>=3.13,<4.0`.
2. Poetry.
3. Ollama.

Depois, na raiz do repositório:

```bash
poetry install
```

Baixe o modelo de embedding usado pela busca por cosseno:

```bash
ollama pull bge-m3
```

O LanceDB e o cliente Python do Ollama já estão nas dependências do projeto.
Não precisa instalar um banco separado: o LanceDB é embarcado e grava o índice
em `.vector_index/`.

## 2. Configurar o `.env`

Copie o exemplo:

```bash
cp .env.example .env
```

Para rodar só local, via cliente MCP na mesma máquina, você pode deixar o
`.env` sem modo de rede.

Para rodar pela LAN:

```env
MOTO_MCP_NETWORK_MODE=lan
MOTO_MCP_NETWORK_HOST=192.168.1.10
MOTO_MCP_NETWORK_PORT=8765
MOTO_MCP_AUTH_TOKEN=gere-um-token-com-32-ou-mais-caracteres
```

Gere um token real:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Para rodar via Tailscale:

```env
MOTO_MCP_NETWORK_MODE=tailscale
MOTO_MCP_NETWORK_HOST=100.x.x.x
MOTO_MCP_NETWORK_PORT=8765
```

Se o Ollama estiver na mesma máquina:

```env
MOTO_MCP_OLLAMA_HOST=http://127.0.0.1:11434
MOTO_MCP_EMBEDDING_MODEL=bge-m3
```

Se o Ollama de embeddings estiver em outra máquina, use o endereço alcançável
por esta máquina:

```env
MOTO_MCP_OLLAMA_HOST=http://100.x.x.x:11434
MOTO_MCP_EMBEDDING_MODEL=bge-m3
```

Esse Ollama é usado pelo `moto_mcp` só para embeddings da busca semântica. O
Ollama que o OpenCode usa para raciocinar é configurado no ambiente do próprio
OpenCode, não neste `.env`.

## 3. Rodar o servidor

Mesmo computador do cliente MCP, sem rede:

```bash
poetry run python -m mcp_server.server
```

Outro computador acessando pela rede:

```bash
poetry run python -m mcp_server.server_network
```

Ao subir, o servidor tenta atualizar o índice semântico automaticamente. Se o
Ollama estiver fora do ar, o servidor sobe mesmo assim: a busca textual continua
funcionando, mas `search_semantic` fica indisponível ou desatualizada até o
Ollama/`bge-m3` estar pronto.

## 4. Reindexar manualmente

Depois de editar muitos arquivos, ou para testar explicitamente a busca por
cosseno:

```bash
poetry run python scripts/reindex.py
```

Esse comando:

- lê os `.md`/`.txt` do repositório;
- divide o conteúdo por seções Markdown;
- gera embeddings com `bge-m3` via Ollama;
- grava ou atualiza os vetores no LanceDB;
- pula chunks que não mudaram.

## 5. Testar busca textual

A busca textual não precisa de Ollama nem LanceDB. Ela procura palavra/frase
exata nos arquivos.

Em um cliente MCP, peça algo como:

```text
Use search_documents para procurar "MOTO_MCP_NETWORK_MODE".
```

Resultado esperado: a tool retorna arquivos e linhas onde esse texto aparece.

## 6. Testar busca por cosseno

A busca semântica precisa:

- Ollama rodando;
- modelo `bge-m3` baixado;
- índice LanceDB populado.

Teste por script:

```bash
poetry run python scripts/ask.py "por que o modo lan precisa de token?"
```

Ou, em um cliente MCP:

```text
Use search_semantic para buscar: por que o modo lan precisa de token?
```

Resultado esperado: a resposta deve trazer chunks relacionados a
`MOTO_MCP_AUTH_TOKEN`, modo LAN ou modelo de segurança de rede, mesmo que a
pergunta não use exatamente as mesmas palavras do arquivo.

## 7. Testar a verificação completa

Quando quiser validar o índice com perguntas conhecidas:

```bash
poetry run python scripts/verify_search.py
```

Esse script compara perguntas de verificação com os chunks esperados. Só trate
a busca por cosseno como validada se ele passar de verdade.

## 8. Configurar OpenCode em outro computador

O computador que roda OpenCode precisa acessar:

1. o `moto_mcp`;
2. o Ollama de raciocínio usado pelo OpenCode.

Instale o Node.js LTS:

```bash
node --version
npm --version
```

Instale o OpenCode na versão usada/testada por este projeto:

```bash
npm install -g opencode-ai@1.18.31
opencode --version
```

O OpenCode lê um arquivo chamado `opencode.json` na pasta onde você roda o
comando `opencode`.

Se o computador cliente também tem este repositório clonado, use o
`opencode.json` que já existe na raiz do repo e edite o bloco `mcp` para
apontar para o servidor remoto.

Se o computador cliente não tem este repositório, crie uma pasta para rodar o
OpenCode e crie um arquivo `opencode.json` dentro dela:

```bash
mkdir moto-mcp-client
cd moto-mcp-client
```

Se você criou uma pasta nova só para o OpenCode, o arquivo
`opencode.json` precisa ter a configuração do MCP e também a configuração do
provedor Ollama. Crie o arquivo com este conteúdo mínimo:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "motomcp": {
        "type": "remote",
        "url": "http://192.168.1.10:8765/mcp",
        "oauth": false,
        "codemode": false,
        "headers": {
          "Authorization": "Bearer seu-token"
        }
      }
    }
  },
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama",
      "options": {
        "baseURL": "{env:MOTO_MCP_OPENCODE_OLLAMA_BASE_URL}"
      },
      "models": {
        "qwen3:4b": {
          "name": "Qwen3 4B"
        },
        "qwen3:8b": {
          "name": "Qwen3 8B"
        },
        "qwen3:14b": {
          "name": "Qwen3 14B"
        }
      }
    }
  }
}
```

Troque:

- `http://192.168.1.10:8765/mcp` pelo IP/porta do notebook que roda o
  `moto_mcp`;
- `seu-token` pelo valor de `MOTO_MCP_AUTH_TOKEN` configurado no `.env` do
  servidor `moto_mcp`.

O nome do servidor no exemplo é `motomcp`, sem hífen, para gerar nomes de tools
mais simples para modelos locais. O `codemode: false` expõe as tools MCP mais
diretamente ao modelo em vez de deixá-las agrupadas no Code Mode do OpenCode.

Para o Ollama do OpenCode, configure uma variável no processo do OpenCode:

```powershell
$env:MOTO_MCP_OPENCODE_OLLAMA_BASE_URL = "http://192.168.1.20:11434/v1"
```

Isso é um comando de terminal, não uma linha para colocar no `.env` do
`moto_mcp`. O `.env` do `moto_mcp` é lido pelo servidor Python; o OpenCode lê
variáveis do próprio processo.

No PowerShell:

```powershell
$env:MOTO_MCP_OPENCODE_OLLAMA_BASE_URL = "http://192.168.1.20:11434/v1"
$env:MOTO_MCP_OPENCODE_OLLAMA_BASE_URL
opencode --model ollama/qwen3:8b
```

A segunda linha deve imprimir uma URL completa começando com `http://`. Se ela
ficar vazia, o OpenCode pode falhar com erro parecido com
`/chat/completions cannot be parsed as a URL`. Essa variável vale só para o
terminal atual; se fechar o terminal ou abrir o OpenCode por atalho, configure
de novo antes de rodar `opencode`.

No Git Bash/Linux:

```bash
export MOTO_MCP_OPENCODE_OLLAMA_BASE_URL="http://192.168.1.20:11434/v1"
opencode --model ollama/qwen3:8b
```

Para conferir se o OpenCode achou o MCP:

```bash
opencode mcp list
```

Esperado: `motomcp` aparecer como conectado. Depois pergunte algo que só o
repositório sabe, por exemplo:

```text
Use o moto-mcp para procurar MOTO_MCP_NETWORK_MODE.
```

## 9. Fazer o OpenCode consultar o MCP automaticamente

O `opencode.json` conecta o MCP, mas não obriga sozinho o agente a usar o MCP
como fonte de verdade. No OpenCode V2, o servidor precisa ficar dentro de
`mcp.servers`; se o arquivo usar `mcp.moto-mcp` direto, a versão atual pode
ignorar o servidor. Para isso, crie um arquivo `AGENTS.md` na mesma pasta
onde você roda o OpenCode:

```powershell
cd C:\Users\Motoshima\Desktop\OpenCode
notepad AGENTS.md
```

Conteúdo sugerido:

```md
# Regras deste OpenCode

O MCP `motomcp` é a fonte principal de contexto deste projeto.

Importante: este MCP expõe tools, não resources. Não tente usar
`list_mcp_resources` para consultar o `motomcp`.

Antes de responder sobre arquitetura, configuração, instalação, decisões do
projeto, rede, OpenCode, Ollama, busca textual, busca semântica ou segurança,
chame uma destas tools do MCP:

1. `motomcp_get_capabilities` para descobrir as tools disponíveis.
2. `motomcp_search_documents` para procurar texto exato nos documentos.
3. `motomcp_search_semantic` para procurar por sentido/contexto.
4. `motomcp_read_document` para ler o documento encontrado.
5. `motomcp_list_documents` se precisar listar documentos existentes.

Fluxo padrão:

1. Use `motomcp_search_documents` ou `motomcp_search_semantic` com a pergunta
   do usuário.
2. Use `motomcp_read_document` nos arquivos retornados quando precisar de
   contexto completo.
3. Só depois responda ao usuário.

Se houver conflito entre conhecimento geral do modelo e documentos retornados
pelo `moto-mcp`, siga os documentos retornados pelo `moto-mcp`.

Não invente configuração. Se não encontrar a informação usando as tools do
`motomcp`, diga que não encontrou.
```

Depois abra o OpenCode a partir dessa mesma pasta:

```powershell
cd C:\Users\Motoshima\Desktop\OpenCode
opencode --model ollama/qwen3:14b
```

O `AGENTS.md` é carregado automaticamente pelo OpenCode para a sessão daquela
pasta. Se quiser aplicar a mesma regra para todas as pastas do usuário, crie um
`AGENTS.md` global na configuração do OpenCode, mas para este projeto o arquivo
local é mais simples e mais seguro.

