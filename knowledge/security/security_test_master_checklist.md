# Checklist de segurança

Checklist base para revisar serviços, ferramentas MCP e automações locais.

## Itens gerais

- Autenticação e autorização.
- Escopo mínimo de leitura e escrita.
- Proteção contra path traversal.
- Proteção contra prompt injection em conteúdo retornado por tools.
- Segredos fora do repositório.
- Dependências fixadas e revisadas.
- Logs sem tokens ou dados sensíveis.
- Operações destrutivas com confirmação.
- Testes de regressão para permissões.

## Itens MCP

- Tools de leitura não executam instruções encontradas em documentos.
- Tools de escrita validam caminho e escopo.
- Tools não expõem arquivos ignorados, binários ou segredos.
- Transporte de rede valida host e autenticação antes de iniciar.
- Cliente remoto usa Bearer em modo `lan`.
- `list_mcp_resources` não deve ser tratado como substituto de tools de busca quando o servidor não expõe resources.

## Validação mínima

```powershell
poetry run pytest
poetry run python scripts/verify_search.py
```

Para transporte de rede, validar:

- sem token em `lan`: `401`;
- token inválido: `401`;
- token válido: passa autenticação.
