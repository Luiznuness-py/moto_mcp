# Dependências — busca vetorial

## Requisitos atuais

| Item | Uso | Instalação |
|---|---|---|
| Ollama | Runtime local para embeddings | <https://ollama.com/download> |
| `bge-m3` | Modelo de embedding | `ollama pull bge-m3` |
| `lancedb` | Banco preferencial, isolado em processo auxiliar | declarado no `pyproject.toml`; lock atual 0.38.0 |
| SQLite (`sqlite3`) | Banco local; busca por cosseno em Python | incluído no Python, sem extensão vetorial |
| `ollama` | Cliente Python | já declarado no `pyproject.toml` |

## Verificação

```powershell
poetry install
ollama pull bge-m3
poetry run python scripts/reindex.py
poetry run python scripts/verify_search.py
```

LanceDB é carregado somente no processo auxiliar. Se faltar o pacote, ocorrer erro Python, falha nativa (incluindo SIGILL) ou timeout de 30 segundos, a sessão usa SQLite e registra o motivo em stderr. Não é necessário instalar extensões SQLite. O espelho SQLite é atualizado antes de cada gravação LanceDB. Veja `docs/fallback_lancedb_sqlite.md`.
