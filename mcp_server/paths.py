# mcp_server/paths.py
#
# Toda entrada de caminho vinda de uma tool passa por aqui antes de
# tocar o disco. Duas garantias, cada uma com sua própria exceção:
# (1) nunca resolve pra fora da raiz do repositório, nem passa por uma
#     pasta ignorada — sem path traversal via "..", caminho absoluto ou
#     acesso a .git/.venv/etc;
# (2) escrita só é permitida dentro de WRITABLE_PREFIXES.

from pathlib import Path

from mcp_server.config import settings
from mcp_server.errors import PathNotWritableError, PathOutsideRepoError


def is_ignored_dir(name: str) -> bool:
    return name in settings.IGNORED_DIR_NAMES or name.startswith(".")


def resolve_safe_path(relative_path: str) -> Path:
    """
    Resolve um caminho relativo (como veio da tool) contra REPO_ROOT e
    garante que o resultado ainda está dentro do repositório, sem
    passar por nenhuma pasta ignorada.
    """
    cleaned = relative_path.strip().lstrip("/\\")
    parts = Path(cleaned).parts
    for part in parts:
        if is_ignored_dir(part):
            raise PathOutsideRepoError(
                f"'{relative_path}' passa por uma pasta não acessível "
                f"por este servidor ('{part}')."
            )

    repo_root = settings.REPO_ROOT.resolve()
    candidate = (repo_root / cleaned).resolve()
    if candidate != repo_root and repo_root not in candidate.parents:
        raise PathOutsideRepoError(
            f"'{relative_path}' resolve para fora da raiz do repositório."
        )
    return candidate


def ensure_writable(path: Path) -> None:
    """Levanta PathNotWritableError se `path` não estiver dentro de uma
    das pastas em Settings.WRITABLE_PREFIXES."""
    repo_root = settings.REPO_ROOT.resolve()
    relative = path.resolve().relative_to(repo_root)
    top_level = relative.parts[0] if relative.parts else ""
    if top_level not in settings.WRITABLE_PREFIXES:
        raise PathNotWritableError(
            f"Escrita não permitida em '{relative}'. Só é permitido escrever "
            f"dentro de: {', '.join(settings.WRITABLE_PREFIXES)}."
        )
