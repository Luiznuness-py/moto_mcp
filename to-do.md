# To-do — busca vetorial (embeddings)

Plano de execução da funcionalidade de busca semântica discutida em
`knowledge/vector-search/embeddings-e-busca-semantica.md` (conceitos e
decisões) e `knowledge/vector-search/dependencias.md` (o que instalar).
Nada disso existe ainda em código — este arquivo é só a ordem dos próximos
passos.

## Concluído

- [x] Dependências da fase "Agora" instaladas: Ollama, modelo `bge-m3`,
  pacotes Python `lancedb` e `ollama`.
- [x] Contrato do provedor de embedding (`mcp_server/embeddings.py`):
  `EmbeddingProvider` (Protocol) + `OllamaEmbeddingProvider`. **Testado de
  verdade manualmente** (REPL, com Ollama rodando) — funcionando, inclusive
  achou e corrigiu um bug real (`OLLAMA_HOST=0.0.0.0` herdado do sistema
  quebrando a conexão do cliente — ver
  `projects/moto-mcp-framework-server.md`). `poetry run pytest -v
  tests/test_embeddings.py` ainda não confirmado.
- [x] Contrato do banco vetorial (`mcp_server/vectorstore.py`):
  `VectorStore` (Protocol) + `LanceDBVectorStore` — `upsert`, `delete`,
  `search` (métrica de cosseno explícita), `list_indexed`. Schema fixo em
  `Settings.EMBEDDING_DIMENSIONS` (1024, bge-m3). **Testado de verdade**:
  `poetry run pytest -v tests/test_vectorstore.py` — 8/8 passou — e
  confirmado manualmente de ponta a ponta (embed real com `bge-m3` →
  `upsert` no LanceDB → `search` → ordem por similaridade correta:
  "arquitetura" 0.7960, "stack" 0.4523, "capital" 0.2000, pra uma pergunta
  sobre arquitetura). Nota de calibração: mesmo o texto sem relação
  nenhuma não chegou perto de 0 — normal em embeddings de texto real; o
  que importa é a ORDEM relativa, não um score absoluto de corte. Isso
  molda como o conjunto de "verificação obrigatória" (mais abaixo) deve
  ser avaliado: pelo chunk certo aparecer nas primeiras posições, não por
  um threshold fixo de score.
- [x] `VectorStore.compact(older_than_days=None)` — manutenção do índice
  (no LanceDB: `table.optimize()`, compacta fragmentos e limpa versões
  antigas). Motivado por um teste manual real que deixou um registro
  órfão (`autho`/`author`, chunk_id trocado) — não apaga isso sozinho
  (compact não remove chunk_ids "errados", só organiza o histórico
  interno), mas é a peça de manutenção que faltava. Ainda só existe como
  método Python — falta expor como tool MCP (ver item logo abaixo sobre
  integrar nas tools do servidor).

## Concluído (continuação)

- [x] Schema de metadata de cada chunk decidido e documentado em
  `knowledge/vector-search/embeddings-e-busca-semantica.md` (seção 7):
  `chunk_id = f"{path}#{section}"`, metadata
  `{path, section, category, content_hash, indexed_at}` —
  `content_hash` = sha256 do corpo da seção (não do arquivo inteiro), é o
  que decide o que reindexar incrementalmente. Só documentado — nenhum
  código escrito ainda a partir disso.

## Concluído (continuação 2)

- [x] Indexação inicial **e** reindexação incremental escritas como o
  MESMO código (`mcp_server/indexing.py`, função `reindex(store,
  embedder, categories=...)`) — não são dois itens separados de verdade:
  na primeira execução o índice está vazio, então tudo conta como "novo"
  (indexação inicial); nas execuções seguintes só o que mudou de
  `content_hash` é reprocessado (reindexação incremental). Varre
  `knowledge/`, `projects/`, `clients/` por padrão
  (`DEFAULT_CATEGORIES`), reusando `documents.list_entries` +
  `documents.split_sections`; gera embeddings em lote
  (`embed_batch`); grava metadata conforme o schema da seção 7
  (`path`, `section`, `category`, `content_hash`, `indexed_at`); deleta
  do índice os chunks cujo arquivo/seção sumiu. Ponto de entrada de CLI
  em `scripts/reindex.py` (`poetry run python scripts/reindex.py`).
  **Testado de verdade**, mas sem pytest nem LanceDB/Ollama de verdade
  (ambiente onde isto foi escrito não tinha rede pra instalar pacotes —
  mesma limitação já registrada pra `test_vectorstore.py`): escrevi
  `tests/test_indexing.py` (11 casos, usando fakes de embedder e de
  vector store — mesmo espírito de `test_embeddings.py`) e RODEI de
  verdade contra um harness manual sem pytest (arquivos reais em disco,
  sha256 real, só o embedder é fake) — 11/11 passou, incluindo um caso
  que pegou um detalhe real do comportamento: `## ` seguido só de um
  "# Título" antes (sem mais texto) ainda vira um chunk, porque
  `split_sections` considera esse texto do título como corpo não-vazio
  da seção `""` — decidido manter esse comportamento (sem heurística
  extra pra filtrar "título sozinho"), documentado nos dois novos
  testes de preâmbulo. `poetry run pytest -v tests/test_indexing.py`
  ainda não confirmado com pytest de verdade.
- [x] Descoberto e corrigido um problema de processo, não de código:
  esta sessão estava editando uma cópia solta do repositório num sandbox
  na nuvem, desincronizada da cópia real neste computador — os itens
  acima só existiam na cópia da nuvem até serem copiados manualmente pra
  cá. Os arquivos deste `to-do.md` e do doc de embeddings já estavam
  fora de sincronia antes desta correção (a seção 7/schema de metadata,
  decidida numa conversa anterior, só chegou aqui agora).

## Concluído (continuação 3)

- [x] **Índice vetorial real gerado pela primeira vez**, rodando
  `poetry run python scripts/reindex.py` de verdade neste computador
  (Yuri rodou, não a sessão na nuvem — `device_bash` continuou quebrado
  o tempo todo). Resultado: **60 chunks indexados**, 0 removidos, 0 sem
  mudança (primeira execução, índice estava vazio) — bate exatamente
  com o esperado pro conteúdo atual de `knowledge/`, `projects/`,
  `clients/`. Dois problemas reais apareceram e foram corrigidos no
  caminho até aqui, nenhum dos dois era o que a gente pensou de
  primeira:
  1. `ModuleNotFoundError: No module named 'mcp_server'` rodando
     `python scripts/reindex.py` direto — não é o bug antigo do
     `OLLAMA_HOST` (esse já estava neutralizado). Causa: `pyproject.toml`
     tem `package-mode = false` (proposital), então `mcp_server` nunca é
     instalado no venv; rodar um `.py` de dentro de `scripts/` bota a
     pasta do script no `sys.path`, não a raiz do repo. Corrigido com um
     `sys.path.insert` no topo de `scripts/reindex.py` (comentado lá
     mesmo com o raciocínio completo).
  2. Depois disso, `ConnectionError: Failed to connect to Ollama` — essa
     sim parecia o bug antigo à primeira vista, mas não era: o Ollama
     simplesmente não estava rodando no momento (serviço desligado).
     Bastando ligar o Ollama, funcionou de primeira.
- [x] Corrigido (e sincronizado de volta pro computador de verdade,
  desta vez CONFERIDO lendo o arquivo de volta depois de gravar) um
  caso em que uma gravação remota relatou sucesso mas o arquivo não foi
  atualizado de fato (`scripts/reindex.py`, antes da correção do
  `sys.path` pegar) — motivo exato não confirmado (suspeita: mesma
  instabilidade do bug do `device_bash`/Windows), mas o processo de
  "gravar e reler pra confirmar" resolveu e vale manter daqui pra
  frente sempre que uma sessão na nuvem escrever arquivo neste
  computador.

## Concluído (continuação 4)

- [x] **Escopo de indexação corrigido pra o repositório inteiro.**
  Testando manualmente com `scripts/ask.py` (pergunta livre, não só o
  conjunto fixo), "quem é o Bill" e "quem é o Mike" não acharam
  `agents/bill.md`/`agents/mike.md` — não porque a busca estivesse ruim,
  mas porque `agents/` nunca tinha sido indexada: `DEFAULT_CATEGORIES`
  original (`knowledge`, `projects`, `clients`) copiou sem necessidade o
  raciocínio de `Settings.WRITABLE_PREFIXES` (proteção de ESCRITA) pra
  decidir escopo de BUSCA — preocupações diferentes, erro meu. Corrigido
  em `mcp_server/indexing.py`: `DEFAULT_ROOTS = ("",)` agora escaneia o
  repositório inteiro a partir da raiz, reusando
  `documents.list_entries("", recursive=True)` (já pula `.git`,
  `.venv`, `.vector_index` etc. — mesma lógica testada em
  `test_documents.py`). `category` na metadata agora é derivado do
  próprio `entry.path` (primeiro segmento), não da pasta escaneada —
  bate exatamente com a seção 7 do doc de embeddings mesmo pra chunk de
  arquivo solto na raiz (`AGENTS.md`, `README.md`...), que ganha
  `category = "(raiz)"` (`ROOT_CATEGORY`). Acrescentei 3 testes novos em
  `tests/test_indexing.py` cobrindo exatamente isso (pasta antes
  excluída agora entra, arquivo solto na raiz vira `(raiz)`, o próprio
  `.vector_index/` continua fora) — 14/14 no harness manual sem pytest.
  Acrescentei 3 perguntas em `mcp_server/verification_questions.py`
  mirando `agents/bill.md` e `agents/mike.md` (total 13), já que esse
  foi o caso real que expôs o problema.
- [x] `scripts/ask.py` — pergunta manual (linha de comando ou modo
  interativo) contra o índice real, pra explorar/calibrar a busca na
  mão sem precisar de REPL Python. Foi rodando isso que o Yuri achou o
  problema de escopo acima — vale como validação de que a ferramenta já
  está sendo útil.
- [ ] **Rodar `poetry run python scripts/reindex.py` de novo neste
  computador**, agora com o escopo corrigido — o índice atual (60
  chunks) ainda reflete só o escopo antigo (knowledge/projects/clients).
  Precisa reindexar antes do próximo passo (verificação) fazer sentido.

## Concluído (continuação 5)

- [x] **Nova tool `list_agents()`.** Pergunta do Yuri ("faz sentido quem
  usar o MCP ter os agentes pré-instalados?") levou a confirmar: sim,
  `agents/*.md` é conteúdo do próprio repositório, então já está
  disponível via `read_document`/`search_documents`/busca semântica —
  não precisa de tool por agente (sem abstração prematura, mesmo
  princípio de `global/workflow.md`). O que faltava era descoberta: quem
  usa o MCP e não leu o repo inteiro não tem como saber que agentes
  existem sem adivinhar nome de arquivo. `list_agents()` resolve isso —
  lista `agents/*.md` com `nome`/`papel` extraídos da primeira linha
  (convenção `# Nome — Papel`, confirmada nos 7 agentes atuais) e
  `arquivo`. Lido do disco a cada chamada (mesmo padrão de
  `get_template`) — agente novo aparece sozinho, sem tocar em código.
  Registrada em `get_capabilities()` e em `mcp_server/server.py`.
  Testes: `tests/test_list_agents.py` (6 casos — extração nome/papel,
  ordenação, título sem "—", arquivo vazio, `agents/` inexistente,
  `mike.md`/`mike_review.md` como entradas distintas e legítimas).
  Harness manual sem pytest achou um bug real antes de sincronizar pro
  computador: `documents.list_entries("agents")` levanta
  `DocumentNotFoundError` quando a pasta não existe, e a primeira versão
  não tratava isso — corrigido com o mesmo padrão try/except já usado em
  `indexing.py`. 6/6 passando depois da correção. Sincronizado e
  conferido byte-a-byte no computador real: `mcp_server/tools.py` (9371
  bytes), `mcp_server/server.py` (665 bytes), `tests/test_list_agents.py`
  (3210 bytes).

## Concluído (continuação 6)

- [x] **`global/user_profile.md` virou `profile/profile.md` — pasta
  própria, gravável.** Testando a busca semântica com "Mike quem sou
  eu?", o resultado veio todo sobre a identidade do Mike, não do
  usuário — investigando, achei que `global/user_profile.md` existia no
  computador real (não estava na minha cópia na nuvem — mais uma
  divergência já catalogada) mas era só o TEMPLATE vazio, nunca
  preenchido. Separado disso, ficou a pergunta do Yuri: esse arquivo
  deveria ser editável pelo próprio usuário (e pelo agente, via MCP)?
  Hoje não dava — `ensure_writable()` só libera `WRITABLE_PREFIXES`
  (`projects/`, `clients/`), e `global/` é bloqueado de propósito (pra
  um agente conectado não reescrever as próprias regras). Mas o perfil
  do usuário é de natureza diferente de `rules_absolute.md` — não é
  regra de comportamento do agente, é dado sobre o usuário — então faz
  sentido ser gravável. Duas opções discutidas: (A) lista de exceção por
  arquivo único em `paths.py`, ou (B) mover pra pasta própria e
  acrescentar em `WRITABLE_PREFIXES` (granularidade sempre por pasta,
  mesmo padrão já usado). Yuri escolheu (B) e já moveu o arquivo pra
  `profile/profile.md` no computador antes de eu terminar de
  implementar. Ajustado: `WRITABLE_PREFIXES = ["projects", "clients",
  "profile"]` em `config.py` (com o porquê comentado ali mesmo);
  atualizadas todas as menções à lista antiga que eu tinha espalhado
  pelo repo (`docs/mcp_server.md` — "Modelo de segurança",
  `projects/moto-mcp-framework-server.md`, `README.md`, docstrings em
  `mcp_server/documents.py`) — aproveitei e corrigi de passagem uma
  referência errada em `tools.py` que apontava "ver README" pro texto
  que na verdade mora em `docs/mcp_server.md`. `replace_section`/
  `append_to_section` já funcionam em `profile/profile.md` sem precisar
  de tool nova (são genéricas por caminho+seção). Testes novos em
  `tests/test_write_restrictions.py` (escrita e `replace_section`
  permitidos em `profile/`, `global`/`agents` continuam bloqueados) — 5/5
  no harness manual sem pytest. Sincronizado e conferido byte-a-byte nos
  7 arquivos tocados.
- [x] **Decisão: `profile/profile.md` fica vazio de propósito por
  enquanto.** Rascunhei um preenchimento com base no que observei nesta
  conversa (ciclo incremental, exige verificação de gravação por
  releitura, não aceita "pronto" sem evidência, cobra entender o
  "porquê"), separando claramente o que era observado direto do que era
  inferência minha. Yuri decidiu não usar esse rascunho agora — o modelo
  de preenchimento é incremental sob demanda: o próprio usuário edita
  quando quiser, ou pede pro agente atualizar uma seção específica
  durante uma conversa normal (ex: "Mike, anota que eu prefiro X"). Não
  é um preenchimento único de uma vez. Isso já é suportado sem código
  novo — `replace_section`/`append_to_section` já funcionam em
  `profile/profile.md` desde a mudança acima — então não fica nada
  pendente de implementação aqui, só o hábito de usar quando fizer
  sentido na conversa.

## Concluído (continuação 7)

- [x] **Primeira rodada real de `scripts/reindex.py` com escopo cheio,
  confirmada.** Yuri já tinha rodado o reindex com o escopo corrigido em
  algum momento entre sessões (o teste "Mike quem sou eu" já mostrava
  `agents/`/`CODEX.md` nos resultados) — essa rodada só trouxe 4 chunks
  novos/atualizados (os `.md` que eu editei nesta sessão:
  `docs/mcp_server.md`, `projects/moto-mcp-framework-server.md`,
  `README.md`, `to-do.md`), 218 sem mudança, total 222. Confirma que a
  reindexação incremental está funcionando de verdade: só chama o Ollama
  pro que mudou.
- [x] **Primeira rodada real de `scripts/verify_search.py`: 10/13.**
  Analisando as 3 falhas:
  - **Q6** ("de onde vêm as práticas da checklist") — achado real: existia
    `docs/security_test_master_checklist.md`, cópia acidental e
    byte-idêntica de `knowledge/security/security_test_master_checklist.md`,
    diluindo a relevância entre as duas. Investigado: o `docs/` nasceu de
    aplicar errado a convenção de `agents/red.md` ("todo sistema novo
    duplica o checklist no próprio `docs/`") — essa convenção é pra
    projetos novos do framework, não pro `docs/` raiz do próprio
    moto_mcp. Nunca foi de fato adaptado, apesar do changelog anterior
    dizer que foi. Yuri confirmou: remover a duplicata. Feito:
    `projects/moto-mcp-framework-server.md` corrigido pra registrar o
    que aconteceu de verdade; `knowledge/security/security_test_master_checklist.md`
    segue como única fonte. Falta só apagar o arquivo no computador (ver
    "Próximos passos" — não consigo fazer isso remotamente, `device_bash`
    segue bloqueado pelo bug do Windows).
  - **Q13** ("pra qual agente eu direciono dúvida de segurança") — Yuri
    corrigiu o meu entendimento: o gabarito apontava pra
    `agents/mike.md#Direcionamento de especialistas` (a seção que FALA
    SOBRE rotear), mas quem realmente responde "pra qual agente eu vou"
    é o próprio especialista, `agents/red.md#Identidade e papel`. O Mike
    direciona, mas o agente certo é o Red — a busca já acertava isso
    antes, o gabarito é que estava errado. Corrigido em
    `mcp_server/verification_questions.py`, com o raciocínio comentado
    ali mesmo.
  - **Q9** ("antes do servidor atual existir, o que fazia esse papel") —
    fica em aberto por enquanto. Scores bem mais baixos que o normal
    (máx. 0.49 contra 0.55–0.70 nas outras) sugerem limitação genuína de
    busca semântica pra essa pergunta específica, não bug — decidido não
    mexer ainda.
- [x] **`docs/security_test_master_checklist.md` apagado (pelo Yuri, via
  VS Code) e reindexado.** `reindex.py` reportou 8 chunks removidos
  (exatamente as seções daquele arquivo) e 3 novos/atualizados (os .md
  que eu tinha editado). `verify_search.py` rodado de novo: Q13 passou
  (gabarito corrigido), mas **Q6 continuou falhando** — minha hipótese de
  que a duplicata era a causa raiz estava incompleta. Investigando o
  conteúdo real da seção esperada
  (`knowledge/security/security_test_master_checklist.md#Fontes externas
  consultadas`), o problema é outro: a seção é só uma lista crua de
  siglas/nomes próprios (OWASP, MITRE, NIST, CIS...), sem frase em
  linguagem natural — pouco "gancho" semântico pro embedding conectar com
  uma pergunta conceitual tipo "de onde vêm as práticas". Mesma
  categoria de limitação da Q9, só que aqui deu pra apontar a causa
  exata. Yuri pediu pra melhorar o texto do arquivo (não pra aceitar
  como limitação) — acrescentei uma frase de introdução em linguagem
  natural antes da lista, sem tirar/mudar nenhuma fonte:
  "As práticas, prioridades e itens deste checklist não foram inventados
  do zero — vêm da consolidação dos seguintes padrões, guias e
  frameworks de segurança reconhecidos pela indústria...". Aplicado nos
  DOIS arquivos — `knowledge/security/security_test_master_checklist.md`
  E `knowledge/security/security_testing_baseline.md` (o canônico, do
  qual todo projeto novo duplica) — pra não reintroduzir o mesmo
  problema em duplicações futuras. Sincronizado e conferido byte-a-byte.
  Ainda falta rodar `reindex.py`/`verify_search.py` de novo pra confirmar
  se a mudança resolveu a Q6 de fato (hipótese, não comprovado ainda).

- [x] **Q6 confirmada resolvida: 12/13.** Rodado `reindex.py` (4
  chunks novos/atualizados: as duas seções "Fontes externas
  consultadas" editadas, mais dois chunks do próprio `to-do.md`; 0
  removidos) e `verify_search.py` de novo — Q6 saiu de "fora do top-8"
  pra **#1 com score 0.6607**. Confirma a hipótese: a frase de
  introdução em linguagem natural foi suficiente, sem mudar nenhuma
  fonte da lista.
- [x] **Mesma técnica aplicada na Q9.** Olhando o conteúdo real de
  `projects/moto-mcp-server.md#Papel (histórico)` (não é lista crua como
  a Q6 — tem texto corrido), achei o mesmo tipo de lacuna: a seção
  mergulha direto nos detalhes técnicos ("Gateway MCP standalone do
  MotoOCR...") sem nunca dizer explicitamente "antes do servidor atual
  existir, este era o papel" — essa relação temporal só existia no
  título do arquivo e no aviso do topo (chunks diferentes, não a seção
  "Papel" em si). Acrescentei uma frase de abertura equivalente:
  "Antes do servidor atual (`moto-mcp-framework-server`) existir, era
  este projeto que ocupava esse papel no repositório: ...". Sincronizado
  e conferido byte-a-byte (4209 bytes). Ainda falta rodar
  `reindex.py`/`verify_search.py` de novo pra confirmar se resolveu —
  se der certo, é 13/13.

- [x] **`poetry run pytest -v` rodado de verdade: 74/74 passou.**
  Yuri decidiu não esperar a confirmação do 13/13 da Q9 antes de seguir
  ("vamos entender melhor no dia a dia") — a fase de reindex/verify_search
  fica encerrada aqui, com a correção da Q9 aplicada mas sua confirmação
  final adiada pro uso real em vez de mais uma rodada de teste fixo.
  74/74 confirma contra pytest/LanceDB/Ollama reais (não só o harness
  manual sem pytest usado na sessão na nuvem) que `test_indexing.py`,
  `test_list_agents.py` e `test_write_restrictions.py` — os três
  escritos só com harness manual até agora — realmente passam no
  ambiente de verdade. Achado no output: um novo warning de depreciação
  (`'asyncio.set_event_loop_policy' is deprecated`) irmão do que já era
  filtrado (`'asyncio.get_event_loop_policy'`) em `pyproject.toml` —
  mesma causa (interno do `pytest-asyncio`, não é código nosso).
  Perguntei ao Yuri se quer que eu adicione ao filtro também; resposta
  ainda pendente.

## Próximos passos (ordem sugerida)
- [ ] (Opcional) Decidir se adiciona o filtro do warning
  `'asyncio.set_event_loop_policy' is deprecated` em
  `[tool.pytest.ini_options] filterwarnings` do `pyproject.toml`, mesmo
  padrão do filtro já existente.
- [x] **Confirmado: a correção da Q9 chegou a 13/13.** Rodado
  `scripts/verify_search.py` de novo nesta sessão (2026-09-15, como
  parte da validação do fix do `sys.path`/`package-mode`) —
  `13/13 perguntas encontraram o chunk certo no top-8`. Ficou pendente
  desde a continuação 7; sem essa confirmação explícita aqui, o item
  ficava marcado como aberto mesmo já resolvido.
- [x] **Decidido e implementado: busca vetorial virou 3 tools novas no
  `mcp_server`.** Perguntei ao Yuri as três sub-decisões que ficaram em
  aberto desde a continuação 4/5, e a resposta pra todas foi "sim,
  fazer":
  1. `search_semantic(query, top_k=5)` — nova tool ao lado de
     `search_documents` (substring), não substituindo — cada uma boa pra
     um tipo de busca (exata vs. conceitual/paráfrase).
  2. `reindex_search()` — expõe `indexing.reindex()` como tool, pra um
     agente conectado disparar reindexação direto de uma conversa (não
     só via `scripts/reindex.py` na linha de comando).
  3. `compact_search_index(older_than_days=None)` — expõe
     `VectorStore.compact()` também (essa era a opção NÃO recomendada
     que eu tinha sugerido manter manual, mas o Yuri preferiu expor).
  Implementado em `mcp_server/tools.py`: as três tools são "fininhas" de
  propósito — cada uma delega pra uma função `_..._impl()` privada
  testável com fakes (store/embedder reais só são instanciados dentro
  da tool pública, nunca como parâmetro exposto no schema MCP — senão
  vazaria detalhe de injeção de dependência pro cliente). `search_semantic`
  não escreve nada (só lê o índice); `reindex_search`/`compact_search_index`
  tocam o índice vetorial (dado gerado em `Settings.VECTOR_DB_PATH`), não
  arquivo do repositório — por isso não passam por
  `paths.ensure_writable()`/`WRITABLE_PREFIXES`, é escopo diferente.
  Registradas em `server.py` e em `get_capabilities()` (com uma nota
  indicando quais precisam do Ollama rodando: `search_semantic` e
  `reindex_search` sim, `compact_search_index` não, já que só mexe no
  LanceDB). De quebra, achei e corrigi um gap: `list_agents` nunca tinha
  sido adicionada em `docs/mcp_server.md` ("Tools expostas") — corrigido
  junto.
  Testes novos: `tests/test_search_tools.py` (7 casos — formatação de
  resultado achatada, embed+top_k repassados corretamente, índice vazio
  não é erro, mapeamento completo de `IndexingReport` pro dict de
  retorno, `compact` delega `older_than_days` e confirma) — todos com
  fakes, sem precisar de LanceDB/Ollama de verdade (mesma filosofia de
  `test_indexing.py`). 7/7 no harness manual sem pytest. Confirmado
  também que `mcp_server/tools.py` e `mcp_server/server.py` importam
  limpo no sandbox da nuvem (o pacote `mcp` está disponível aqui,
  então até validei que o `FastMCP` aceita as assinaturas das 3 tools
  novas sem erro, não só a lógica isolada). Sincronizado e conferido
  byte-a-byte em todos os arquivos tocados
  (`tools.py`/`server.py`/`docs/mcp_server.md`/`tests/test_search_tools.py`).

- [x] **`poetry run pytest -v` confirmado: 81/81 passou** (os 74 de
  antes + os 7 novos de `tests/test_search_tools.py`, todos verdes
  contra pytest/LanceDB/Ollama reais). Nenhuma regressão nas tools
  existentes. Fecha o ciclo desta rodada de trabalho: RAG completo
  (repositório como fonte → chunking/embedding bge-m3 via Ollama →
  LanceDB → 12 tools MCP, substring e semântica lado a lado) com
  cobertura de teste real de ponta a ponta.
- [x] **Verificação independente de que registro e documentação batem
  de verdade** — não só relendo o código, perguntei direto pro objeto
  `FastMCP` (`server.mcp.list_tools()`) quais tools ele tem registradas
  e comparei com `get_capabilities()`. Bateu 1:1 nas 12 tools (a única
  "diferença" é `get_capabilities` não se autolistar no próprio
  catálogo, o que é esperado, não bug). Confirma que `search_semantic`/
  `reindex_search`/`compact_search_index` estão de fato disponíveis
  pra qualquer cliente MCP conectado, não só declaradas no código.

## Concluído (continuação 9)

- [x] **Bug real achado testando `poetry run mcp dev mcp_server/server.py`
  (MCP Inspector): `ModuleNotFoundError: No module named 'mcp_server'`.**
  Mesmo sintoma do bug antigo de `scripts/reindex.py`, causa diferente:
  `mcp dev` carrega `server.py` direto pelo CAMINHO do arquivo via
  `importlib` (`mcp/cli/cli.py:_import_server`), não via `python -m` —
  isso não bota nem o cwd nem a pasta do arquivo no `sys.path`. Como
  `python -m mcp_server.server` (usado no `claude_desktop_config.json`)
  já funcionava só porque o `-m` bota o cwd no `sys.path` sozinho,
  ninguém tinha notado que `server.py` não sobrevivia a ser carregado de
  outro jeito. Corrigido com o mesmo remendo já usado em
  `scripts/reindex.py`: `sys.path.insert` da raiz do repo no topo de
  `server.py`, antes do `from mcp_server import tools`. Verificado de
  duas formas antes de sincronizar: (1) simulei o mecanismo exato do
  `mcp dev` (`importlib.util.spec_from_file_location` + `exec_module`)
  rodando de `/tmp` — carregou limpo; (2) rodei `python -m
  mcp_server.server` de novo pra confirmar que o caminho que já
  funcionava continua funcionando (sem regressão). Sincronizado e
  conferido byte-a-byte (1869 bytes).

## Concluído (continuação 10)

- [x] **Causa raiz do `ModuleNotFoundError` eliminada — não só contornada.**
  O remendo da continuação 9 (`sys.path.insert` em `server.py`) resolvia o
  sintoma, não a causa: `package-mode = false` no `pyproject.toml` impedia
  o Poetry de instalar `mcp_server` no venv, então qualquer forma de
  carregar o arquivo que não passasse pelo `sys.path` manual quebrava.
  Corrigido de vez: `package-mode = false` removido, `packages =
  [{include = "mcp_server"}]` adicionado, `poetry install` agora instala
  `mcp_server` em modo editável. Com isso, `sys.path.insert` foi removido
  dos 4 arquivos que tinham o remendo (`server.py`,
  `scripts/reindex.py`, `scripts/ask.py`, `scripts/verify_search.py`).
  Validado nos três mecanismos de carregamento que motivaram o remendo
  original: `pytest` (81/81), `python -m mcp_server.server`, carregamento
  por caminho via `importlib` (mesmo mecanismo do `mcp dev`/MCP
  Inspector) — e os três scripts rodados diretos
  (`poetry run python scripts/reindex.py` etc., sem `-m`). Bônus:
  `verify_search.py` deu **13/13** nessa rodada (a Q9, em aberto desde a
  continuação 7, também passou).
- [x] **Comentários/docstrings do código revisados pra tirar referência
  pessoal.** `mcp_server/config.py`, `mcp_server/server.py` e
  `mcp_server/verification_questions.py` tinham trechos endereçando
  alguém diretamente ("você precisaria...") ou atribuindo uma correção a
  uma pessoa específica no meio da explicação técnica. Reescrito pra
  manter o raciocínio técnico e tirar a referência pessoal — escopo
  limitado a `.py` (`mcp_server/`, `scripts/`, `tests/`); os `.md` de
  changelog/histórico (este arquivo, `projects/*.md`) continuam
  registrando decisão com autor, como já documentado em
  `global/workflow.md`. `81/81` confirmado depois da mudança.
- [x] **Achado e corrigido: `poetry run mcp dev mcp_server/server.py`
  (recomendado em `docs/mcp_server.md` pra testar no MCP Inspector) não
  funciona de verdade.** O subcomando `dev` do `mcp[cli]` sempre delega
  a execução pra um ambiente `uv` isolado (`uv run --with mcp mcp run
  <arquivo>`), ignorando o venv do Poetry mesmo chamado com `poetry run`
  na frente — esse ambiente `uv` não tem `mcp_server` nem `lancedb`/
  `ollama`/`pydantic-settings` instalados, então o servidor falha ao
  subir (confirmado testando: status "Failed" no Inspector). Corrigido
  em `docs/mcp_server.md`: instrução trocada por abrir o Inspector direto
  (`npx @modelcontextprotocol/inspector`) e configurar o servidor na mão
  (`Command: poetry`, `Arguments`: `run`/`python`/`-m`/`mcp_server.server`
  como itens separados — o campo não aceita a string inteira de uma vez,
  isso já pegou um usuário real). Testado de ponta a ponta: servidor
  conecta e responde no Inspector com esse caminho.

## Concluído (continuação 11)

- [x] **Prompt injection — mitigação mínima implementada.** Escolhida a
  opção de aviso explícito (não a estrutural): `read_document`,
  `search_documents` e `search_semantic` ganharam um trecho fixo
  (`_UNTRUSTED_CONTENT_NOTE` em `mcp_server/tools.py`) anexado à
  docstring, marcando o retorno como dado do repositório, nunca
  instrução a obedecer. `get_capabilities` também referencia o aviso.
  Escolha justificada por ser o menor pedaço correto: não muda o
  formato de retorno (sem risco de quebrar quem já consome essas
  tools), só marca a intenção pro LLM chamador. `92/92` testes
  passando depois da mudança (não é teste automatizado de resistência a
  injeção de verdade — isso exigiria um LLM de fato tentando obedecer,
  fora do escopo de teste unitário; fica como limite conhecido).
- [x] **Transporte de rede (streamable-http) implementado e testado de
  ponta a ponta.** Novo módulo `mcp_server/network.py`
  (`ensure_safe_bind_host`) — garantia estrutural, mesma filosofia de
  `paths.ensure_writable`: recusa subir (`UnsafeBindHostError`) se o
  host não for um endereço da faixa do Tailscale (`100.64.0.0/10`),
  cobrindo vazio, `0.0.0.0`, `::`, IP de LAN comum e IP público — 11
  casos novos em `tests/test_network.py`. Novo ponto de entrada
  `mcp_server/server_network.py` (`python -m
  mcp_server.server_network`), reaproveita o mesmo `mcp` de
  `server.py` (mesmas 12 tools, sem duplicar registro), sobe com
  `mcp.run(transport="streamable-http")`. `Settings.NETWORK_HOST`/
  `NETWORK_PORT` novos em `config.py`, sem default de host de
  propósito (força configuração explícita). Validado com Tailscale
  real rodando nesta máquina: subiu bindado no IP real do tailnet
  (confirmado no log do uvicorn), respondeu HTTP real na porta
  (`406` num GET simples — esperado, é o handshake do streamable-http
  rejeitando requisição fora do protocolo, não "conexão recusada"), e
  recusou subir com host vazio/`0.0.0.0`/IP de LAN comum. `92/92`
  testes passando.
  **Decisão de autenticação seguida**: Tailscale como única fronteira
  de confiança, sem token/auth própria — a proposta que estava em
  aberto, adotada por autorização de seguir em frente ("pode fazer
  todas"), não por confirmação item a item. Registrado explicitamente
  em `docs/mcp_server.md`, "Modelo de segurança deste modo", incluindo
  a condição que tornaria isso insuficiente.
- [x] `docs/mcp_server.md` e `README.md` atualizados com o modo de rede
  real (não mais "planejado") — como rodar, exemplo de config remota
  pro OpenCode, modelo de segurança explícito.
- [x] **Evidência cruzada de `moto_ocr`/`moto_rules` (repositórios
  privados próprios, já em produção e com pentest/red team documentado)
  que apoia a decisão de autenticação acima**: o pentest do `moto_ocr`
  (`reviews/pentest-findings-2026-07-02.md`, achado #4) encontrou 3
  furos reais no MCP gateway dele — sem checagem de scope por tool, sem
  isolamento multi-tenant em duas tools, leitura arbitrária de arquivo
  local via uma tool (`document_path`). Aceito como risco baixo só
  porque o gateway era single-consumer, com pré-requisito bloqueante
  registrado: fechar os 3 antes de liberar acesso a um segundo
  consumidor. `moto_rules` incorporou a lição desde o início
  (`docs/security_audit/README.md`: "MCP: mesma autorização das rotas
  REST"). Aplicando ao `moto_mcp`: o furo de leitura arbitrária de
  arquivo já não existe aqui (`paths.py` confina tudo à raiz do repo,
  só `.md`/`.txt`) — mais restrito do que o `moto_ocr` estava antes do
  pentest dele nesse ponto específico. O furo que mapeia de verdade é
  "sem scope": o `moto_mcp` também é tudo-ou-nada. Mesma regra de risco
  aceito aplicada aqui — Tailscale como fronteira, sem scope, enquanto
  for só dispositivo do próprio Yuri.

## Concluído (continuação 12)

- [x] **`opencode.json` na raiz — OpenCode registrado como cliente MCP
  do `moto_mcp`.** Validado de verdade, não só escrito: `opencode mcp
  list` mostrou `moto-mcp` como `connected`, subindo o processo sozinho
  via stdio. Dois providers de modelo configurados (usuário escolhe em
  tempo de uso, nenhum obrigatório): `ollama` (local, `@ai-sdk/openai-
  compatible`, `baseURL` via `MOTO_MCP_OPENCODE_OLLAMA_BASE_URL`) e
  `anthropic` (nuvem, `apiKey` via `{env:ANTHROPIC_API_KEY}`). Bug real
  encontrado e corrigido testando: a chave do modelo dentro de
  `provider.ollama.models` é o que vai literal pra API do Ollama — não
  dá pra parametrizar por env var ali (só o campo `name`, que é só
  label, foi testado com `{env:...}` e o valor NÃO era resolvido pro
  id real enviado à API). Corrigido fixando a chave
  (`"qwen2.5-coder:14b"`) com instrução no guia pra editar manualmente
  se o modelo baixado for outro. **Não validado**: uma resposta real de
  inferência via Ollama (Ollama não estava rodando no momento do
  teste) — só a conexão MCP e a resolução do model id foram
  confirmadas de ponta a ponta (`opencode models` mostrou
  `ollama/qwen2.5-coder:14b` corretamente).
- [x] **`docs/guia_opencode.md` criado** — passo a passo em linguagem
  simples pra usuário de baixo conhecimento técnico: instalar Node,
  instalar OpenCode com versão fixada (`opencode-ai@1.18.31`, não
  `@latest` — mitigação prática contra risco de supply-chain do npm,
  mais barata que uma imagem Docker customizada), escolher entre Ollama
  local ou Claude/Anthropic na nuvem, configurar variável de ambiente,
  subir, e testar com um exemplo concreto (perguntar "quem é o Bill" e
  confirmar que a resposta vem de `agents/bill.md` via tool call, não
  de conhecimento prévio do modelo). `README.md` linkado pro guia.

## Concluído (continuação 13)

- [x] **Reindexação automática no startup.** Quem clona o repositório e
  sobe o servidor pela primeira vez tinha `search_semantic` vazio até
  lembrar de rodar `scripts/reindex.py` manualmente — e desatualizado
  de novo depois de qualquer edição, pelo mesmo motivo. Novo
  `mcp_server/startup.py` (`reindex_on_startup`), chamado no início de
  `server.py` e `server_network.py`, antes de `mcp.run(...)`. Barato de
  chamar toda vez porque `reindex()` já é incremental (só reprocessa o
  que mudou, por `content_hash`). Falha de embedding/vectorstore nunca
  impede o servidor de subir — vira aviso no log, não exceção (as
  outras 11 tools não dependem do Ollama). Testado nos dois sentidos:
  4 casos novos em `tests/test_startup.py` (fakes, sucesso e as duas
  falhas) e teste real de verdade com o Ollama desta máquina
  efetivamente fora do ar — `python -m mcp_server.server` imprimiu o
  aviso e subiu normalmente, não travou. `96/96` testes passando.

## Concluído (continuação 14)

- [x] **Tool `search_web` — busca na internet aberta via SearXNG.**
  Decisão: instância própria (standalone), não o container do projeto
  `n8n` do usuário — o `n8n` não expõe porta pro host (só alcançável na
  rede Docker isolada `n8n-local`), e acoplar o `moto_mcp` a outro
  projeto pessoal contradiz o objetivo de ser portátil (qualquer um
  clona e usa). `docker-compose.yml` na raiz (imagem
  `searxng/searxng:2026.9.12-d4f00d15d` — mesma versão já validada
  rodando no `n8n`, não uma tag chutada), `searxng/settings.yml.example`
  (`use_default_settings: true` + `search.formats` incluindo `json`,
  obrigatório pra API funcionar — SearXNG recusa `format=json` por
  padrão) e `.gitignore` cobrindo `searxng/settings.yml` real (carrega
  `secret_key` gerado, nunca commitado). Novo `mcp_server/websearch.py`
  — função simples (`httpx.get`), sem Protocol/adapter como
  embeddings/vectorstore têm: não existe plano de trocar de motor de
  busca web, construir essa abstração agora seria prematuro. Aviso de
  conteúdo não confiável **mais forte** que o das outras tools
  (`_UNTRUSTED_WEB_CONTENT_NOTE` em `tools.py`) — conteúdo vem de
  qualquer página da internet, superfície de prompt injection maior que
  arquivo do próprio repositório. `tests/test_websearch.py` (6 casos,
  cliente httpx falso injetado — mesmo padrão de
  `OllamaEmbeddingProvider`). `102/102` testes passando.
  **Correção de rumo na mesma sessão**: primeira tentativa de validar
  usou `docker`/`docker.exe`, que não existe nesta máquina — erro
  meu, ignorando a regra já documentada em `global/yuri_profile.md`
  ("Podman, nunca Docker puro") e uma pista que eu já tinha lido e não
  conectei (`n8n/config/searxng.env` tem `container=podman`
  literalmente escrito nele). Corrigido: `podman`/`podman machine` já
  instalados e a VM rodando nesta máquina. **Validado de ponta a
  ponta de verdade**: `podman compose -p moto-mcp -f docker-compose.yml
  up -d searxng` subiu o container (imagem pinada existe, não é tag
  chutada), `curl` no endpoint real devolveu JSON, e
  `mcp_server.websearch.search_web(...)` chamado sem mock nenhum
  devolveu resultado real da web (`python.org` etc.). Comentários/docs
  corrigidos de "docker compose" pra "podman compose -p moto-mcp -f
  docker-compose.yml" em todos os arquivos tocados
  (`docker-compose.yml`, `searxng/settings.yml.example`,
  `mcp_server/websearch.py`, `docs/mcp_server.md`) — nome do arquivo
  continua `docker-compose.yml` de propósito (é só o formato,
  compatível; mesma convenção já usada em `moto_ocr`/`moto_rules`).

## Concluído (continuação 15)

- [x] **`search_web` ganhou paginação (`page`) em vez de truncar
  conteúdo.** Testando com dado real, o campo `content` de cada
  resultado já vem sem HTML (confirmado com 135 resultados reais de 4
  buscas diferentes — `format=json` do SearXNG já entrega texto puro,
  não precisa sanitizar nada do lado do `moto_mcp`), mas o risco
  levantado foi resultado individual grande demais pro contexto do LLM.
  Truncar perderia informação; paginar não. `pageno` é parâmetro nativo
  do SearXNG — `mcp_server/websearch.py`/`tools.py` só repassam
  `page` pra ele. Confirmado com dado real (não só teste com fake):
  página 1 e página 2 da mesma busca trazem resultado **totalmente
  diferente**, zero sobreposição, testado com a tool de verdade contra
  o container rodando. 1 teste novo em `tests/test_websearch.py`
  (`page` repassado como `pageno`). `103/103` testes passando.

## Concluído (continuação 16)

- [x] **Causa raiz #1 confirmada e corrigida: `qwen2.5-coder:14b` não
  emite `tool_calls` estruturado neste Ollama.** Testado direto na API
  do Ollama (`/v1/chat/completions` e `/api/chat`), comparando lado a
  lado com `qwen3:14b` na mesma chamada exata: `qwen2.5-coder:14b`
  sempre devolve `tool_calls: None` (a intenção de chamada vaza como
  texto no `content`); `qwen3:14b` devolve `tool_calls` estruturado
  corretamente, reproduzido várias vezes, inclusive com um conjunto de
  10 tools realista (o tamanho real do `moto-mcp`). `opencode.json`
  corrigido: `qwen3:14b` é o modelo declarado pra tool-calling;
  `qwen2.5-coder:14b` continua no arquivo, documentado como "não usa
  tool-calling neste Ollama — só pra código sem tool".
- [x] **Causa raiz #2 identificada, não é bug do `moto_mcp`: o problema
  restante é do OpenCode, não do modelo/Ollama.** Com `qwen3:14b`
  dentro do OpenCode, pedindo pra listar as tools MCP disponíveis, o
  modelo reporta uma lista que **nem inclui** as 13 tools do
  `moto-mcp` — só tools nativas do OpenCode. Isolado o suficiente pra
  descartar Ollama/modelo como causa (testes diretos na API confirmam
  que funcionam com até 10 tools reais). O volume de tools + system
  prompt que o OpenCode monta é maior que o testado isoladamente, e o
  modelo local quantizado (`qwen3:14b`, Q4) não dá conta de raciocinar
  certo sobre isso em modo `opencode run` (execução única). Não é algo
  corrigível no `moto_mcp` — é limitação real de modelo local pequeno
  com agente pesado, já citada como risco antes de virar fato
  observado. Fica registrado como limitação conhecida, não bug aberto.

## Concluído (continuação 17)

- [x] **OpenCode + Ollama local + moto-mcp funcionando de ponta a
  ponta, de verdade, confirmado com resposta real.** Três causas raiz
  precisaram ser corrigidas juntas (a #1/#2 já registradas na
  continuação 16 não eram suficientes sozinhas):
  1. Modelo certo: `qwen3:14b` (não `qwen2.5-coder:14b`).
  2. **`OLLAMA_CONTEXT_LENGTH=16384`** ao subir o Ollama (`ollama
     serve`) — sem isso, o prompt (system prompt do OpenCode + tools)
     estourava o contexto padrão e era truncado antes do modelo ver as
     tools do `moto-mcp` (achado real, visto no log:
     `"truncating input prompt" limit=2050 prompt=9040`).
  3. **Agente customizado `moto`** em `opencode.json` (`"agent":
     {"moto": {...}}`) — desliga tools nativas do OpenCode que não
     precisamos (`bash`, `edit`, `write`, `task`, `todowrite`,
     `webfetch`, `glob`, `grep`), reduzindo o tamanho do prompt e a
     concorrência de opções pro modelo.
  Achado extra relevante: as tools MCP aparecem pro modelo com o nome
  **prefixado pelo servidor** (`moto-mcp_list_agents`, não
  `list_agents` puro) — explica por que pedidos anteriores usando o
  nome sem prefixo confundiam o modelo.
  Teste real (`opencode run --agent moto --model ollama/qwen3:14b`,
  pedindo pra chamar `list_agents`): chamou `moto-mcp_list_agents` de
  verdade, trouxe os 7 agentes reais do repositório (Bill, Fred, Homes,
  Levi, Mike, Mike Review, Red) com papel e arquivo corretos. Sem
  truncamento em nenhuma das 3 chamadas do teste (`truncated = 0`).

## Concluído (continuação 18) — correção da continuação 17

- [x] **O agente `moto` (continuação 17) foi um erro de julgamento,
  corrigido.** Apontado pelo Yuri: desligar 8 ferramentas nativas do
  OpenCode (`bash`, `edit`, `write`, `task`, `todowrite`, `webfetch`,
  `glob`, `grep`) fez UM teste específico passar, mas removeu
  funcionalidade real (o agente `moto` não conseguia editar arquivo
  nem rodar shell) e não provava que o problema estava resolvido —
  só que funcionava com capacidade cortada.
  **Reteste real, com o agente `build` completo (nada desligado)** +
  `OLLAMA_CONTEXT_LENGTH=32768` (subido de 16384, que já tinha pouca
  margem): funcionou igual, chamou `moto-mcp_list_agents`, trouxe os 7
  agentes corretos, **sem cortar nenhuma tool nativa**. Prompt real
  medido: 9195–9758 tokens, `truncated = 0`. Prova que o agente `moto`
  nunca foi necessário — o problema sempre foi só tamanho de contexto.
  **Removido `"agent": {"moto": {...}}` do `opencode.json`** — volta a
  usar o agente padrão do OpenCode, sem restrição.
  **Limite real de hardware registrado, não escondido**: `32768` de
  contexto usa ~15.473 MiB dos 16.303 MiB de VRAM da RTX 5070 Ti (95%,
  medido com `nvidia-smi`, não estimado). Não tem margem pra crescer
  mais nesse hardware — conversa longa/multi-turno ainda pode esbarrar
  no mesmo teto de truncamento. Não é "resolvido pra sempre", é
  "funciona pra pergunta pontual, com pouca folga". Alternativas
  registradas, não implementadas: `qwen3:8b` (libera VRAM), cache de
  contexto quantizado (`OLLAMA_KV_CACHE_TYPE`), ou usar nuvem (Claude)
  pra sessão que precisa de mais contexto.
  `docs/guia_opencode.md` e `docs/mcp_server.md` atualizados pra
  refletir isso — sem `--agent moto`, `OLLAMA_CONTEXT_LENGTH=32768`,
  aviso explícito sobre a margem apertada de VRAM.

## Concluído (continuação 19) — backlog de 8 itens (ecossistema leve/pessoal)

- [x] **Modo LAN oficial, sem exigir Tailscale.**
  `Settings.NETWORK_MODE` (`tailscale`/`lan`/`local`) +
  `mcp_server/network.py` reescrito pra validar a fronteira certa por
  modo. `tailscale` continua igual (só faixa `100.64.0.0/10`); `lan`
  aceita `10.0.0.0/8`/`172.16.0.0/12`/`192.168.0.0/16`/
  `169.254.0.0/16`; `local` só `127.0.0.1`/`::1`. `0.0.0.0`/`::` nunca
  aceito em nenhum modo. Testado de verdade em modo `lan` (bind real
  no IP da LAN, resposta HTTP confirmada).
- [x] **Token Bearer obrigatório em modo LAN.** Novo
  `mcp_server/auth.py` (`BearerTokenMiddleware`, comparação de tempo
  constante) — montado em `server_network.py` só quando
  `MOTO_MCP_AUTH_TOKEN` está configurado; `ensure_safe_bind_host`
  recusa subir em modo `lan` sem token (fail-closed). Testado de
  ponta a ponta: sem token → `401`, token errado → `401`, token certo
  → passa da autenticação. `tests/test_auth.py` (3 casos).
- [x] **Perfis de modelo/contexto documentados com dado real**, não
  estimativa — `docs/guia_maquina_fraca.md` novo. `qwen3:4b`/`qwen3:8b`
  (contexto `16384`) e `qwen3:14b` (contexto `32768`, ressalva de VRAM)
  confirmados de ponta a ponta dentro do OpenCode real.
  `qwen2.5-coder:14b` e `mistral-nemo:12b` testados e reprovados
  (registrados pra ninguém perder tempo tentando de novo). Perfil
  "forte" (30B+) fica como futuro, não testado.
- [x] **`scripts/test_tool_calling.py`** — testa se um modelo do
  Ollama faz tool-calling estruturado de verdade (mesmo conjunto
  representativo de 10 tools usado nos testes manuais desta sessão).
  Validado reproduzindo os dois resultados já conhecidos: `qwen3:4b`
  passa, `qwen2.5-coder:14b` falha com o mesmo vazamento de JSON que
  já tínhamos visto manualmente. Aviso explícito no próprio script:
  passar aqui não garante funcionar dentro do OpenCode de verdade
  (`mistral-nemo:12b` é o exemplo real disso — não foi testado
  isolado antes de existir este script, mas seria um caso de alerta
  pra não confiar cegamente no resultado isolado).
- [x] **`docs/guia_maquina_fraca.md`** cobre também os itens 5 e 6 do
  backlog: como perceber contexto insuficiente (sinais reais
  observados nesta sessão — tool "não disponível", resposta vazia,
  tool inventada sem o indicador `⚙` de execução real), quando evitar
  OpenCode pesado (modelo gratuito de nuvem via OpenCode, ou uso sem
  agente nenhum via `scripts/ask.py`), e deploy persistente simples
  (`nohup`/`disown` em terminal, sem systemd/Podman — decisão explícita
  do Yuri de manter simples).
- [x] **`projects/moto-mcp-framework-server.md` atualizado** — a
  decisão antiga "stdio, não streamable-http" estava desatualizada
  desde a continuação 11; corrigida pra refletir os três modos atuais.
  Pendências resolvidas (pytest, poetry.lock, teste com cliente MCP
  real) tiradas da lista de pendências.
- [x] **Ajustes de consistência**: "12 tools" → "13 tools" nos
  comentários de `mcp_server/server.py`/`server_network.py`. `README.md`
  menciona os três modos de rede, não só Tailscale.
  `128/128` testes passando depois de tudo.

## Concluído (continuação 20) — correções de revisão externa

Achados de uma revisão (não desta sessão) sobre a continuação 19,
todos corrigidos e testados:

- [x] **P1 — `uvicorn`/`starlette`/`httpx` declarados direto no
  `pyproject.toml`**, não só transitivos via `mcp[cli]`. Piso de
  versão igual ao que `mcp[cli]` já exige hoje (`poetry show`), não
  inventado. `poetry lock` regenerado — sem mudança de versão
  resolvida (já estavam nesses valores via transitiva), só passaram a
  aparecer como dependência direta.
- [x] **P2 — token de LAN com piso mínimo de tamanho.**
  `ensure_safe_bind_host` recusa `MOTO_MCP_AUTH_TOKEN` com menos de 32
  caracteres em modo `lan` (constante `_MIN_TOKEN_LENGTH` em
  `mcp_server/network.py`) — não é força de senha de verdade
  (entropia/dicionário), só trava erro bobo tipo `AUTH_TOKEN=1`. 5
  testes novos (`tests/test_network.py`).
- [x] **P2 — contradição entre `guia_maquina_fraca.md` e
  `guia_opencode.md` sobre `qwen3:8b` corrigida.** `guia_opencode.md`
  não repete mais a tabela de perfis — aponta pra
  `docs/guia_maquina_fraca.md` como única fonte, evitando desalinhar
  de novo no futuro.
- [x] **P2 — `opencode.json` atualizado** com os perfis confirmados
  (`qwen3:4b`, `qwen3:8b`) declarados no provider `ollama`, não só
  `qwen3:14b`. Validado com `opencode models` — os 4 aparecem
  corretamente.
- [x] **P3 — descrição do `pyproject.toml` corrigida**: não fala mais
  só "via Tailscale", menciona os três modos.
  `133/133` testes passando.

## Próximos passos (ordem sugerida)
- [ ] Testar `search_semantic`/`reindex_search`/`compact_search_index` de
  verdade, conectado num cliente MCP de verdade (ex: Claude Desktop,
  não só via script/harness) — falta essa última confirmação de ponta a
  ponta, com um agente de fato chamando essas tools numa conversa.
- [x] **Conectividade de rede com dispositivo físico real, confirmada
  (teste temporário fora do modelo de segurança).** Subido um processo
  avulso (fora do repositório, sem tocar `network.py`) bindado no IP
  da LAN (`192.168.15.19:8765`, não o do Tailscale) + regra temporária
  de firewall (`New-NetFirewallRule`, removida depois). Celular na
  mesma Wi-Fi acessou `http://192.168.15.19:8765/mcp` no navegador e
  recebeu resposta JSON-RPC real do servidor (erro `-32600` esperado —
  GET de navegador não completa o handshake streamable-http, mesma
  classe de resposta que o `curl` já tinha mostrado antes; um cliente
  MCP de verdade completaria a sessão normalmente). Prova que o
  transporte de rede funciona ponta a ponta com dispositivo físico
  real, não só localmente. **Isso não substitui nem valida o modo de
  produção** (Tailscale-only, `ensure_safe_bind_host` intacto) — foi
  deliberadamente um bypass temporário só pra este teste, revertido
  depois (processo derrubado, regra de firewall removida, nenhum
  arquivo do repositório alterado).
- [ ] Ainda falta: testar o modo de rede com um **cliente MCP de
  verdade** (não navegador) de outro dispositivo — o teste acima prova
  conectividade de rede, não uma sessão MCP completa.

## Concluído (continuação 21) — segunda rodada de correções de revisão

- [x] **P2 — exemplo de `curl` do `docs/guia_maquina_fraca.md` estava
  errado pro modo `lan`.** Mandava testar sem header `Authorization` e
  dizia que `406` = "está de pé" — em modo `lan` (token obrigatório),
  **testado de verdade agora**: sem header dá `401` (autenticação
  funcionando, não é falha), só com o header certo chega no `406`
  esperado. Corrigido o guia pra separar os dois casos (tailscale/local
  sem token vs. lan com token) e explicar que `401` sem header é sinal
  de que a auth está funcionando, não de que o servidor caiu.
- [x] **P2 — `scripts/test_tool_calling.py` dizia "mesmo conjunto real
  do moto_mcp" na mensagem impressa**, contradizendo o aviso logo no
  topo do próprio arquivo ("subconjunto representativo"). Corrigido
  pra "subconjunto representativo", consistente com o aviso.
- [x] **P3 — docstring de `UnsafeBindHostError` desatualizada**
  (ainda falava só de Tailscale) — corrigida pra descrever os três
  modos e a checagem de token.
- [x] **P3 — `docs/mcp_server.md` dizia "sem dependência nova"** pra
  `starlette`/`uvicorn`, desatualizado desde que passaram a ser
  declarados diretos no `pyproject.toml` (continuação 20). Corrigido.
- [x] **P3 — promessa de "zero custo" do `opencode/big-pickle`
  suavizada** — agora deixa explícito que é serviço de terceiro,
  gratuito "no momento em que isto foi escrito", não garantia
  permanente; orienta confirmar disponibilidade antes de montar fluxo
  que dependa disso.
  `133/133` testes passando.

## Concluído (continuação 22) — achado real do Yuri numa máquina de verdade

- [x] **Primeiro teste real de verdade em outro computador** (clone do
  GitHub, usuário Windows diferente, `moto_mcp` nunca configurado
  antes) — e ele achou um problema real que eu não tinha testado: rodar
  `poetry run python -m mcp_server.server_network` sem nenhuma variável
  de ambiente configurada (cenário exato de quem acabou de clonar)
  devolvia um **stack trace cru do Python**, não uma mensagem
  compreensível. A lógica em si estava certa (o servidor deve mesmo
  recusar subir sem host — isso já era testado), mas eu nunca tinha
  testado a **experiência real** de rodar o comando do zero, sem nada
  pré-configurado — só testei com as variáveis já setadas nas minhas
  sessões. Falha real de cobertura de teste, não de lógica.
  **Corrigido**: `server_network.py` agora captura
  `UnsafeBindHostError` no ponto de entrada e imprime uma mensagem
  limpa de uma linha + `sys.exit(1)`, em vez de deixar o traceback
  vazar. Testado de verdade: reproduzi o erro original (mesmo
  traceback), apliquei a correção, reproduzi nos dois casos (host
  vazio e modo `lan` sem token) confirmando saída limpa.
  `tests/test_server_network_cli.py` novo — sobe o processo de verdade
  via `subprocess` (não mock), exatamente como um usuário rodaria, e
  confirma ausência de "Traceback" na saída. `135/135` testes passando.

## Depois — troca de backend (validação da abstração)

- [ ] Instalar `pgvector` no Postgres já existente + pacotes Python
  `psycopg[binary]` e `pgvector` (ver `dependencias.md`).
- [ ] Implementar o adaptador Postgres/`pgvector` pro mesmo contrato do
  banco vetorial (sem tocar no resto do código — chunking, embedding,
  tools).
- [ ] Rodar de novo o mesmo conjunto de perguntas de verificação contra o
  backend Postgres e confirmar que os resultados batem com os do LanceDB.
  Isso é o que prova que a abstração funcionou.

## Pendências herdadas (não relacionadas a este plano)

- Execução de comandos neste computador a partir de uma sessão do Claude
  na nuvem (`device_bash`) está quebrada desde uma atualização do
  Windows de 8/set — bug conhecido, já sendo rastreado pela Anthropic
  (a sessão só consegue ler/escrever arquivo por arquivo aqui, não rodar
  comando). Enquanto isso não for corrigido, qualquer coisa que precise
  rodar um comando de verdade aqui (poetry, pytest,
  `scripts/reindex.py`) precisa ser rodada manualmente por quem estiver
  no teclado, não por uma sessão na nuvem.
- Decidir se `projects/moto-mcp-server.md` (registro obsoleto do gateway de
  OCR) deve ser apagado ou mantido como está.
