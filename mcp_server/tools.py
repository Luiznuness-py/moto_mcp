# mcp_server/tools.py
#
# Cada tool de escrita aqui delega a proteção de caminho pra
# documents.write_text()/replace_section(), que sempre passam por
# paths.ensure_writable(). Isso é garantia estrutural, não checagem
# espalhada — mesma filosofia usada no gateway do moto_ocr (server/):
# a regra vive num único lugar, não repetida em cada tool.

from __future__ import annotations

import re

from mcp_server import documents
from mcp_server.config import settings
from mcp_server.errors import (
    DocumentNotFoundError,
    EntryAlreadyExistsError,
    TemplateNotFoundError,
)

_KIND_TO_DIR = {"projeto": "projects", "cliente": "clients"}


def _slugify(nome: str) -> str:
    slug = nome.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "sem-nome"


async def get_capabilities() -> dict:
    """Catálogo das tools deste servidor e o que cada uma faz."""
    return {
        "servico": "MotoMCP Framework Server (self-hosted, stdio)",
        "descricao": (
            "Expõe o conteúdo do próprio repositório moto_mcp (regras, "
            "knowledge, agentes, projetos, clientes) como tools MCP. "
            "Leitura cobre o repositório inteiro (exceto pastas técnicas "
            "como .git/.venv); escrita só é permitida dentro de "
            f"{', '.join(f'{p}/' for p in settings.WRITABLE_PREFIXES)} — "
            "global/, agents/ e knowledge/ são somente leitura por este "
            "servidor de propósito (ver docs/mcp_server.md, 'Modelo de "
            "segurança')."
        ),
        "tools": [
            {"tool": "list_documents", "tipo": "leitura"},
            {"tool": "read_document", "tipo": "leitura"},
            {"tool": "search_documents", "tipo": "leitura"},
            {"tool": "list_agents", "tipo": "leitura"},
            {"tool": "get_template", "tipo": "leitura"},
            {"tool": "register_entry", "tipo": "escrita", "restrito_a": settings.WRITABLE_PREFIXES},
            {"tool": "replace_section", "tipo": "escrita", "restrito_a": settings.WRITABLE_PREFIXES},
            {"tool": "append_to_section", "tipo": "escrita", "restrito_a": settings.WRITABLE_PREFIXES},
        ],
    }


async def list_documents(subpath: str = "", recursive: bool = False) -> list[dict]:
    """
    Lista arquivos/pastas do repositório a partir de `subpath` (raiz do
    repo se vazio). Só lista extensões legíveis (.md/.txt) e pula
    pastas técnicas (.git, .venv, __pycache__ etc).
    """
    return [vars(e) for e in documents.list_entries(subpath, recursive=recursive)]


async def read_document(path: str) -> str:
    """Lê o conteúdo de um arquivo .md/.txt do repositório, pelo caminho relativo à raiz (ex: 'global/rules_absolute.md')."""
    return documents.read_text(path)


async def search_documents(
    query: str,
    subpath: str = "",
    case_sensitive: bool = False,
    max_results: int = 50,
) -> list[dict]:
    """Busca uma string em todos os .md/.txt sob `subpath` (repositório inteiro se vazio). Retorna path/linha/trecho de cada ocorrência."""
    return documents.search(query, subpath, case_sensitive=case_sensitive, max_results=max_results)


async def list_agents() -> list[dict]:
    """
    Lista os agentes definidos em agents/ — nome, papel resumido e
    arquivo — pra quem não leu o repositório inteiro descobrir quem
    existe sem precisar adivinhar nome de arquivo. Lido do disco a cada
    chamada, nunca hardcoded (mesmo princípio de get_template): agente
    novo em agents/ aparece aqui sozinho, sem precisar tocar em código.

    Nome/papel são extraídos da primeira linha de cada arquivo (título
    '# Nome — Papel', convenção seguida pelos 7 agentes atuais). Um
    arquivo sem essa convenção ainda aparece na lista, só com `papel`
    vazio — nunca é omitido silenciosamente.

    `agents/` inexistente (ex: fork do moto_mcp que ainda não definiu
    nenhum agente) devolve lista vazia — não é erro.
    """
    agents: list[dict] = []
    try:
        entries = documents.list_entries("agents")
    except DocumentNotFoundError:
        return agents

    for entry in entries:
        if entry.type != "file":
            continue
        text = documents.read_text(entry.path)
        first_line = text.splitlines()[0].strip() if text.strip() else ""
        title = first_line.lstrip("#").strip()
        if " — " in title:
            nome, papel = (part.strip() for part in title.split(" — ", 1))
        else:
            nome, papel = title, ""
        agents.append({"nome": nome, "papel": papel, "arquivo": entry.path})
    return agents


async def get_template(kind: str = "projeto") -> dict:
    """
    Retorna o template real (_TEMPLATE.md) usado por register_entry
    para 'projeto' ou 'cliente' — conteúdo bruto e a lista de seções
    ('## ...') já identificadas, para o chamador saber que campos
    preencher antes de registrar uma entrada nova. Lido do disco a cada
    chamada, nunca hardcoded aqui, porque o template pode mudar.
    """
    if kind not in _KIND_TO_DIR:
        raise ValueError("kind precisa ser 'projeto' ou 'cliente'.")
    template_path = f"{_KIND_TO_DIR[kind]}/_TEMPLATE.md"
    try:
        raw = documents.read_text(template_path)
    except DocumentNotFoundError as exc:
        raise TemplateNotFoundError(f"Template '{template_path}' não encontrado no repositório.") from exc
    sections = documents.split_sections(raw)
    return {"template_path": template_path, "raw": raw, "secoes": [s for s in sections if s]}


async def register_entry(
    kind: str,
    nome: str,
    secoes: dict[str, str],
    repositorio: str = "",
    overwrite: bool = False,
) -> dict:
    """
    Cria projects/<slug>.md ou clients/<slug>.md a partir do template
    real do repositório, preenchendo as seções passadas em `secoes`
    (chave = título da seção '## ...' tal como aparece no template,
    valor = corpo). Seções do template não passadas ficam vazias — use
    get_template antes pra saber quais existem. Também registra a
    entrada em INDEX.md ("Projetos e clientes registrados"). Por padrão
    recusa sobrescrever um arquivo existente — passe overwrite=True de
    propósito se for isso mesmo.
    """
    if kind not in _KIND_TO_DIR:
        raise ValueError("kind precisa ser 'projeto' ou 'cliente'.")
    dir_name = _KIND_TO_DIR[kind]
    template = await get_template(kind)

    unknown = sorted(set(secoes) - set(template["secoes"]))
    if unknown:
        raise ValueError(
            f"Seção(ões) desconhecida(s) para o template de '{kind}': {unknown}. "
            f"Seções válidas: {template['secoes']}. Chame get_template('{kind}') "
            "antes pra conferir os nomes exatos."
        )

    slug = _slugify(nome)
    target_path = f"{dir_name}/{slug}.md"

    if not overwrite:
        exists = True
        try:
            documents.read_text(target_path)
        except DocumentNotFoundError:
            exists = False
        if exists:
            raise EntryAlreadyExistsError(
                f"'{target_path}' já existe. Passe overwrite=True para sobrescrever de propósito."
            )

    lines = [f"# {nome}"]
    if repositorio:
        lines.append(f"Repositório: `{repositorio}`.")
    for header in template["secoes"]:
        lines.append(f"\n## {header}")
        body = secoes.get(header, "").strip()
        if body:
            lines.append(body)

    documents.write_text(target_path, "\n".join(lines).strip("\n") + "\n")
    _register_in_index(nome, target_path)

    return {
        "path": target_path,
        "slug": slug,
        "secoes_preenchidas": [k for k in secoes if secoes.get(k, "").strip()],
    }


def _register_in_index(nome: str, target_path: str) -> None:
    index_content = documents.read_text("INDEX.md")
    marker = "## Projetos e clientes registrados"
    if marker not in index_content:
        # Estrutura inesperada — não inventa uma seção nova no INDEX.md.
        return

    bullet = f"- `{target_path}` — {nome}."
    # str.partition tira o próprio marcador de head/tail (fica em `sep`) —
    # precisa ser recolocado ao remontar, senão o cabeçalho da seção some.
    head, sep, tail = index_content.partition(marker)
    body_lines = [
        line for line in tail.splitlines() if line.strip() and not line.strip().startswith("Nenhum ainda")
    ]
    if bullet not in body_lines:
        body_lines.append(bullet)

    new_section = sep + "\n\n" + "\n".join(body_lines)
    new_content = (head + new_section).rstrip("\n") + "\n"
    documents.write_index(new_content)


async def replace_section(path: str, secao: str, novo_conteudo: str) -> dict:
    """Substitui o corpo da seção '## <secao>' de um documento em projects/ ou clients/. A seção precisa já existir no documento."""
    documents.replace_section(path, secao, novo_conteudo, append=False)
    return {"path": path, "secao": secao, "acao": "substituida"}


async def append_to_section(path: str, secao: str, texto: str) -> dict:
    """Acrescenta texto ao final da seção '## <secao>' de um documento em projects/ ou clients/ (não sobrescreve o que já tinha)."""
    documents.replace_section(path, secao, texto, append=True)
    return {"path": path, "secao": secao, "acao": "acrescentado"}
