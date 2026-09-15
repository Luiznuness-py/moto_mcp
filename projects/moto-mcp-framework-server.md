# moto-mcp-framework-server
Repositório: `C:\Users\Pichau\Desktop\Projetos\moto_mcp` (a raiz do próprio repositório — não uma subpasta. `pyproject.toml` e o pacote `mcp_server/` vivem na raiz, ao lado de `global/`, `knowledge/`, `projects/` etc.).

## Papel
Servidor MCP local (stdio) que expõe o conteúdo do próprio repositório
`moto_mcp` — regras (`global/`), base de conhecimento (`knowledge/`),
perfis de agente (`agents/`), projetos e clientes (`projects/`,
`clients/`) — como tools MCP, para qualquer cliente MCP (Claude
Desktop, Claude Code, outras ferramentas compatíveis) consultar e
(dentro de limites) atualizar de forma estruturada, em vez de depender
só da leitura direta de arquivo pelos arquivos-ponte.

**Este repositório não contém, nem deve conter, código específico de
outro projeto** (ex: um gateway de OCR). Uma versão anterior deste
trabalho tinha colocado o gateway MCP de um projeto de OCR (`moto_ocr`)
numa subpasta `server/` aqui dentro — o Yuri removeu essa pasta e
corrigiu o rumo: `moto_ocr` foi só a referência estrutural/conceitual
que motivou o design de segurança deste servidor (ver "Decisões de
arquitetura"), nunca deveria ter virado código embutido neste repo.
Ver `projects/moto-mcp-server.md` para o registro histórico dessa
etapa (marcado como obsoleto).

## Decisões de arquitetura
- **O repositório inteiro é o projeto Python** — sem subpasta pro
  "código do servidor". `pyproject.toml`, `mcp_server/` e
  `tests/` ficam na raiz. Corrigido depois de uma primeira versão que
  colocava tudo dentro de uma subpasta `framework_mcp/`, por analogia
  errada com o gateway do `moto_ocr` (que fazia sentido isolado, porque
  é código de OUTRO projeto).
- **Leitura aberta, escrita restrita**: leitura cobre o repositório
  inteiro (`.md`/`.txt`); escrita só é permitida em `projects/`,
  `clients/` e `profile/` (`Settings.WRITABLE_PREFIXES`). `global/`,
  `agents/`, `knowledge/`, `templates/`, `handoff/` e os arquivos-ponte
  da raiz são somente leitura por este servidor, de propósito — um
  agente conectado não pode reescrever as próprias regras de
  comportamento através dele. Garantido estruturalmente em
  `paths.ensure_writable()`, chamado por toda escrita de propósito
  geral, não checado tool a tool. `profile/` é a exceção: guarda dado
  sobre o usuário (não regra de comportamento do agente), então é
  aceitável que o próprio agente o atualize — movido de
  `global/user_profile.md` pra sua própria pasta exatamente pra
  permitir essa exceção sem abrir `global/` inteiro.
- **Templates lidos do disco em runtime, nunca hardcoded**: `get_template`
  lê `projects/_TEMPLATE.md`/`clients/_TEMPLATE.md` reais a cada
  chamada. Decisão direta de uma lição desta mesma conversa — presumir
  a estrutura de `clients/_TEMPLATE.md` sem checar teria dado errado
  (a estrutura real, com seções "Confirmado/Hipóteses/Decisões/Ativos e
  evidências/Pendências/Próximo passo/Histórico", é bem diferente da de
  `projects/_TEMPLATE.md`).
- **`register_entry` valida as seções passadas contra o template real**
  antes de escrever — uma chave com nome errado dá erro claro em vez de
  silenciosamente virar uma seção vazia.
- **Transporte stdio, não streamable-http**: decisão explícita do Yuri
  — sem porta de rede, sem autenticação pra pensar.

## Stack
Python `>=3.13,<4.0`, Poetry (`package-mode = false`), `mcp[cli]`
(FastMCP, transporte stdio), `pydantic-settings`, `lancedb`, `ollama`.
Testes: `pytest` (`asyncio_mode = "auto"`).

**Atualização (busca semântica, 2026-09-15)**: até aqui este servidor não
fazia nenhuma chamada de rede. Isso deixou de ser 100% verdade com
`mcp_server/embeddings.py` — ele chama o Ollama local (padrão
`http://127.0.0.1:11434`) pra gerar embeddings com `bge-m3`. Continua
offline no sentido que importa (nada sai da máquina, não depende de
internet), mas não é mais "zero rede" no sentido literal. Nos testes
(`tests/test_embeddings.py`) isso é contornado injetando um cliente Ollama
falso (`client=...` no construtor de `OllamaEmbeddingProvider`) — nenhum
teste chama a rede de verdade, real ou local. Ver
`knowledge/vector-search/embeddings-e-busca-semantica.md` e `to-do.md`
para o raciocínio e o plano completo.

**Bug real encontrado testando manualmente (2026-09-15)**: no primeiro
teste de verdade contra o Ollama rodando (fora dos mocks dos testes
automatizados), `provider.embed(...)` falhava com `ConnectionError`
mesmo com o Ollama confirmadamente rodando (`http://localhost:11434`
respondendo "Ollama is running" no navegador). Causa: a variável de
ambiente `OLLAMA_HOST` do sistema estava configurada como
`0.0.0.0:11434` (provavelmente pra permitir que o Ollama aceite conexão
de outros dispositivos na rede) — a biblioteca Python `ollama` usa essa
mesma variável como endereço de DESTINO quando nenhum host é passado
explicitamente, e `0.0.0.0` não é um endereço válido pra um cliente se
conectar, só pra um servidor escutar. Corrigido tornando
`Settings.OLLAMA_HOST` um valor explícito por padrão
(`http://127.0.0.1:11434`, não mais `None`) e fazendo
`OllamaEmbeddingProvider` sempre passar esse valor pro `ollama.Client(...)`
— nunca herdando a variável de ambiente do sistema. Coberto por
`test_default_host_is_explicit_regardless_of_ambient_env`. Lição: esse
tipo de configuração (Ollama exposto na rede local) provavelmente não é
incomum em quem for instalar este servidor no futuro, então o default
explícito é proteção real, não só cosmética.

## Estado atual
Código gerado e revisado manualmente (não em produção, não deployado,
não configurado em nenhum cliente MCP ainda), agora na **raiz** do
repositório:
- `mcp_server/`: `config.py`, `errors.py`, `paths.py`
  (garantia de path safety + restrição de escrita), `documents.py`
  (list/read/write/search/seções), `tools.py` (8 tools), `server.py`,
  `embeddings.py` (contrato `EmbeddingProvider` + adaptador
  `OllamaEmbeddingProvider` pra `bge-m3`), `vectorstore.py` (contrato
  `VectorStore` + adaptador `LanceDBVectorStore` — segunda peça da busca
  semântica, ver `to-do.md`).
- `tests/`: 52 testes cobrindo path traversal, restrição de escrita
  (a regressão central), listagem/leitura/busca, parsing e edição de
  seção markdown, `register_entry` (incluindo os dois templates reais
  e um bug do INDEX.md corrigido — `_register_in_index` perdia o
  próprio cabeçalho da seção ao reconstruir o arquivo, por uso errado
  de `str.partition`), `embeddings.py` (com um cliente Ollama falso
  injetado, sem chamada de rede real) e `vectorstore.py` (esses sim
  contra o LanceDB de verdade, num tmp_path descartável — é embarcado,
  sem rede, então não precisa de mock; `pytest -v tests/test_vectorstore.py`
  já foi confirmado passando os 8/8 originais).

**Confirmado de verdade (2026-09-15)**: `poetry run pytest -v
tests/test_vectorstore.py` rodado na máquina real, 8/8 passou (antes da
adição do `compact`, ver abaixo). Também testado manualmente de ponta a
ponta com `bge-m3` real (`OllamaEmbeddingProvider`) + LanceDB real: textos
sobre arquitetura/stack/capital indexados, busca por "por que a escrita é
restrita a projects e clients" trouxe o chunk de arquitetura em primeiro
(score 0.7960), stack em segundo (0.4523), capital (sem relação) em
último (0.2000) — ordem correta. Nota de calibração registrada em
`knowledge/vector-search/embeddings-e-busca-semantica.md`: mesmo o texto
sem relação nenhuma não chegou perto de 0 — o critério de "funcionou"
deve ser ordem relativa, não um score de corte absoluto.

**`VectorStore.compact()` adicionado (2026-09-15)**: método de manutenção
— no LanceDB, chama `table.optimize()` (compacta fragmentos pequenos,
apaga versões antigas do histórico interno; ver notas sobre
`.lance`/`.manifest`/`.txn` no knowledge doc). Motivado por observação
real: um teste manual criou duas entradas (`autho`/`author`, erro de
digitação corrigido) que ficaram como registros separados no índice —
não é bug, é o comportamento correto de upsert-por-chave, mas expôs a
necessidade de uma forma de limpar/organizar o índice sob demanda. Por
enquanto só existe como método Python (chamável manualmente); virar tool
MCP exposta pro LLM está registrado no `to-do.md`, condicionado à etapa de
integrar a busca vetorial nas tools do servidor (ainda não feita).

**Dois avisos (warnings) corrigidos após rodar `pytest` de verdade
(2026-09-15)**: (1) `mcp_server/vectorstore.py` usava `db.table_names()`
pra checar se a tabela já existe — método obsoleto no LanceDB, e pior,
paginado (10 tabelas por padrão): um repositório com mais de 10 tabelas
faria a checagem dar falso-negativo, tentando recriar uma tabela que já
existia. Trocado por `table_name in db` (`Connection.__contains__`), que
resolve a paginação por baixo corretamente — não é só suprimir o aviso,
é um bug de verdade evitado antes de acontecer. (2) O aviso restante
(`asyncio.get_event_loop_policy` obsoleto) é interno do próprio
`pytest-asyncio`, não do nosso código — filtrado especificamente por
mensagem+módulo em `pyproject.toml` (`[tool.pytest.ini_options]
filterwarnings`), não um "ignore" genérico de `DeprecationWarning`, pra
não esconder avisos de verdade no futuro.
- `README.md` (raiz) ganhou uma seção curta apontando pra
  `docs/mcp_server.md`, que tem os detalhes técnicos completos:
  modelo de segurança, tools, transporte, setup.
- `docs/security_test_master_checklist.md` — checklist do `moto_mcp`
  duplicado e adaptado (superfície de risco real é path
  traversal/escopo de escrita, não rede — transporte é stdio local).

**Removido (2026-09-14)**: `.env.example` e o suporte a arquivo `.env`
em `config.py` — o Yuri questionou se ainda fazia sentido, e não fazia:
não há cenário real onde `MOTO_MCP_REPO_ROOT` precisaria ser
sobrescrito (mover `mcp_server/` pra fora do `moto_mcp` contradiz a
razão de o projeto existir). `MOTO_MCP_REPO_ROOT` como variável de
ambiente direta continua funcionando como válvula de escape, sem a
maquinaria de carregar `.env`.

**Validação**: `python -m py_compile` passa em todos os arquivos,
incluindo `embeddings.py` e `test_embeddings.py`. `pytest` **não foi
executado de fato** — PyPI bloqueado no ambiente onde este código foi
gerado (mesmo pra pacotes já instalados na máquina real, como `ollama`
e `pydantic`). Os testes foram revisados manualmente linha a linha
contra a implementação, mas isso é "smoke + revisão manual", não
"testado" — rodar `poetry run pytest -v` localmente é o que confirma de
verdade.

## Pendências conhecidas
- **P0**: rodar `poetry install --with dev && poetry run pytest` de
  verdade localmente e confirmar os testes passando.
- **P0**: gerar e comitar `poetry.lock`.
- Configurar este servidor num cliente MCP real (Claude Desktop ou
  equivalente) e testar as tools manualmente — nada disso foi exercitado
  de ponta a ponta ainda, só revisado no código.
- P2: sem lock de arquivo — duas escritas concorrentes no mesmo
  documento (`register_entry`/`replace_section`) podem colidir. Baixo
  risco em uso local de um agente por vez, mas não tratado.
- P2: sem tool para **remover** um projeto/cliente registrado — só
  criar (com `overwrite`) e editar seção.
- Decidir se `projects/moto-mcp-server.md` (registro histórico do
  gateway de OCR removido) deve continuar existindo como está marcado
  agora (obsoleto, mantido só como referência) ou se o Yuri prefere que
  eu apague o conteúdo por completo — não consigo deletar o arquivo
  neste momento (ver nota abaixo sobre limitação de ferramenta).
- Nada foi commitado/enviado para o Git do usuário — só escrito no
  repositório local. Commit/push só acontece se o Yuri pedir
  explicitamente (`global/commit_policy.md`).

## Nota operacional (não é sobre o projeto, é sobre esta sessão)
Não consegui excluir arquivos/pastas no dispositivo do Yuri nesta
sessão — a ferramenta de shell remoto está com um bug conhecido do
Windows (update de 8/set bloqueando o acesso). Por isso a antiga pasta
`framework_mcp/` (se ainda existir) e `projects/moto-mcp-server.md`
precisam ser removidos manualmente pelo Yuri, se ele quiser — eu só
consigo sobrescrever/criar arquivo, não apagar.
