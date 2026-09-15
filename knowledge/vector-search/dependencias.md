# Dependências — busca vetorial (embeddings)

Checklist do que precisa ser instalado, na ordem do plano já decidido (ver
`knowledge/vector-search/embeddings-e-busca-semantica.md`): `bge-m3` local
via Ollama + LanceDB agora; Postgres/`pgvector` como próximo backend a
validar depois, trocando só o adaptador.

## Agora

| O quê | Motivo/utilidade | Como instalar |
|---|---|---|
| Ollama | Runtime que roda o modelo de embedding localmente, sem depender de internet. | https://ollama.com/download/windows |
| Modelo `bge-m3` | Modelo de embedding escolhido — multilíngue, roda local via Ollama, sem custo por chamada. | `ollama pull bge-m3` (depois do Ollama instalado e rodando) |
| Pacote Python `lancedb` | Biblioteca do banco vetorial escolhido — guarda e busca os embeddings, embarcado (sem servidor separado). | `poetry add lancedb` (na raiz do `moto_mcp`, onde já está o `pyproject.toml`) |
| Pacote Python `ollama` | Cliente oficial pra chamar a API local do Ollama a partir do Python — é como o código vai pedir o embedding do `bge-m3`. | `poetry add ollama` |

## Depois — ao trocar para Postgres (`pgvector`)

| O quê | Motivo/utilidade | Como instalar |
|---|---|---|
| Extensão `pgvector` no Postgres já existente | Adiciona um tipo de coluna vetor e busca por similaridade direto em SQL, sem precisar de outro processo. | Sem instalador oficial pronto pra Windows — precisa compilar (Visual Studio Build Tools) ou usar um build pré-compilado da comunidade. Repositório oficial: https://github.com/pgvector/pgvector — build pré-compilado pra Windows: https://github.com/andreiramani/pgvector_pgsql_windows |
| Pacote Python `psycopg[binary]` | Driver pra conectar no Postgres a partir do Python. | `poetry add "psycopg[binary]"` |
| Pacote Python `pgvector` | Adaptador que ensina o driver Python a entender o tipo vetor do Postgres (registra o tipo, converte pra/de lista de floats). | `poetry add pgvector` |

## Verificação obrigatória (não pular)

Antes de considerar LanceDB — ou depois Postgres — "funcionando de
verdade": rodar o conjunto de perguntas com chunk esperado conhecido (ver
`embeddings-e-busca-semantica.md`, seção "Verificação obrigatória") nos dois
backends e confirmar que a busca traz o resultado certo nos dois. Só isso
valida de fato a troca de banco.
