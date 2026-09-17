# Embeddings e busca semântica

Notas técnicas sobre a busca semântica usada por `search_semantic`.

## Embedding

Um embedding converte texto em um vetor numérico. Textos semanticamente parecidos tendem a gerar vetores próximos.

Vetores de modelos diferentes não devem ser comparados entre si, mesmo quando têm a mesma dimensão. Ao trocar o modelo de embedding, recrie o índice.

## Modelo padrão

O modelo padrão é `bge-m3` via Ollama.

Características úteis:

- roda localmente;
- suporta português;
- gera vetores de 1024 dimensões;
- funciona bem para busca densa multilíngue.

Configuração:

```env
MOTO_MCP_OLLAMA_HOST=http://127.0.0.1:11434
MOTO_MCP_EMBEDDING_MODEL=bge-m3
MOTO_MCP_EMBEDDING_DIMENSIONS=1024
```

Instalação do modelo:

```powershell
ollama pull bge-m3
```

## Chunking

O índice usa seções Markdown como unidade de chunk. Cada seção `##` vira um candidato separado para embedding.

Arquivos sem seções usam o preâmbulo como seção vazia.

## Similaridade

A busca usa similaridade de cosseno. O score deve ser comparado de forma relativa entre os resultados da mesma consulta. Evite usar um corte fixo universal.

## Índice

O LanceDB guarda os vetores em `.vector_index/`.

Reindexar:

```powershell
poetry run python scripts/reindex.py
```

Validar perguntas conhecidas:

```powershell
poetry run python scripts/verify_search.py
```

## Campos de metadata

Cada chunk indexado contém:

- `chunk_id`
- `path`
- `section`
- `category`
- `content_hash`
- `indexed_at`

`content_hash` decide se um chunk precisa ser reprocessado.
