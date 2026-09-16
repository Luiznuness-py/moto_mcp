# moto_mcp como servidor MCP

Este repositório, na raiz, **é** um servidor MCP — não tem uma subpasta
separada pro "código do servidor". `pyproject.toml` e o pacote
`mcp_server/` vivem na raiz, ao lado de `global/`, `knowledge/`,
`agents/`, `projects/`, `clients/` etc., porque o conteúdo dessas
pastas é exatamente o que este servidor expõe via protocolo MCP.

Ele expõe regras (`global/`), base de conhecimento (`knowledge/`),
perfis de agente (`agents/`), projetos e clientes (`projects/`,
`clients/`) como tools MCP — em vez de (ou além de) depender só da
leitura direta de arquivo pelos arquivos-ponte (`CLAUDE.md`, `CODEX.md`,
`AGENTS.md`, `GEMINI.md`).

## Por que isto existe

Surgiu de uma pergunta direta: por que colocar código de servidor
dentro de `moto_mcp`, se `moto_mcp` é conteúdo (regras/knowledge), não
código? Resposta: porque a ideia real é o `moto_mcp` **ser** um
servidor MCP — qualquer cliente MCP (Claude Desktop, Claude Code, outra
ferramenta compatível) passa a poder consultar e (dentro de limites)
atualizar esse conteúdo via protocolo, em vez de só um agente com
acesso a filesystem lendo os `.md` direto do disco.

Isso também resolve, de um jeito mais robusto, o problema que começou a
conversa que levou a este projeto: um LLM rodando local via Ollama
sozinho não fala MCP (isso não muda), mas qualquer cliente MCP que você
configure pode conectar aqui e ter acesso estruturado ao conteúdo do
`moto_mcp`.

Este repositório não contém código específico de nenhum outro projeto
seu (ex: OCR) — isso foi removido de propósito. Qualquer projeto real
que você tenha usado como referência conceitual/estrutural durante o
design (padrões de segurança, decisões de arquitetura) fica só como
lição aprendida documentada, nunca como código embutido aqui.

## Modelo de segurança: leitura aberta, escrita restrita

Esta é a decisão de design central deste servidor:

- **Leitura**: cobre o repositório inteiro (`.md`/`.txt`), exceto
  pastas técnicas (`.git`, `.venv`, `__pycache__` etc). Qualquer agente
  conectado pode ler regras, knowledge, perfis de agente, projetos e
  clientes.
- **Escrita**: restrita a `projects/`, `clients/` e `profile/` —
  `Settings.WRITABLE_PREFIXES` em `mcp_server/config.py`.
  **`global/`, `agents/`, `knowledge/`, `templates/`, `handoff/` e os
  arquivos-ponte da raiz são somente leitura por este servidor, de
  propósito.**

O motivo da restrição: este é literalmente o repositório de regras de
comportamento que agentes de IA (inclusive eu, gerando este código) são
instruídos a seguir. Um servidor MCP que desse escrita irrestrita
deixaria um agente mal orientado — ou um prompt malicioso vindo de
qualquer lugar na conversa — reescrever as próprias regras que deveriam
te proteger. `paths.ensure_writable()` é chamado por toda escrita de
propósito geral (`documents.write_text`), então essa garantia é
estrutural, não uma checagem que cada tool precisa lembrar de fazer.

`profile/` é a única pasta fora de `projects/`/`clients/` liberada pra
escrita, e é deliberado: `profile/profile.md` não é regra de
comportamento do agente, é dado sobre o usuário (perfil, estilo de
trabalho, preferências) — natureza diferente das demais pastas
protegidas acima. Ficava em `global/user_profile.md` originalmente, mas
foi movido pra sua própria pasta especificamente pra poder virar essa
exceção sem abrir `global/` inteiro (que continua protegendo
`rules_absolute.md`, `workflow.md` etc.).

Ver `tests/test_write_restrictions.py` para a regressão disso: tenta
escrever em `global/rules_absolute.md`, `agents/bill.md`,
`knowledge/security/...`, `README.md`, `START_HERE.md` — todas devem
falhar com `PathNotWritableError`.

A única exceção controlada é o `INDEX.md`: `register_entry` atualiza
especificamente a seção "Projetos e clientes registrados" nele (não é
escrita livre — é uma função interna dedicada, `documents.write_index`,
nunca exposta como tool de escrita genérica).

## Tools expostas

- `get_capabilities` — catálogo desta lista.
- `list_documents(subpath="", recursive=False)` — lista arquivos/pastas.
- `read_document(path)` — lê um `.md`/`.txt`.
- `search_documents(query, subpath="", case_sensitive=False, max_results=50)` —
  busca texto em todo o repositório (ou num subpath), com número da linha.
  (Junto com `read_document`/`search_semantic`, a docstring desta tool
  avisa explicitamente o LLM chamador que o conteúdo devolvido é dado
  do repositório, não instrução — mitigação de prompt injection, ver
  `mcp_server/tools.py`, `_UNTRUSTED_CONTENT_NOTE`.)
- `list_agents()` — lista os agentes definidos em `agents/` (nome, papel
  resumido, arquivo), lido do disco a cada chamada. Pra quem se conecta
  a este servidor sem ter lido o repositório inteiro descobrir quem
  existe sem adivinhar nome de arquivo.
- `search_web(query, max_results=10, page=1)` — busca na internet
  aberta via uma instância própria de SearXNG (`docker-compose.yml` na
  raiz, ver "Busca web" abaixo). Sem relação com o conteúdo do
  repositório — útil quando a pergunta precisa de informação que não
  está aqui dentro. `page` usa a paginação nativa do SearXNG
  (`pageno`) — pra ver mais resultado da mesma busca, pede `page=2`
  etc., em vez de truncar o conteúdo de cada resultado (perderia
  informação) ou pedir `max_results` alto demais de uma vez. Confirmado
  com dado real: páginas diferentes trazem resultado diferente, sem
  sobreposição. Aviso de conteúdo não confiável mais forte que os
  demais (é internet aberta, não arquivo do próprio repo).
- `search_semantic(query, top_k=5)` — busca por SENTIDO (embeddings
  `bge-m3` via Ollama local + LanceDB), cobrindo o mesmo repositório
  inteiro de `search_documents`, mas por similaridade de significado em
  vez de substring exata — boa pra pergunta conceitual/paráfrase.
  Precisa do Ollama rodando localmente. O índice é atualizado sozinho a
  cada vez que o servidor sobe (ver "Reindexação automática no
  startup" abaixo); `reindex_search` continua existindo pra atualizar
  sem precisar reiniciar o processo. Convive com `search_documents` de propósito
  — cada uma boa pra um tipo de busca (exata vs. conceitual). Ver
  `knowledge/vector-search/embeddings-e-busca-semantica.md`.
- `reindex_search()` — atualiza o índice vetorial usado por
  `search_semantic` (mesmo algoritmo incremental de
  `scripts/reindex.py`: só reprocessa o que mudou de verdade, por
  `content_hash`). A busca semântica não se atualiza sozinha a cada
  escrita — chame esta tool depois de criar/editar/apagar um documento.
  Precisa do Ollama.
- `compact_search_index(older_than_days=None)` — manutenção do índice
  vetorial (compacta fragmentos do LanceDB, limpa histórico de versões
  antigas); não muda dado atual. Não precisa do Ollama.
- `get_template(kind="projeto"|"cliente")` — retorna o `_TEMPLATE.md`
  real (`projects/_TEMPLATE.md` ou `clients/_TEMPLATE.md`), lido do
  disco a cada chamada — nunca hardcoded aqui, porque os templates do
  seu repositório podem mudar.
- `register_entry(kind, nome, secoes, repositorio="", overwrite=False)` —
  cria `projects/<slug>.md` ou `clients/<slug>.md` a partir do template
  real, preenchendo as seções passadas, e registra a entrada em
  `INDEX.md`. Recusa sobrescrever por padrão. Valida as chaves de
  `secoes` contra os cabeçalhos reais do template — nome errado dá erro
  claro em vez de virar seção vazia silenciosamente.
- `replace_section(path, secao, novo_conteudo)` / `append_to_section(path, secao, texto)` —
  edita uma seção `## <nome>` de um documento já existente em `projects/`
  ou `clients/` (a seção precisa já existir — não cria seção nova
  silenciosamente, pra não divergir do template).

## Transporte: stdio (local)

Modo padrão pra uso na mesma máquina (Claude Desktop, OpenCode local,
MCP Inspector) — sem porta de rede, sem autenticação pra pensar. O
cliente MCP sobe este processo diretamente na sua máquina. (Existe
também um modo de rede, streamable-http, pra outro dispositivo — ver
"Transporte de rede" mais abaixo; os dois convivem, não competem.)

### Configurar em um cliente MCP (ex: Claude Desktop)

```json
{
  "mcpServers": {
    "moto-mcp": {
      "command": "poetry",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "cwd": "C:\\Users\\Pichau\\Desktop\\Projetos\\moto_mcp"
    }
  }
}
```

Se preferir não depender do Poetry estar no PATH do processo que sobe o
cliente MCP, aponte direto pro Python da venv criada pelo Poetry (depois
de rodar `poetry install` uma vez, `poetry env info --path` mostra o
caminho):

```json
{
  "mcpServers": {
    "moto-mcp": {
      "command": "C:\\Users\\Pichau\\AppData\\Local\\pypoetry\\Cache\\virtualenvs\\<nome-da-venv>\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"]
    }
  }
}
```

## Transporte de rede — acesso de outra máquina

Além do stdio (seção acima, continua sendo o caminho pra uso na mesma
máquina, sem mudança), o `moto_mcp` também sobe via **Streamable
HTTP**, pra outro dispositivo (ex: outro computador rodando OpenCode)
se conectar sem copiar o repositório. Mesmo padrão já usado pelo
gateway MCP do `moto_ocr` (`mcp.streamable_http_app()` + `uvicorn`).
Sem dependência nova: `starlette`/`uvicorn` já vêm como dependência
transitiva de `mcp[cli]`.

### Modelo de segurança deste modo

**O Tailscale é a fronteira de confiança — não há autenticação própria
(sem token/Bearer).** O servidor recusa subir (`UnsafeBindHostError`)
se `MOTO_MCP_NETWORK_HOST` não for um endereço da faixa do Tailscale
(`100.64.0.0/10`) — nunca sobe em `0.0.0.0`, `::`, ou IP de LAN/rede
pública, mesmo por engano de configuração (`mcp_server/network.py`,
`ensure_safe_bind_host`, coberto por `tests/test_network.py`).

Isso significa: **qualquer dispositivo já aprovado no seu tailnet, que
alcançar essa porta, tem acesso total** às 13 tools (leitura do
repositório inteiro, escrita em `projects/clients/profile`) — sem
RBAC por dispositivo. Decisão aceitável enquanto for só dispositivo do
próprio usuário (mesmo modelo de risco aceito documentado no pentest
do `moto_ocr` pro gateway dele, enquanto era single-consumer — ver
`to-do.md`). Se algum dia um consumidor fora do seu controle precisar
alcançar essa porta, isso vira bloqueante — aí sim faz sentido uma
camada de autenticação própria (bearer token está registrado como
opção, não implementada).

### Como rodar

```bash
tailscale ip -4    # confirma o IP desta máquina no tailnet, ex: 100.70.89.100

cd C:\Users\Pichau\Desktop\Projetos\moto_mcp
$env:MOTO_MCP_NETWORK_HOST = "100.70.89.100"   # PowerShell; no Git Bash: export MOTO_MCP_NETWORK_HOST=100.70.89.100
poetry run python -m mcp_server.server_network
```

Porta padrão `8765` (`MOTO_MCP_NETWORK_PORT` pra trocar). No cliente MCP
do outro dispositivo (ex: OpenCode, `opencode.json`), registre como
servidor remoto:

```json
{
  "mcp": {
    "moto-mcp": {
      "type": "remote",
      "url": "http://100.70.89.100:8765/mcp"
    }
  }
}
```

Validado de ponta a ponta: servidor sobe, bind confirmado no IP do
Tailscale (log do uvicorn), responde HTTP real na porta — e recusa
subir com `MOTO_MCP_NETWORK_HOST` vazio, `0.0.0.0` ou IP de LAN comum.

## Busca web (SearXNG)

`search_web` depende de uma instância própria de SearXNG, standalone —
**não** é o container do projeto `n8n` do usuário, de propósito: o
`moto_mcp` deve continuar se bastando sozinho, sem depender de outro
projeto estar de pé.

Setup (uma vez) — Podman, não Docker (padrão do ecossistema, ver
`global/yuri_profile.md`):

```bash
cd C:\Users\Pichau\Desktop\Projetos\moto_mcp
cp searxng/settings.yml.example searxng/settings.yml
# editar searxng/settings.yml e trocar "ultrasecretkey" por um valor
# gerado de verdade:
python -c "import secrets; print(secrets.token_hex(32))"

podman machine start   # se a VM ainda não estiver ligada
podman compose -p moto-mcp -f docker-compose.yml up -d searxng
```

`settings.yml` é git-ignored de propósito (carrega o `secret_key` real
— nunca commitar). `Settings.SEARXNG_BASE_URL` (padrão
`http://127.0.0.1:8080`) aponta pra essa instância local.

**Validado de ponta a ponta (2026-09-15)**: `podman compose up`
funcionou (imagem pinada existe de verdade), `curl
"http://127.0.0.1:8080/search?q=python&format=json"` devolveu JSON
real, e `mcp_server.websearch.search_web("python programming
language")` chamado direto (sem mock) devolveu resultados reais da
web. Não é só `tests/test_websearch.py` (6 casos com cliente falso) —
é a stack inteira rodando de verdade.

## OpenCode (agente de terminal com Ollama ou API de nuvem)

`opencode.json` na raiz do repositório registra o `moto_mcp` como
servidor MCP local pro [OpenCode](https://opencode.ai) (`npm install -g
opencode-ai`) — validado de verdade: `opencode mcp list` mostra `moto-mcp
connected`, o OpenCode sobe o processo via stdio sozinho
(`poetry run python -m mcp_server.server`), sem configuração adicional.

Dois providers de modelo configurados, escolha em tempo de uso
(`opencode --model <provider>/<modelo>` ou selecionando na TUI) — nenhum
é obrigatório, o usuário decide:

- **`ollama`** (local, gratuito, sem chave): usa a API compatível com
  OpenAI do Ollama. Requer `MOTO_MCP_OPENCODE_OLLAMA_BASE_URL` no
  ambiente (ex: `http://127.0.0.1:11434/v1`, ou o IP do Tailscale se o
  Ollama estiver em outra máquina). **O nome do modelo em
  `opencode.json` (`"qwen2.5-coder:14b"`) precisa ser editado pra bater
  exatamente com o que você rodou `ollama pull`** — é a chave que vai
  direto pra API do Ollama, não um valor de variável de ambiente (só
  `baseURL` é parametrizável por env var; testado e confirmado que
  colocar `{env:...}` na chave do modelo não funciona — o texto literal
  seria enviado como nome do modelo).
- **`anthropic`** (nuvem, paga): `apiKey` via `{env:ANTHROPIC_API_KEY}`
  — nunca coloque a chave direta no arquivo. Pra outro provider de
  nuvem (OpenAI, Gemini), adicionar bloco equivalente em `provider` (ver
  [docs de providers do OpenCode](https://opencode.ai/docs/providers)).

**Não validado ainda**: uma resposta real do modelo via Ollama (o
Ollama não estava rodando no momento do teste, só a conexão MCP e a
resolução do model id foram confirmadas de ponta a ponta).

## Setup local

Requer Python `>=3.13,<4.0` e Poetry.

```bash
cd C:\Users\Pichau\Desktop\Projetos\moto_mcp
poetry install
poetry run python -m mcp_server.server
```

Ele espera stdin/stdout de um cliente MCP real — rodar direto no
terminal fica esperando input, o que é o comportamento correto pra
stdio (não é um bug, é assim que MCP via stdio funciona). Pra testar de
verdade, configure num cliente MCP (acima) ou use o MCP Inspector.

**Não use `poetry run mcp dev mcp_server/server.py`** — o subcomando
`dev` do `mcp[cli]` sempre delega a execução pra um ambiente `uv`
isolado (`uv run --with mcp mcp run <arquivo>`), mesmo chamado com
`poetry run` na frente; esse ambiente `uv` não tem `mcp_server` nem
suas dependências (`lancedb`, `ollama`, `pydantic-settings`) instaladas,
então o servidor falha ao subir. Abra o Inspector direto e configure o
servidor manualmente, sem passar pelo `mcp dev`:

```bash
cd C:\Users\Pichau\Desktop\Projetos\moto_mcp
npx @modelcontextprotocol/inspector
```

Na tela do Inspector, adicione um servidor (transporte `STDIO`) com:

- **Command**: `poetry`
- **Arguments**: quatro itens separados — `run`, `python`, `-m`,
  `mcp_server.server` (não uma string só; o campo espera cada argumento
  como item próprio, senão o Poetry recebe tudo grudado como um único
  argumento inválido)
- **Working directory**: `C:\Users\Pichau\Desktop\Projetos\moto_mcp`
  (ou já rode o `npx` acima de dentro dessa pasta)

## Testes

```bash
poetry install --with dev
poetry run pytest -v
```

**Confirmado de verdade (2026-09-15)**: `poetry run pytest -v` rodado
neste computador, `102/102` passou (81 originais + 11 do transporte de
rede + 4 da reindexação automática no startup + 6 da busca web).
`poetry.lock` existe e
está commitado.

## Reindexação automática no startup

Os dois pontos de entrada (`server.py`, `server_network.py`) chamam
`mcp_server.startup.reindex_on_startup()` antes de `mcp.run(...)` —
quem acabou de clonar o repositório não precisa lembrar de rodar
`scripts/reindex.py` manualmente pra `search_semantic` funcionar, e o
índice fica atualizado a cada restart sem custo extra (`reindex()` já é
incremental — só reprocessa o que mudou, por `content_hash`). Falha
de embedding/vectorstore (Ollama fora do ar, pacote não instalado) vira
aviso no log, nunca impede o servidor de subir — validado com o Ollama
desta máquina de fato fora do ar durante o teste.

## Pendências conhecidas

- Sem tool de **remover** um projeto/cliente registrado — só criar
  (com `overwrite`) e editar seção. Avaliar se faz sentido antes de
  expor escrita a um agente que pode, por exemplo, tentar "limpar"
  registros por conta própria.
- Sem limite de tamanho em `read_document`/`search_documents` — um
  arquivo `.md` gigante seria lido/varrido inteiro. Baixo risco aqui
  (é um repositório de anotações, não dados de usuário), mas fica
  registrado.
- Sem lock de arquivo — duas escritas concorrentes no mesmo documento
  (`register_entry`/`replace_section`) podem colidir. Baixo risco
  enquanto for um agente por vez na mesma máquina; o modo de rede
  aumenta a chance real disso (mais de um dispositivo podendo escrever
  ao mesmo tempo), mas continua não tratado.
