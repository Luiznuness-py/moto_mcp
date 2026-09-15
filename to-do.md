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
- [ ] **`profile/profile.md` ainda é o template vazio** — Yuri só moveu
  o arquivo, não preencheu. Ofereci rascunhar o preenchimento com base
  no que observei nesta conversa (ciclo incremental, exige verificação
  de gravação por releitura, não aceita "pronto" sem evidência, cobra
  entender o "porquê"); ainda sem resposta.

## Próximos passos (ordem sugerida)
- [ ] Rodar `poetry run python scripts/reindex.py` de novo com o escopo
  corrigido (item pendente da continuação 4, ainda não feito) — o índice
  atual (60 chunks) ainda reflete só knowledge/projects/clients, sem
  `agents/`, `global/` etc.
- [ ] Rodar `poetry run python scripts/verify_search.py` contra o índice
  já reindexado com o escopo novo (13 perguntas agora, incluindo 3 sobre
  `agents/`) — ver seção "Verificação obrigatória" em
  `embeddings-e-busca-semantica.md`. Não seguir pro próximo passo sem
  isso passando.
- [ ] Rodar `poetry run pytest -v` de verdade neste computador —
  confirma `tests/test_indexing.py`, `tests/test_list_agents.py` (e o
  resto da suíte) contra o pytest/LanceDB/Ollama reais, não só o harness
  manual sem pytest usado na sessão na nuvem.
- [ ] Decidir como a busca vetorial se encaixa nas tools existentes do
  `mcp_server` — substitui `search_documents` (substring), ou convivem
  (ex: uma tool nova, `search_semantic`, ao lado da atual)? Incluir nessa
  decisão se/como expor `VectorStore.compact()` como tool também (hoje só
  existe como método Python, chamável manualmente via REPL), e se/como
  expor `reindex()` como tool (rodar reindexação a partir de uma
  conversa, não só via `scripts/reindex.py` na linha de comando).

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

- `poetry run pytest -v` ainda não foi executado de verdade no
  `mcp_server` (ver `projects/moto-mcp-framework-server.md`).
- Execução de comandos neste computador a partir de uma sessão do Claude
  na nuvem (`device_bash`) está quebrada desde uma atualização do
  Windows de 8/set — bug conhecido, já sendo rastreado pela Anthropic
  (a sessão só consegue ler/escrever arquivo por arquivo aqui, não rodar
  comando). Enquanto isso não for corrigido, qualquer coisa que precise
  rodar um comando de verdade aqui (poetry, pytest,
  `scripts/reindex.py`) precisa ser rodada manualmente por quem estiver
  no teclado, não por uma sessão na nuvem.
- `.env.example` ainda não foi deletado do repositório (arquivo órfão,
  sem função depois da simplificação do `config.py`).
- Decidir se `projects/moto-mcp-server.md` (registro obsoleto do gateway de
  OCR) deve ser apagado ou mantido como está.
