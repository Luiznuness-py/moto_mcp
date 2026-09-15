# moto_mcp como servidor MCP

Este repositório, na raiz, **é** um servidor MCP — não tem uma subpasta
separada pro "código do servidor". `pyproject.toml` e o pacote
`mcp_server/` vivem na raiz, ao lado de `global/`, `knowledge/`,
`agents/`, `projects/`, `clients/` etc., porque o conteúdo dessas
pastas é exatamente o que este servidor expõe via protocolo MCP.

Ele expõe regras (`global/`), base de conhecimento (`knowledge/`),
perfis de agente (`agents/`), projetos e clientes (`projects/`,
`clients/`) como tools MCP — em vez de (ou além de) depender só da
leitura direta de arquivo pelos arquivos-ponte (`CLAUDE.md`, `CODEX.md`,
`AGENTS.md`, `GEMINI.md`).

## Por que isto existe

Surgiu de uma pergunta direta: por que colocar código de servidor
dentro de `moto_mcp`, se `moto_mcp` é conteúdo (regras/knowledge), não
código? Resposta: porque a ideia real é o `moto_mcp` **ser** um
servidor MCP — qualquer cliente MCP (Claude Desktop, Claude Code, outra
ferramenta compatível) passa a poder consultar e (dentro de limites)
atualizar esse conteúdo via protocolo, em vez de só um agente com
acesso a filesystem lendo os `.md` direto do disco.

Isso também resolve, de um jeito mais robusto, o problema que começou a
conversa que levou a este projeto: um LLM rodando local via Ollama
sozinho não fala MCP (isso não muda), mas qualquer cliente MCP que você
configure pode conectar aqui e ter acesso estruturado ao conteúdo do
`moto_mcp`.

Este repositório não contém código específico de nenhum outro projeto
seu (ex: OCR) — isso foi removido de propósito. Qualquer projeto real
que você tenha usado como referência conceitual/estrutural durante o
design (padrões de segurança, decisões de arquitetura) fica só como
lição aprendida documentada, nunca como código embutido aqui.

## Modelo de segurança: leitura aberta, escrita restrita

Esta é a decisão de design central deste servidor:

- **Leitura**: cobre o repositório inteiro (`.md`/`.txt`), exceto
  pastas técnicas (`.git`, `.venv`, `__pycache__` etc). Qualquer agente
  conectado pode ler regras, knowledge, perfis de agente, projetos e
  clientes.
- **Escrita**: restrita a `projects/`, `clients/` e `profile/` —
  `Settings.WRITABLE_PREFIXES` em `mcp_server/config.py`.
  **`global/`, `agents/`, `knowledge/`, `templates/`, `handoff/` e os
  arquivos-ponte da raiz são somente leitura por este servidor, de
  propósito.**

O motivo da restrição: este é literalmente o repositório de regras de
comportamento que agentes de IA (inclusive eu, gerando este código) são
instruídos a seguir. Um servidor MCP que desse escrita irrestrita
deixaria um agente mal orientado — ou um prompt malicioso vindo de
qualquer lugar na conversa — reescrever as próprias regras que deveriam
te proteger. `paths.ensure_writable()` é chamado por toda escrita de
propósito geral (`documents.write_text`), então essa garantia é
estrutural, não uma checagem que cada tool precisa lembrar de fazer.

`profile/` é a única pasta fora de `projects/`/`clients/` liberada pra
escrita, e é deliberado: `profile/profile.md` não é regra de
comportamento do agente, é dado sobre o usuário (perfil, estilo de
trabalho, preferências) — natureza diferente das demais pastas
protegidas acima. Ficava em `global/user_profile.md` originalmente, mas
foi movido pra sua própria pasta especificamente pra poder virar essa
exceção sem abrir `global/` inteiro (que continua protegendo
`rules_absolute.md`, `workflow.md` etc.).

Ver `tests/test_write_restrictions.py` para a regressão disso: tenta
escrever em `global/rules_absolute.md`, `agents/bill.md`,
`knowledge/security/...`, `README.md`, `START_HERE.md` — todas devem
falhar com `PathNotWritableError`.

A única exceção controlada é o `INDEX.md`: `register_entry` atualiza
especificamente a seção "Projetos e clientes registrados" nele (não é
escrita livre — é uma função interna dedicada, `documents.write_index`,
nunca exposta como tool de escrita genérica).

## Tools expostas

- `get_capabilities` — catálogo desta lista.
- `list_documents(subpath="", recursive=False)` — lista arquivos/pastas.
- `read_document(path)` — lê um `.md`/`.txt`.
- `search_documents(query, subpath="", case_sensitive=False, max_results=50)` —
  busca texto em todo o repositório (ou num subpath), com número da linha.
- `get_template(kind="projeto"|"cliente")` — retorna o `_TEMPLATE.md`
  real (`projects/_TEMPLATE.md` ou `clients/_TEMPLATE.md`), lido do
  disco a cada chamada — nunca hardcoded aqui, porque os templates do
  seu repositório podem mudar.
- `register_entry(kind, nome, secoes, repositorio="", overwrite=False)` —
  cria `projects/<slug>.md` ou `clients/<slug>.md` a partir do template
  real, preenchendo as seções passadas, e registra a entrada em
  `INDEX.md`. Recusa sobrescrever por padrão. Valida as chaves de
  `secoes` contra os cabeçalhos reais do template — nome errado dá erro
  claro em vez de virar seção vazia silenciosamente.
- `replace_section(path, secao, novo_conteudo)` / `append_to_section(path, secao, texto)` —
  edita uma seção `## <nome>` de um documento já existente em `projects/`
  ou `clients/` (a seção precisa já existir — não cria seção nova
  silenciosamente, pra não divergir do template).

## Transporte: stdio (local)

Decisão explícita: **só local, via stdio** — sem porta de rede, sem
autenticação pra pensar. O cliente MCP sobe este processo diretamente
na sua máquina.

### Configurar em um cliente MCP (ex: Claude Desktop)

```json
{
  "mcpServers": {
    "moto-mcp": {
      "command": "poetry",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "cwd": "C:\\Users\\Pichau\\Desktop\\Projetos\\moto_mcp"
    }
  }
}
```

Se preferir não depender do Poetry estar no PATH do processo que sobe o
cliente MCP, aponte direto pro Python da venv criada pelo Poetry (depois
de rodar `poetry install` uma vez, `poetry env info --path` mostra o
caminho):

```json
{
  "mcpServers": {
    "moto-mcp": {
      "command": "C:\\Users\\Pichau\\AppData\\Local\\pypoetry\\Cache\\virtualenvs\\<nome-da-venv>\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"]
    }
  }
}
```

## Setup local

Requer Python `>=3.13,<4.0` e Poetry.

```bash
cd C:\Users\Pichau\Desktop\Projetos\moto_mcp
poetry install
poetry run python -m mcp_server.server
```

Ele espera stdin/stdout de um cliente MCP real — rodar direto no
terminal fica esperando input, o que é o comportamento correto pra
stdio (não é um bug, é assim que MCP via stdio funciona). Pra testar de
verdade, configure num cliente MCP (acima) ou use o MCP Inspector:

```bash
poetry run mcp dev mcp_server/server.py
```

## Testes

```bash
poetry install --with dev
poetry run pytest -v
```

**Pendência de origem**: não consegui instalar dependências nem rodar
`pytest` de verdade no sandbox onde este código foi gerado — PyPI
bloqueado por política de rede lá. Revisei os testes manualmente linha
a linha contra a implementação (inclusive simulando à mão o parsing de
seção markdown e a atualização do `INDEX.md`, onde encontrei e corrigi
um bug real: a primeira versão de `_register_in_index` perdia o próprio
cabeçalho `## Projetos e clientes registrados` ao reconstruir o
arquivo, por um uso errado de `str.partition`). `python -m py_compile`
passa em tudo. Isso é revisão manual + smoke de sintaxe, não validação
— rode `poetry run pytest` localmente antes de confiar nisto.

## Pendências conhecidas

- Testes não executados de verdade neste ambiente (ver acima).
- Sem `poetry.lock` gerado (mesma causa).
- Sem tool de **remover** um projeto/cliente registrado — só criar
  (com `overwrite`) e editar seção. Avaliar se faz sentido antes de
  expor escrita a um agente que pode, por exemplo, tentar "limpar"
  registros por conta própria.
- Sem limite de tamanho em `read_document`/`search_documents` — um
  arquivo `.md` gigante seria lido/varrido inteiro. Baixo risco aqui
  (é um repositório de anotações, não dados de usuário), mas fica
  registrado.
