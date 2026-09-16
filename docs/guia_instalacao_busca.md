# Guia rápido — instalar, configurar e rodar buscas

Para OpenCode + Ollama + MCP remotos, consulte o
[procedimento comprovado em 2026-09-16](diagnostico_opencode_remoto.md)
e o exemplo `opencode/opencode.remote.example.json`. Ele inclui contexto
efetivo do Ollama, diferenças entre V1/V2 e evidências de chamadas reais.

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
    "motomcp": {
      "type": "remote",
      "url": "http://192.168.1.10:8765/mcp",
      "oauth": false,
      "headers": {
        "Authorization": "Bearer {env:MOTO_MCP_AUTH_TOKEN}"
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
- configure `MOTO_MCP_AUTH_TOKEN` no ambiente do processo OpenCode com o
  mesmo Bearer do servidor; não grave o valor real no JSON.

O nome do servidor no exemplo é `motomcp`, sem hífen, para gerar nomes de tools
mais simples para modelos locais. No OpenCode **1.18.31**, `mcp.servers` é
aceito por compatibilidade, mas `codemode` é removido e não muda a exposição
das tools. O exemplo usa o formato nativo V1, com ferramentas diretas.
Para os perfis Ollama com contexto maior testados, use o exemplo remoto
referenciado no início deste guia; a configuração mínima acima só registra
a conexão e os modelos originais.

Para o Ollama do OpenCode, configure uma variável no processo do OpenCode:

```powershell
$env:MOTO_MCP_OPENCODE_OLLAMA_BASE_URL = "http://192.168.1.20:11434/v1"
$segredo = Read-Host 'Bearer token do moto_mcp' -AsSecureString
$env:MOTO_MCP_AUTH_TOKEN = [System.Net.NetworkCredential]::new('', $segredo).Password
Remove-Variable segredo
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
Use motomcp_search_documents para procurar MOTO_MCP_NETWORK_MODE.
```

## 9. Fazer o OpenCode consultar o MCP automaticamente

O `opencode.json` conecta o MCP, mas não obriga sozinho o agente a usar o MCP
como fonte de verdade. No OpenCode **1.18.31** testado aqui, `mcp.motomcp`
é o formato nativo e `mcp.servers` é aceito por compatibilidade; `codemode`
é removido. A V2 tem outro comportamento, conforme sua documentação.
Para orientar o agente, crie um arquivo `AGENTS.md` na mesma pasta
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

## 10. `opencode mcp list` mostra conectado, mas o modelo não chama as tools

Achado real (2026-09-16): `opencode mcp list` conectado só confirma que o
handshake MCP (transporte + auth) funcionou. Não garante que o modelo vai
efetivamente chamar as tools. Verifique, nesta ordem:

1. **Prefixo da tool tem que bater com a chave do servidor.** O OpenCode
   prefixa cada tool com a chave do servidor em `mcp` no `opencode.json`
   (achado documentado em `to-do.md`, continuação 17). Se a chave é
   `motomcp`, as tools chegam ao modelo como `motomcp_get_capabilities`,
   `motomcp_search_documents` etc. Se o `AGENTS.md` da mesma pasta instruir o
   modelo a chamar um prefixo diferente (ex.: `moto-mcp_get_capabilities`,
   com hífen), a instrução aponta para outro nome de ferramenta. **Divergência
   encontrada e corrigida nesta data**: `opencode/AGENTS.md` deste
   repositório citava o prefixo `moto-mcp_` enquanto `opencode/opencode.json`
   registra o servidor como `motomcp` — os dois arquivos precisam usar o
   mesmo prefixo. Confira sempre os dois arquivos juntos antes de assumir
   outra causa.
2. **`OLLAMA_CONTEXT_LENGTH` no Ollama de raciocínio, não no `.env` do
   `moto_mcp`.** Isso é o Ollama que o OpenCode usa pra pensar (ex.:
   `10.80.132.178:11434` no cenário de MCP remoto), não o
   `MOTO_MCP_OLLAMA_HOST` de embeddings deste `.env`. Sem contexto maior que
   o padrão, o prompt (instruções do OpenCode + tools nativas + tools do
   MCP) pode ser truncado. Na comparação atual com 4096 tokens, capabilities
   executou nos três Qwen3, mas a busca falhou nos três; aumentar o contexto
   permitiu executar a mesma busca. Ver as evidências do diagnóstico remoto e
   `docs/guia_maquina_fraca.md` para os valores testados por modelo
   (`qwen3:14b` → `32768`; `qwen3:8b`/`qwen3:4b` → `16384`). Suba o Ollama
   remoto com essa variável setada antes de testar, ou crie perfis separados
   com `PARAMETER num_ctx`, conforme o procedimento remoto testado, sem
   reiniciar o serviço. Confirme `/api/ps`: metadados de contexto no OpenCode
   ou reiniciar só o cliente não aumentam o limite do runtime Ollama.
3. **Teste modelo por modelo.** Suporte a tool-calling estruturado varia por
   modelo — `qwen2.5-coder:14b`, por exemplo, já foi confirmado que não emite
   `tool_calls` neste Ollama (ver `opencode.json` da raiz). Não assuma que
   `qwen3:14b`, `qwen3:8b` e `qwen3:4b` se comportam igual só porque são da
   mesma família.
4. **Diagnóstico direto do OpenCode**, na mesma pasta do `opencode.json`:
   ```bash
   opencode mcp list
   opencode mcp debug motomcp
   ```
   `mcp debug` nessa versão verifica OAuth e encerra com `oauth: false`;
   não é teste de chamada Bearer. Peça o prompt explícito "Use a tool
   motomcp_get_capabilities agora. Não explique. Apenas execute a tool." e
   exija evento `tool_use` concluído com dados reais. Se falhar, verifique
   nomes, configuração efetiva, exposição de tools, permissões, contexto e
   comportamento do modelo; conexão isolada não descarta essas causas.

Não declare o problema resolvido sem repetir o teste do passo 4 depois de
cada mudança — as três causas acima são independentes e podem estar
empilhadas.

