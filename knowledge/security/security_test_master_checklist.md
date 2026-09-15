---
name: security-testing-baseline
description: "Security Test Master Checklist — baseline de DESENVOLVIMENTO (não só teste) para qualquer backend/frontend/gateway/worker/integração. Consolida red team local + práticas de appsec, produto, cloud, supply chain e frontend."
metadata:
  type: reference
---

# Security Test Master Checklist — moto-mcp-framework-server

Cópia própria deste sistema, duplicada de
`knowledge/security/security_testing_baseline.md` no repositório
`moto_mcp` em 2026-09-14, conforme "Como usar em novos projetos" desse
documento (item 1: duplicar, não referenciar um lugar único). A matriz
original está reproduzida abaixo sem alteração; a seção "Adaptação para
este sistema", no fim, é o que muda por projeto.

Objetivo: baseline de validação antes de considerar um backend, frontend, gateway,
worker ou integração pronto para uso real. **É base de DESENVOLVIMENTO, não portão de
teste no fim** — entra no dia 1 de cada sistema novo. Toda construção nova **duplica
este checklist** no próprio `docs/` (cópia própria por sistema, não referência a um
único lugar) e nasce sob este padrão.

Escopo seguro: testes autorizados, ambientes locais/test/staging, sem DDoS, sem brute
force destrutivo, sem alvo externo sem autorização explícita.

## Fontes externas consultadas

OWASP WSTG/ASVS/API Security Top 10/Top 10/Cheat Sheets (Authentication, Session
Management, XSS Prevention, SSRF Prevention), MITRE CWE Top 25/ATT&CK/CAPEC, NIST SP
800-115/SSDF SP 800-218/Cybersecurity Framework 2.0, CIS Controls/Benchmarks, PortSwigger
Web Security Academy, MDN Web Security/HTTP Observatory, Microsoft SDL/Threat Modeling
Tool, OpenSSF Scorecard, SLSA, Kubernetes Security Checklist, Cloud Security Alliance
CCM, PCI SSC, OpenID Connect Core, IETF RFC 9700 OAuth 2.0 Security BCP, GraphQL
Security, GitHub Code Security docs, Docker build/security docs.

## Complementos além do red team local básico

- Threat modeling obrigatório por STRIDE/DFD antes de implementar feature sensível.
- Abuso de negócio: fluxos multi-step, desconto, pagamento, convite, reset, aprovação,
  limite, estado e replay fora da ordem feliz.
- Frontend/browser: DOM XSS, Trusted Types, CSP estrita, SRI, source maps, tokens em
  storage, service worker, cache, clickjacking e XS-Leaks.
- OAuth/OIDC: PKCE, nonce/state, redirect URI exata, mix-up, token leakage, confused
  deputy e validação de claims.
- GraphQL, WebSocket, SSE e streaming: authorization por campo/evento, limite de
  profundidade, custo, introspection e desconexão.
- Supply chain: SBOM, provenance, Scorecard, dependency review, pinning, signed builds,
  secret scanning, branch protection e artifact integrity.
- Cloud/container: rootless/non-root, seccomp/AppArmor, capabilities, read-only FS,
  secrets fora da imagem, network policies, egress allowlist, IAM mínimo.
- Cache/proxy: request smuggling, web cache poisoning/deception, host header,
  hop-by-hop headers, cache de resposta autenticada e vary correto.
- Detecção/resposta: alertas para auth abuse, token replay, SSRF blocked, admin actions,
  secrets detected, 5xx spike e egress anômalo.
- Privacy/compliance: minimização, retenção, export/delete, classificação de dados,
  mascaramento e propósito de coleta.

## Lista consolidada por domínio

Prioridade: **P0** bloqueia release se falhar · **P1** corrigir antes de produção ou
documentar risco aceito · **P2** maturidade, pode ser backlog se não houver exposição.

Domínios (ver checklist completo de referência ao adaptar este template): governança e
critério de aceite; threat modeling e superfície de ataque; configuração/secrets/
ambientes; sanidade/build/CI; autenticação/contas/identidade; sessão/cookies/CSRF/
refresh tokens; autorização/RBAC/tenant/IDOR; contratos de API/validação/robustez;
injection/parsing hostil; dados sensíveis/privacidade/criptografia; frontend/browser
security; HTTP/proxy/cache/headers; SSRF/egress/integrações externas; uploads/arquivos/
conteúdo ativo; business logic/estado/concorrência/replay; logs/auditoria/detecção/
resposta; MCP/agents/LLM/ferramentas; DB/cache/fila/resiliência; container/cloud/runtime
hardening; supply chain/dependência; protocolos especiais (GraphQL/WebSocket/SSE/gRPC).

## Bateria mínima por tipo de projeto

**Backend/API mínimo para qualquer release:** sanidade (check/compile/import/test) →
health público/privado e startup sem dependência → auth (sem/inválido/expirado/
revogado/scope) → RBAC/IDOR (A não acessa B em read/list/write/export/log) → validação
(JSON errado/extra/null/unicode/grande) → injection (SQL/NoSQL/command/template/path/
header/log) → sessão/cookies/CSRF/refresh replay se houver browser login → secrets
(response/log/DB/cache/queue/relatório limpos) → SSRF/egress em toda URL externa/
webhook/provider/parser → concorrência/idempotência nos estados críticos → logs/
auditoria/correlation ID → container/supply chain (lock/advisory/image/secrets/
non-root/healthcheck).

**Frontend mínimo para qualquer release:** DOM XSS em toda entrada renderizada (inclui
querystring/hash/localStorage) → bundle/source map sem segredo/token/endpoint/comentário
→ tokens fora de localStorage quando sensíveis, refresh em cookie HttpOnly → CSP/
frame-ancestors/nosniff/referrer/permissions/HTTPS → CORS/CSRF em browser real → rotas
protegidas no front não substituem enforcement no backend → SRI/CDN/dependency audit →
cache/service worker não guarda resposta autenticada → upload/download UI não permite
tipo ativo perigoso sem tratamento → erros de UI sem stacktrace/segredo/payload raw.

**Deep/periódico:** DAST/manual com proxy → OSV/advisories e scan de imagem → threat
modeling atualizado → race em fluxos de dinheiro/permissão/token/convite/job → request
smuggling/cache poisoning quando houver proxy/CDN → GraphQL/WebSocket/SSE quando
existirem → cloud/IAM/K8s/CIS quando houver deploy cloud → incident response tabletop
(secret leak, token replay, provider compromise).

## Como usar em novos projetos

1. **Duplicar** esta matriz no `docs/` do sistema novo (cópia própria — cada sistema tem
   a sua, é base de desenvolvimento desde o dia 1, não referência a um lugar único).
2. Marcar cada item `Aplicável` / `Não aplicável` / `Backlog`.
3. Todo `P0 Aplicável` precisa de teste automatizado, teste manual registrado ou risco
   aceito por escrito.
4. Todo backend novo recebe ao menos a bateria mínima antes de "pronto".
5. Todo frontend novo recebe a bateria mínima de browser security antes de expor login/
   dados sensíveis/operação autenticada.
6. Para cada achado: evidência, impacto, reprodução, fix sugerido e comando de
   revalidação.

## Checklist curta para PR/review

- Auth/scopes/tenant estão no backend e no repositório?
- Algum dado sensível aparece em response/log/cache/DB/bundle?
- Alguma URL externa/webhook/provider/upload/parser abre SSRF/path risk?
- Algum estado crítico pode sofrer replay/race/idempotency bug?
- Alguma dependência/imagem/action/script novo aumenta supply chain risk?
- Frontend introduziu XSS, storage de token, CSP fraca ou source map sensível?
- Proxy/cache/CORS/cookies mudaram?
- Existe teste ou evidência real, não apenas mock feliz?

---

## Adaptação para este sistema (moto-mcp-framework-server)

Natureza do sistema: servidor MCP local, transporte stdio (sem porta de
rede), sem frontend, sem banco/cache/fila, sem segredo de aplicação. A
superfície de risco real não é "alguém de fora ataca pela rede" — é
"um agente conectado a este servidor consegue ler/escrever algo que não
deveria" (path traversal, escrita fora do escopo pretendido). Isso muda
bastante o que é `Aplicável` aqui vs. o gateway do `moto_ocr`.

| Domínio | Status | Nota |
|---|---|---|
| Governança e critério de aceite | Aplicável | Este documento + README são a evidência do critério. |
| Threat modeling e superfície de ataque | Aplicável | Modelo explícito: a ameaça central é um agente conectado escrevendo fora de `projects/`/`clients/` (em particular, reescrevendo `global/`/`agents/` — suas próprias regras de comportamento) ou lendo/escrevendo fora da raiz do repo via path traversal. Ambos endereçados estruturalmente (`paths.py`), não por checagem espalhada. |
| Configuração/secrets/ambientes | Aplicável | Nenhum segredo de aplicação — `MOTO_MCP_REPO_ROOT` é o único ajuste possível, e não é secreto. |
| Sanidade/build/CI | Parcial | `python -m py_compile` passou em todos os arquivos. `pytest` **não foi executado** neste ambiente de geração (PyPI bloqueado — ver README). Revisão manual linha a linha encontrou e corrigiu um bug real (`_register_in_index` perdendo o cabeçalho do INDEX.md por uso errado de `str.partition`) — evidência de que a revisão manual não é só formalidade. Sem CI configurado. |
| Autenticação/contas/identidade | Não aplicável | Transporte stdio local — quem pode falar com este processo já é quem tem acesso à máquina/ao cliente MCP configurado. Sem rede, sem token, sem sessão. |
| Sessão/cookies/CSRF/refresh tokens | Não aplicável | Idem — sem browser, sem HTTP exposto. |
| Autorização/RBAC/tenant/IDOR | Aplicável (modelo próprio) | Não é RBAC por usuário — é RBAC por **caminho de arquivo**: leitura ampla, escrita restrita a `projects/`+`clients/`, garantida em `paths.ensure_writable()` e testada em `tests/test_write_restrictions.py` (a regressão central deste projeto, análoga ao `test_auth_passthrough.py` do gateway do `moto_ocr`). |
| Contratos de API/validação/robustez | Aplicável | `register_entry` agora valida `kind` e valida as chaves de `secoes` contra os cabeçalhos reais do template (`get_template`), rejeitando com erro claro em vez de silenciosamente ignorar uma seção com nome errado — corrigido durante a própria geração deste projeto (ver "Pendências conhecidas" no README, que documenta a correção). |
| Injection/parsing hostil | Aplicável (path traversal) | O único "parsing hostil" relevante aqui é caminho de arquivo. `paths.resolve_safe_path` bloqueia `..`, caminho absoluto disfarçado e qualquer segmento dentro de pasta ignorada (`.git`, `.venv`), testado em `tests/test_paths_safety.py`. Sem SQL/shell/template — não há esses sinks neste serviço. |
| Dados sensíveis/privacidade/criptografia | Não aplicável | O conteúdo servido (regras, knowledge, projetos) não é dado pessoal nem segredo — é o próprio material de trabalho do repositório, já seria lido por qualquer agente com acesso a filesystem. |
| Frontend/browser security | Não aplicável | Sem frontend. |
| HTTP/proxy/cache/headers | Não aplicável | Sem HTTP — stdio puro. |
| SSRF/egress/integrações externas | Não aplicável | Este servidor não faz nenhuma chamada de rede — só lê/escreve arquivo local. |
| Uploads/arquivos/conteúdo ativo | Aplicável (leitura restrita por extensão) | `READABLE_EXTENSIONS` limita leitura a `.md`/`.txt` — nunca serve binário nem arquivo de config que possa ter segredo, mesmo que tecnicamente dentro do repo. Testado em `test_documents.py::test_read_rejects_non_readable_extension`. |
| Business logic/estado/concorrência/replay | Backlog (P2) | Sem lock de arquivo — duas chamadas concorrentes de `register_entry`/`replace_section` no mesmo arquivo podem colidir (race de escrita). Baixo risco real (uso local, um agente por vez, tipicamente), mas não tratado. Avaliar se vale a pena antes de múltiplos clientes MCP conectarem ao mesmo tempo. |
| Logs/auditoria/detecção/resposta | Backlog (P2) | Nenhum logging de quem leu/escreveu o quê. Como é só leitura/escrita local dentro do próprio repositório de regras (já sob controle de versão do usuário — `git diff`/`git log` já dão auditoria de fato), a prioridade é baixa, mas registrado. |
| MCP/agents/LLM/ferramentas | Aplicável — foco central deste projeto | `tests/test_write_restrictions.py` (nenhuma tool escreve fora do escopo) e `tests/test_register_entry.py` (comportamento correto de `register_entry`, incluindo o bug do INDEX.md corrigido) são a regressão direta do risco que motivou este design: um agente MCP não pode reescrever as regras que deveria seguir. |
| DB/cache/fila/resiliência | Não aplicável | Sem banco, cache ou fila. |
| Container/cloud/runtime hardening | Não aplicável | Não roda em container — é um processo stdio local, subido pelo próprio cliente MCP na máquina do usuário. Sem Dockerfile aqui de propósito. |
| Supply chain/dependência | Backlog | Mesma causa do gateway do `moto_ocr`: `poetry.lock` não gerado neste ambiente (PyPI bloqueado). Gerar localmente (`poetry lock`) antes de considerar pronto. Superfície pequena — só 3 dependências de produção (`mcp`, `pydantic`, `pydantic-settings`). |
| Protocolos especiais (GraphQL/WebSocket/SSE/gRPC) | Não aplicável | Só stdio do MCP. |

### P0/P1 pendentes antes de uso real

1. Rodar a suíte de testes de verdade (`poetry install --with dev && poetry run pytest`)
   e confirmar que todos passam — hoje é revisão manual, não validação.
2. Gerar e comitar `poetry.lock`.
3. Decidir se vale endereçar a race de escrita concorrente (P2, ver tabela) antes de
   conectar mais de um cliente MCP simultâneo a este servidor.

Os demais itens marcados `Backlog` são P2 e podem esperar, mas ficam
registrados aqui — conforme a própria regra do `moto_mcp`: nada
presumido, pendência explícita.
