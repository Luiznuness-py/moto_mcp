# Embeddings e busca semântica — notas conceituais

Base conceitual sobre busca vetorial/semântica, motivada pela ideia de
melhorar a tool `search_documents` do `mcp_server` (ver
`projects/moto-mcp-framework-server.md`) conforme o conteúdo do repositório
crescer. Nenhum código foi escrito a partir destas notas ainda — é só o
conhecimento necessário pra decidir cada peça antes de implementar.

Requisitos que guiam as decisões aqui:
- Reusável em outros MCPs futuros, não só no `moto_mcp`.
- Precisa funcionar 100% offline.
- Pode ter uma opção via rede (embedding por API), mas só como escolha de quem
  for instalar — nunca como dependência obrigatória.

## 1. O que é um embedding

Um embedding é um texto convertido numa lista de números de tamanho fixo (ex:
1024 números) — um **vetor**, não uma matriz. Esse vetor é um ponto num espaço
de muitas dimensões, e a posição desse ponto representa o *sentido* do texto:
textos com significado parecido caem em pontos geometricamente próximos nesse
espaço, mesmo que não compartilhem nenhuma palavra em comum.

Uma matriz só aparece depois, quando se empilha vários desses vetores juntos
(um por chunk, por exemplo) — isso importa mais pra fase de armazenamento, não
pra definição do que é um embedding em si.

Ponto central: **o número de dimensões não é o que garante que dois vetores
sejam comparáveis — é o modelo que gerou os dois.** Dois modelos diferentes
podem coincidentemente gerar vetores do mesmo tamanho e ainda assim serem
totalmente incompatíveis entre si, porque cada modelo organiza seu próprio
espaço de um jeito diferente durante o treino. Consequência prática direta:
trocar de modelo de embedding no futuro exige reprocessar (reembedar) tudo que
já foi indexado — não dá pra só comparar os vetores antigos com os novos.

## 2. Modelo escolhido: bge-m3

Modelo local (via Ollama), aberto, decidido depois de comparar com a
alternativa de API (`text-embedding-3-small`, da OpenAI):

- **bge-m3**: roda inteiramente local — nenhum texto sai da máquina, o que
  atende o requisito de offline. Sem custo por chamada, custo é só de
  hardware/CPU local. 1024 dimensões, até ~8194 tokens por texto. Multilíngue
  de verdade (mais de 100 idiomas, incluindo português com qualidade boa) —
  motivo principal da escolha, já que o conteúdo do repositório é em
  português. Também suporta busca densa (a vetorial, discutida aqui) e busca
  esparsa (tipo TF-IDF) no mesmo modelo, caso um dia valha combinar os dois
  métodos.
- **text-embedding-3-small** (API, não escolhido como padrão): mais popular no
  mercado geral de embeddings, mas depende de rede (nunca funciona offline) e
  tem custo por token. 1536 dimensões, contexto parecido (~8192 tokens).

Nota de mercado, pra não confundir "melhor" com "mais usado": dentro do
ecossistema Ollama especificamente, `nomic-embed-text` é hoje o mais usado de
longe (85,7M downloads, contra 6,6M do `bge-m3`) — mas isso reflete
principalmente ter sido um dos primeiros embeddings bons e fáceis desse
ecossistema, não necessariamente qualidade superior pro caso de uso daqui.
`bge-m3` foi escolhido apesar de menos popular, pela vantagem concreta em
multilíngue e pelo suporte nativo a busca densa+esparsa.

## 3. Chunking — como dividir o conteúdo antes de embedar

A decisão de como embedar varia de acordo com a densidade do conteúdo:

- Se o conteúdo **não é denso** (um assunto só, curto), tudo bem indexar o
  arquivo/documento por completo, sem dividir.
- Quando **começa a ficar denso** (várias ideias/assuntos diferentes no mesmo
  arquivo), separar por seção/tema ajuda — cada chunk passa a representar uma
  ideia só, em vez de um vetor "médio" borrado de vários assuntos misturados
  (esse problema de misturar assuntos no mesmo vetor é o que motiva dividir).
- Quando uma seção sozinha **fica muito densa** (grande demais pra ainda ser
  "uma ideia só"), usar **overlap**: repetir as últimas frases de um chunk no
  início do próximo, pra não cortar uma ideia no meio e o chunk seguinte não
  ficar sem nenhum contexto do que veio antes.

No caso específico do `mcp_server`, o chunk natural já existe: `## ` (seções
markdown), que `documents.split_sections()` já sabe separar — não precisa
inventar uma unidade de chunking nova, só reusar essa função. Overlap dentro
de uma seção só entraria se, no futuro, alguma seção crescer demais pra ainda
ser "uma ideia só" sozinha (hoje isso ainda não acontece nos arquivos do
repositório).

Chunk pequeno demais também tem custo, não é "sempre melhor": perde o
contexto que dava sentido à frase isolada, multiplica o número de vetores
guardados, e pode fazer a busca trazer vários fragmentos picados que, juntos,
ainda não dão ao LLM o contexto necessário pra responder bem — o que vai
contra o próprio objetivo original de reduzir tokens enviados ao LLM.

## 4. Métricas de similaridade — por que cosseno

Três formas de medir se dois vetores são "parecidos":

- **Distância euclidiana**: a distância em linha reta entre os dois pontos.
  Sensível ao tamanho (magnitude) do vetor, não só à direção. Quando um vetor
  é maior que o outro mesmo apontando pro mesmo sentido, o resultado da
  distância fica maior que o esperado — o tamanho "engana" a medida, mesmo
  quando o significado é parecido.
- **Produto escalar (dot product)**: rápido de calcular, mas tem o mesmo
  problema da distância euclidiana — cresce com o tamanho do vetor, não só
  com a direção.
- **Similaridade de cosseno**: ignora completamente o tamanho, olha só o
  ângulo entre os dois vetores. É o padrão de fato pra embeddings porque
  resolve exatamente o problema das outras duas.

Cosseno vai de -1 a 1: **1 = mesma direção (sentido igual). -1 = sentido
exatamente oposto (direções contrárias, não "mesma direção só que ao
contrário"). 0 = sem relação (perpendiculares).** Na prática, embeddings de
texto real quase nunca chegam perto de -1 — e, confirmado em teste manual
real (`bge-m3` + LanceDB), nem chegam muito perto de 0: um par de frases em
português sem relação nenhuma entre si tende a dar algo em torno de
0.2-0.3, não 0. Frases reais sempre compartilham alguma estrutura de
linguagem. Consequência prática: não faz sentido usar um valor de corte
fixo (tipo "só aceita acima de 0.5") pra decidir se um resultado é
relevante — o que importa é a ORDEM relativa entre os candidatos, não o
valor absoluto do score.

Detalhe de implementação (não precisa ser feito na mão): vetores costumam ser
normalizados (magnitude = 1) antes de guardar, o que faz cosseno equivaler a
um produto escalar simples — mais rápido de calcular em massa. Bancos
vetoriais (Chroma, LanceDB, sqlite-vec) já cuidam disso sozinhos.

## 5. Indexação aproximada (ANN / HNSW)

Problema que motiva o ANN: comparar o vetor da busca contra *todos* os vetores
já indexados (busca exata) funciona bem com poucos vetores, mas o custo cresce
linearmente — em milhões/bilhões de vetores fica lento demais.

**HNSW** (Hierarchical Navigable Small World) é a técnica mais usada hoje.
Uma analogia útil: uma competição de robôs em labirinto, onde o robô tem
sensores mas nenhuma visão de cima e precisa achar a saída rápido. A analogia
fica exata separando em duas fases, como essas competições costumam
funcionar:

- **Construir o mapa do labirinto** (fase de exploração do robô) =
  **indexação**: o HNSW monta, uma vez, uma estrutura em camadas — poucas
  conexões de longa distância nas camadas de cima (pra pular rápido pra
  região certa), mais conexões curtas nas camadas de baixo (pra refinar).
- **Correr o labirinto usando o mapa já pronto** (fase de corrida rápida) =
  **cada busca**: em vez de comparar com todo mundo, o algoritmo salta pela
  estrutura já construída até a vizinhança certa, sem re-explorar do zero.

"Aproximado" no nome vem de existir uma chance pequena de o algoritmo não
achar o vetor teoricamente mais parecido (por ter "saltado" pra vizinhança
levemente errada) — na prática, a perda de precisão é mínima (tipicamente
95-99% de acerto vs busca exata) e compensa muito pela velocidade.

Pro volume de conteúdo do `moto_mcp` hoje (dezenas de arquivos, não milhões),
busca exata já seria rápida o bastante — ANN/HNSW não seria estritamente
necessário aqui. Mesmo assim, vale entender porque: (a) os bancos vetoriais
candidatos já vêm com HNSW embutido por padrão, então ele "vem de fábrica" de
qualquer forma; (b) o objetivo de reusar essa solução em outros MCPs futuros
pode envolver volumes bem maiores, onde isso passa a importar de verdade.

## 6. Reindexação incremental (nota lateral)

Ter algo que reprocesse automaticamente o conteúdo sempre que ele muda faz
sentido — é um problema padrão de todo sistema RAG. A solução não precisa ser
um "agente de IA": um script determinístico (compara data de
modificação/hash de cada arquivo com o que já foi indexado, reembeda só o que
mudou) é mais confiável, rápido e barato que deixar um LLM decidir isso. Um
agente de IA só entraria se algum dia se quisesse uma decisão mais
"inteligente" em cima disso — não é o caso aqui.

## 7. Schema de metadata de cada chunk

`vectorstore.upsert()` já exige `chunk_id` estável e determinístico, e
`metadata` como um dict livre (serializado como `metadata_json` no adaptador
LanceDB — ver `mcp_server/vectorstore.py`). Faltava fixar o que exatamente
entra nesse dict. Decisão:

- **`chunk_id`**: `f"{path}#{section}"` — `path` é o mesmo formato de
  `documents.Entry.path` (relativo à raiz do repo, sempre com `/`), `section`
  é a chave devolvida por `documents.split_sections()` (texto do cabeçalho
  `## `, sem o `## `; string vazia `""` pro preâmbulo antes do primeiro
  cabeçalho). Já é estável e determinístico por construção — não precisa de
  hash nem UUID como chave.
- **`path`** (str): igual ao `chunk_id` sem a seção — repetido dentro da
  metadata (e não só embutido no `chunk_id`) porque `list_indexed()` devolve
  `{chunk_id: metadata}` solto, sem re-parsear a chave; a reindexação
  incremental precisa comparar "quais chunks pertencem a este arquivo" sem
  ter que fazer `chunk_id.rsplit("#", 1)` toda hora.
- **`section`**: idem — mesma razão, guardado solto em vez de só derivado do
  `chunk_id`.
- **`category`** (str): primeiro segmento do `path` (`knowledge`, `projects`,
  `clients`, etc — o mesmo conceito que `paths.ensure_writable()` já usa como
  `top_level`). Permite filtrar por área sem re-parsear o path em toda busca
  (ex: uma tool que só quer buscar dentro de `clients/`).
- **`content_hash`** (str): hash (sha256 hexdigest) do **corpo da seção**
  (o texto que de fato foi embedado) — não hash nem mtime do arquivo inteiro.
  Motivo de ser por chunk e não por arquivo: um arquivo pode ter várias
  seções, e só uma mudar — hash por chunk permite reembedar só a seção que
  mudou, não o arquivo inteiro. Motivo de ser hash de conteúdo e não mtime:
  mtime é enganoso (ex: um `git checkout`/clone pode resetar timestamps sem
  o conteúdo ter mudado, forçando reprocessamento à toa; o inverso também é
  possível). Como `split_sections()` já exige ler o arquivo inteiro mesmo
  (é leitura de disco, não chamada ao Ollama), calcular um hash por seção
  nesse momento é praticamente grátis — o custo caro (embedding) só entra
  quando o hash realmente mudou.
- **`indexed_at`** (str, ISO 8601): timestamp de quando aquele chunk foi
  upsertado pela última vez. Não participa da decisão de reindexar (quem
  decide é `content_hash`) — serve só pra auditoria/debug (ex: "quando essa
  seção foi indexada pela última vez").

Algoritmo de reindexação incremental que este schema viabiliza (fecha o
item "Reindexação incremental" do `to-do.md`):

1. Para cada arquivo relevante (`documents.list_entries(recursive=True)`,
   dentro das pastas que interessa indexar — `knowledge/`, `projects/`,
   `clients/`): `read_text` + `split_sections` -> monta
   `chunk_id -> {path, section, category, content_hash}` do estado atual.
2. Compara contra `store.list_indexed()` (estado já indexado):
   - `chunk_id` novo (não existia) ou `content_hash` diferente do que está
     salvo -> precisa (re)embedar e `upsert`.
   - `chunk_id` que estava indexado mas não existe mais no estado atual
     (arquivo apagado, ou seção removida/renomeada) -> `delete`.
   - `chunk_id` igual com `content_hash` igual -> não faz nada (pula a
     chamada ao Ollama, que é o passo caro).

Implementado em `mcp_server/indexing.py` (`reindex()`) — ver `to-do.md`
pro que já foi testado. Um detalhe real que só apareceu escrevendo os
testes: conteúdo antes do primeiro `## ` vira a seção `""` (preâmbulo),
e isso inclui um `# Título` sozinho, sem mais nada — pra
`split_sections()`, essa linha do título já é "corpo não-vazio" da seção
`""`. Decisão: manter assim (indexar também), sem heurística extra pra
distinguir "preâmbulo com conteúdo de verdade" de "só o título" — a
regra fica simples (corpo vazio não indexa, corpo não-vazio indexa) e o
pior caso é um chunk de baixo valor semântico, não um erro.

## Decisões já tomadas (resumo)

- Modelo de embedding: `bge-m3`, local via Ollama. Sem prefixo de instrução
  na pergunta (diferente das versões antigas da linha BGE, que exigiam um
  texto fixo tipo "Represent this sentence for searching relevant
  passages:") — `bge-m3` foi treinado sem depender disso.
- Chunking: por seção `## ` (reusando `documents.split_sections()`), com
  overlap só se alguma seção específica crescer demais.
- Métrica de similaridade: cosseno (padrão do ecossistema, resolve o
  problema de magnitude da distância euclidiana/produto escalar).
- Banco vetorial: contrato próprio (`upsert`/`delete`/`search`/
  `listar_indexados`) com adaptadores trocáveis — começando por LanceDB,
  com Postgres/`pgvector` como próximo backend a validar via troca de
  adaptador (ver `knowledge/vector-search/dependencias.md` pra lista de
  instalação).
- Provedor de embedding também isolado num contrato próprio (`embedar(texto)
  -> vetor`), separado do contrato do banco.
- Schema de metadata de cada chunk: `chunk_id = f"{path}#{section}"` +
  metadata `{path, section, category, content_hash, indexed_at}` —
  `content_hash` (sha256 do corpo da seção, não do arquivo inteiro) é o que
  decide reindexação incremental (ver seção 7 acima).
- Escopo de indexação: **o repositório inteiro** (`DEFAULT_ROOTS = ("",)`
  em `mcp_server/indexing.py`), não só `knowledge/`+`projects/`+
  `clients/`. Decisão revista depois de um teste manual real (perguntar
  "quem é o Bill" não achava `agents/bill.md`, porque a pasta `agents/`
  nem estava sendo indexada) — a primeira versão tinha copiado sem
  necessidade o raciocínio de `Settings.WRITABLE_PREFIXES` (proteção
  contra ESCRITA por um agente conectado via MCP) pra decidir escopo de
  BUSCA, o que não faz sentido: são preocupações diferentes. `moto_mcp`
  é "base de conhecimento e time de agentes" (README.md) inteiro.

## Verificação obrigatória ao chegar nos bancos

Antes de considerar qualquer backend (LanceDB, e depois Postgres/`pgvector`)
"funcionando de verdade", rodar um conjunto fixo de perguntas com chunk
esperado já conhecido (ex: "por que a escrita é restrita a projects e
clients" -> deveria trazer a seção "Decisões de arquitetura" de
`projects/moto-mcp-framework-server.md`) e confirmar que a busca traz o
resultado certo nos dois backends. Isso é o que valida de fato a troca de
banco (a abstração funcionando), não só "não deu erro" — não pular essa
etapa quando chegar a hora de implementar/testar os bancos.

## Pendências / decisões ainda não tomadas

- Nenhum código de indexação foi escrito ainda a partir destas decisões —
  próxima etapa é a indexação inicial (varrer o repositório, gerar os
  chunks com esse schema, embedar e gravar via `upsert`) — ver `to-do.md`
  na raiz do repositório.
