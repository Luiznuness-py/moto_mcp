# moto-mcp-server — OBSOLETO, código removido

> **Este projeto foi removido do repositório pelo Yuri em 2026-09-14.**
> A pasta `server/` (o código do gateway) não existe mais aqui. O que
> resta abaixo é registro histórico — o motivo pelo qual isso foi
> construído e a decisão de arquitetura por trás, mantido porque
> influenciou o design do servidor atual (`moto-mcp-framework-server`,
> ver `projects/moto-mcp-framework-server.md`). `moto_ocr` nunca deveria
> ter virado código embutido neste repositório — serviu só como
> referência estrutural/conceitual (o caso real que motivou a revisão
> de segurança que gerou os aprendizados abaixo).
>
> Se preferir apagar este arquivo por completo em vez de mantê-lo como
> histórico, é só excluir — eu não consegui fazer isso automaticamente
> nesta sessão (ferramenta de shell remoto indisponível no momento).

---

Repositório original: `C:\Users\Pichau\Desktop\Projetos\moto_mcp\server` (removido).

## Papel (histórico)
Gateway MCP standalone do MotoOCR (projeto `moto_ocr`, em
`C:\Users\Pichau\Desktop\Projetos\moto_ocr`). Expõe OCR, classificação/
estruturação de documento e administração de vocabulário como tools MCP,
chamando a API REST já existente do `moto_ocr` — não tem acesso direto a
banco, storage nem segredos de aplicação.

Nasceu de uma revisão de segurança (2026-09-14) do gateway MCP embutido
no `moto_ocr` (`mcp_gateway/`), que encontrou:
- **ALTA**: `ocr_document_from_url` / `ocr_document_structured_from_url`
  não checavam scope antes de chamar o upstream.
- **MÉDIA**: o middleware de auth do gateway antigo nunca validava
  `secret_version`, então revogar uma credencial comprometida não
  invalidava tokens já emitidos com o secret anterior.

Relatório completo entregue separadamente ao Yuri.

## Decisões de arquitetura (histórico — influenciaram o servidor atual)
- **Passthrough de auth, não reimplementação**: o gateway capturava o
  header `Authorization` bruto (via `ContextVar`, seguro sob
  concorrência asyncio) e repassava sem modificação em toda chamada ao
  `moto_ocr`. Nunca decriptava o JWE, nunca validava scope, nunca
  decidia RBAC/tenant — tudo isso continuava decidido pelo `moto_ocr`,
  na mesma chamada. O princípio de "garantia estrutural, não checagem
  espalhada" foi reaproveitado no `moto-mcp-framework-server` (lá é
  `paths.ensure_writable()`, aqui era o passthrough de auth).
- **Removida a tool `document_path`** (leitura de arquivo local do
  servidor) que existia no gateway ainda mais antigo do `moto_ocr` —
  fazia sentido lá por rodar embutido no mesmo host da aplicação; num
  serviço desacoplado, seria superfície de ataque nova sem necessidade.
- **Colocação do código (decisão revertida)**: em 2026-09-14, quando
  perguntei onde colocar este gateway, o Yuri respondeu "dentro do
  moto_mcp mesmo" — decisão que foi corrigida depois: `moto_ocr` é um
  projeto próprio, sem relação com o framework genérico do `moto_mcp`,
  e não deveria ter código embutido aqui. O Yuri removeu a pasta
  `server/` e corrigiu o rumo.

## Stack (histórico)
Python `>=3.13,<4.0`, Poetry (`package-mode = false`), `mcp[cli]`
(FastMCP, transporte streamable-http), `httpx`, `pydantic-settings`,
`starlette`/`uvicorn`. Testes: `pytest` (`asyncio_mode = "auto"`),
`respx` para mock de chamadas HTTP upstream.

## Estado atual
**Código removido do repositório.** Nunca chegou a ser testado de
verdade (mesma limitação de PyPI bloqueado no ambiente de geração) nem
deployado.

## Pendências conhecidas
- Decidir com o Yuri o destino do gateway antigo em
  `moto_ocr/mcp_gateway/` (dentro do próprio repositório `moto_ocr`,
  não deste): desligar, ou aplicar o patch pontual do achado ALTA lá.
  Essa decisão nunca foi tomada e continua em aberto — mas agora é
  assunto do repositório `moto_ocr`, não deste.
- Se o gateway do `moto_ocr` for reconstruído no futuro, deve viver no
  próprio repositório `moto_ocr` (ou em um repositório dedicado a ele),
  nunca dentro do `moto_mcp`.
