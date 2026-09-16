# Guia — usando o moto_mcp com o OpenCode

Passo a passo pra quem nunca usou nenhuma dessas ferramentas. Sem jargão
desnecessário — só o que você precisa pra ter um assistente de IA no
terminal que conhece o conteúdo deste repositório (regras, knowledge,
agentes, projetos) e consegue ler/editar arquivo junto com você.

## O que você vai escolher antes de começar

Duas decisões, independentes uma da outra:

1. **Onde o "cérebro" (modelo de IA) roda**: no seu computador, de graça
   (Ollama), ou na nuvem, pago (Claude/Anthropic). Pode ter os dois
   configurados e trocar quando quiser — não precisa escolher um pra
   sempre.
2. **Você não precisa decidir nada sobre o `moto_mcp` em si** — ele já
   vem configurado no `opencode.json` deste repositório.

## Passo 1 — instalar o Node.js

O OpenCode roda sobre Node.js. Baixe a versão **LTS** em
<https://nodejs.org> e instale (padrão, next-next-finish).

Confirme que funcionou, abrindo um terminal (PowerShell) e rodando:

```powershell
node --version
npm --version
```

Se aparecer um número de versão nos dois, seguiu certo.

## Passo 2 — instalar o OpenCode

```powershell
npm install -g opencode-ai@1.18.31
```

**Por que a versão fixa (`@1.18.31`) e não `@latest`**: instalar sempre
a última versão sem controle é abrir mão de saber exatamente o que está
rodando na sua máquina — um pacote npm pode mudar de conteúdo entre
versões sem aviso. Fixar a versão é a proteção simples contra isso; sem
custo de manutenção, sem imagem Docker especial. Atualize deliberadamente
(mudando o número aqui) quando quiser, não por padrão.

Confirme:

```powershell
opencode --version
```

## Passo 3 — escolher o cérebro

### Opção A — Ollama (local, de graça, precisa de computador razoável)

1. Baixe e instale o Ollama em <https://ollama.com>.
2. Baixe um modelo com suporte a "tool calling" (chamar ferramentas) —
   é isso que faz ele conseguir usar as tools do `moto_mcp`. Perfis
   testados de ponta a ponta, computador razoável até fraco — tabela
   completa e atualizada em **`docs/guia_maquina_fraca.md`**, não
   repetida aqui pra não desalinhar de novo:
   ```powershell
   ollama pull qwen3:14b
   ```
3. **Suba o Ollama com contexto maior que o padrão** — sem isso, o
   prompt (instruções do OpenCode + as tools nativas + as tools do
   `moto_mcp`) é cortado antes do modelo ver as tools, e nada funciona
   (achado real, não suposição — ver `to-do.md`, continuações 17/18):
   ```powershell
   $env:OLLAMA_CONTEXT_LENGTH = "32768"
   ollama serve
   ```
   (deixa essa janela do terminal aberta rodando; se o Ollama já
   estiver rodando como app/serviço, feche-o antes e suba assim
   manualmente, ou configure a variável de ambiente permanente do
   Windows pra ele sempre subir com esse valor.)

   **Atenção — limite real de hardware, não promessa**: com
   `32768`, o `qwen3:14b` já usa ~95% da VRAM de uma RTX 5070 Ti
   (16GB) — testado e medido, não estimado. Isso funciona pra uma
   pergunta pontual, mas **não tem muita margem pra conversa longa**
   (histórico acumulando turno a turno, resultado grande de alguma
   tool). Se travar/ficar lento com sessão longa, ou baixe pra
   `qwen3:8b` (libera VRAM, um pouco menos preciso), ou use Claude
   (Opção B) pra sessão que precisa de mais contexto.
4. Se o nome do modelo que você baixou for diferente de `qwen3:14b`,
   edite `opencode.json` na raiz deste repositório e troque o nome lá
   (é a chave dentro de `"provider" > "ollama" > "models"`).

### Opção B — Claude/Anthropic (nuvem, pago, sem instalar nada local)

1. Crie uma chave de API em <https://console.anthropic.com>.
2. Guarde essa chave — você vai usar como variável de ambiente no
   próximo passo, nunca digitada dentro de um arquivo do repositório.

## Passo 4 — configurar as variáveis de ambiente

Abra um PowerShell **dentro da pasta do `moto_mcp`** e rode só o que se
aplica à opção que você escolheu no passo 3:

```powershell
cd C:\Users\Pichau\Desktop\Projetos\moto_mcp

# Se escolheu Ollama (Opção A):
$env:MOTO_MCP_OPENCODE_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"

# Se escolheu Claude/Anthropic (Opção B):
$env:ANTHROPIC_API_KEY = "cole a chave aqui"
```

Essas variáveis valem só pra essa janela de terminal aberta. Se fechar e
abrir de novo, precisa rodar de novo (ou configurar como variável de
ambiente permanente do Windows, se preferir não repetir).

## Passo 5 — subir o OpenCode

Ainda na pasta do `moto_mcp`:

```powershell
opencode
```

Isso abre a interface do OpenCode no terminal. Ele já lê o
`opencode.json` do repositório sozinho — não precisa configurar nada a
mais.

## Passo 6 — testar se está tudo funcionando

**Confirme que o `moto_mcp` conectou** (antes mesmo de conversar com o
modelo), num terminal separado:

```powershell
cd C:\Users\Pichau\Desktop\Projetos\moto_mcp
opencode mcp list
```

Esperado: `moto-mcp` com um ✓ e "connected". Se aparecer erro aqui, o
problema é na configuração do `moto_mcp`/Poetry, não no modelo de IA —
ver `docs/mcp_server.md`.

**Escolha o modelo** (dentro do OpenCode, ou direto na linha de
comando — agente padrão do OpenCode, sem restrição nenhuma de
ferramenta):

```powershell
opencode --model ollama/qwen3:14b
# ou, pra usar Claude:
opencode --model anthropic/claude-sonnet-5
```

**Pergunte algo que só o `moto_mcp` sabe responder**, pra confirmar que
o modelo está de fato usando as tools, não só "chutando":

> Quem é o Bill nesse projeto?

Resposta esperada: algo mencionando marketing/posicionamento/conteúdo —
vindo de `agents/bill.md`, que só existe porque o modelo chamou uma tool
do `moto_mcp` (`moto-mcp_list_agents` ou `moto-mcp_read_document` — o
OpenCode prefixa o nome da tool com o nome do servidor MCP) pra ler o
arquivo, não porque ele já sabia disso de antemão. Testado de verdade
com `qwen3:14b`, agente padrão (`build`), **sem desligar nenhuma
ferramenta nativa** — funciona.

Se a resposta vier genérica ou errada, confirme primeiro o Passo 6
(`opencode mcp list`) antes de desconfiar do modelo — e confirme que o
Ollama subiu com `OLLAMA_CONTEXT_LENGTH=32768` (passo 3).
