# Dependências — busca vetorial

## Requisitos atuais

| Item | Uso | Instalação |
|---|---|---|
| Ollama | Runtime local para embeddings | <https://ollama.com/download> |
| `bge-m3` | Modelo de embedding | `ollama pull bge-m3` |
| `lancedb` | Banco vetorial embarcado | já declarado no `pyproject.toml` |
| `ollama` | Cliente Python | já declarado no `pyproject.toml` |

## Verificação

```powershell
poetry install
ollama pull bge-m3
poetry run python scripts/reindex.py
poetry run python scripts/verify_search.py
```
