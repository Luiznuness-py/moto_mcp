# tests/test_paths_safety.py
#
# Garantia de base: nenhum caminho vindo de uma tool escapa da raiz do
# repositório, nem alcança pastas técnicas (.git, .venv etc).

import pytest

from mcp_server.errors import PathNotWritableError, PathOutsideRepoError
from mcp_server.paths import ensure_writable, resolve_safe_path


class TestPathSafety:
    def test_rejects_parent_traversal(self, fake_repo):
        with pytest.raises(PathOutsideRepoError):
            resolve_safe_path("../outside.md")

    def test_rejects_ignored_dir_segment(self, fake_repo):
        (fake_repo / ".git").mkdir()
        with pytest.raises(PathOutsideRepoError):
            resolve_safe_path(".git/config")

    def test_resolves_normal_path(self, fake_repo):
        resolved = resolve_safe_path("global/rules_absolute.md")
        assert resolved == fake_repo / "global" / "rules_absolute.md"

    def test_resolves_empty_path_to_repo_root(self, fake_repo):
        assert resolve_safe_path("") == fake_repo.resolve()

    def test_write_blocked_outside_whitelist(self, fake_repo):
        with pytest.raises(PathNotWritableError):
            ensure_writable(fake_repo / "global" / "rules_absolute.md")

    def test_write_allowed_inside_whitelist(self, fake_repo):
        ensure_writable(fake_repo / "projects" / "algo.md")  # não levanta
