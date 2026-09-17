# mcp_server/documents.py
#
# Operações de baixo nível sobre arquivos markdown/texto do repositório.
# tools.py só orquestra chamadas pra cá — parsing de seção e garantia de
# path safety vivem neste módulo, não espalhadas por tool.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mcp_server.config import settings
from mcp_server.errors import (
    DocumentNotFoundError,
    SectionNotFoundError,
    UnsupportedExtensionError,
)
from mcp_server.paths import ensure_writable, is_ignored_dir, resolve_safe_path


@dataclass
class Entry:
    name: str
    path: str  # relativo à raiz do repo, sempre com "/"
    type: str  # "file" | "dir"
    size: int | None = None


def _check_extension(path: Path) -> None:
    if path.suffix not in settings.READABLE_EXTENSIONS:
        raise UnsupportedExtensionError(
            f"Extensão '{path.suffix}' não é lida por este servidor "
            f"(permitidas: {', '.join(settings.READABLE_EXTENSIONS)})."
        )


def list_entries(subpath: str = "", *, recursive: bool = False) -> list[Entry]:
    base = resolve_safe_path(subpath)
    if not base.exists():
        raise DocumentNotFoundError(f"'{subpath or '.'}' não existe no repositório.")

    repo_root = settings.REPO_ROOT.resolve()

    if base.is_file():
        rel = base.relative_to(repo_root)
        return [Entry(name=base.name, path=str(rel).replace("\\", "/"), type="file", size=base.stat().st_size)]

    entries: list[Entry] = []
    iterator = base.rglob("*") if recursive else base.iterdir()
    for item in sorted(iterator):
        rel_to_base = item.relative_to(base).parts
        if any(is_ignored_dir(part) for part in rel_to_base):
            continue
        rel = item.resolve().relative_to(repo_root)
        if item.is_dir():
            entries.append(Entry(name=item.name, path=str(rel).replace("\\", "/"), type="dir"))
        elif item.suffix in settings.READABLE_EXTENSIONS:
            entries.append(
                Entry(name=item.name, path=str(rel).replace("\\", "/"), type="file", size=item.stat().st_size)
            )
    return entries


def read_text(relative_path: str) -> str:
    path = resolve_safe_path(relative_path)
    _check_extension(path)
    if not path.is_file():
        raise DocumentNotFoundError(f"'{relative_path}' não existe (ou não é um arquivo).")
    return path.read_text(encoding="utf-8")


def write_text(relative_path: str, content: str, *, create_dirs: bool = True) -> None:
    """Escrita intencionalmente geral — sempre passa por ensure_writable.
    Usada para arquivos dentro de WRITABLE_PREFIXES (projects/, clients/,
    profile/)."""
    path = resolve_safe_path(relative_path)
    _check_extension(path)
    ensure_writable(path)
    if create_dirs:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_index(content: str) -> None:
    """
    Escreve especificamente em INDEX.md. Não passa por ensure_writable
    porque não é escrita livre: só é chamada internamente por
    tools.register_entry, e só pra acrescentar/atualizar a seção
    'Projetos e clientes registrados' — nunca exposta como tool de
    escrita genérica.
    """
    path = resolve_safe_path("INDEX.md")
    _check_extension(path)
    path.write_text(content, encoding="utf-8")


def search(query: str, subpath: str = "", *, case_sensitive: bool = False, max_results: int = 50) -> list[dict]:
    base = resolve_safe_path(subpath)
    repo_root = settings.REPO_ROOT.resolve()
    needle = query if case_sensitive else query.lower()
    results: list[dict] = []
    candidates = base.rglob("*") if base.is_dir() else [base]
    for item in sorted(candidates):
        if not item.is_file() or item.suffix not in settings.READABLE_EXTENSIONS:
            continue
        rel_parts = item.resolve().relative_to(repo_root).parts
        if any(is_ignored_dir(part) for part in rel_parts):
            continue
        try:
            text = item.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            haystack = line if case_sensitive else line.lower()
            if needle in haystack:
                rel = item.resolve().relative_to(repo_root)
                results.append({"path": str(rel).replace("\\", "/"), "line": line_number, "text": line.strip()})
                if len(results) >= max_results:
                    return results
    return results


def split_sections(markdown: str) -> dict[str, str]:
    """
    Divide um markdown em seções por cabeçalho '## '. A chave é o texto
    do cabeçalho (sem o '## '); o valor é o corpo até o próximo '## '
    (ou até o fim do documento). Conteúdo antes do primeiro '## ' fica
    na chave "" (preâmbulo/título).
    """
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for line in markdown.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
        else:
            sections[current].append(line)
    return {key: "\n".join(lines).strip("\n") for key, lines in sections.items()}


def replace_section(relative_path: str, section: str, new_body: str, *, append: bool = False) -> None:
    """
    Substitui (ou, se append=True, acrescenta a) o corpo da seção
    '## <section>' de um documento já existente. Levanta
    SectionNotFoundError se a seção não existir — não cria seção nova
    silenciosamente, pra não divergir do template sem querer.

    Como usa write_text() por baixo, herda a restrição de
    WRITABLE_PREFIXES: só funciona em documentos dentro de projects/,
    clients/ ou profile/.
    """
    original = read_text(relative_path)
    lines = original.splitlines()
    header = f"## {section}"
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            continue
        if start is not None and line.startswith("## "):
            end = i
            break
    if start is None:
        raise SectionNotFoundError(f"Seção '## {section}' não encontrada em '{relative_path}'.")

    existing_body = "\n".join(lines[start + 1 : end]).strip("\n")
    if append and existing_body:
        body = f"{existing_body}\n{new_body}".strip("\n")
    else:
        body = new_body.strip("\n")

    new_lines = lines[: start + 1] + ["", body, ""] + lines[end:]
    write_text(relative_path, "\n".join(new_lines).strip("\n") + "\n")
