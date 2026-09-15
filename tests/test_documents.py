# tests/test_documents.py

import pytest

from mcp_server import documents
from mcp_server.errors import SectionNotFoundError, UnsupportedExtensionError


class TestListAndRead:
    def test_list_root_skips_ignored_dirs(self, fake_repo):
        (fake_repo / ".git").mkdir()
        entries = documents.list_entries("")
        names = {e.name for e in entries}
        assert ".git" not in names
        assert "projects" in names
        assert "clients" in names

    def test_read_existing_document(self, fake_repo):
        content = documents.read_text("global/rules_absolute.md")
        assert "Não presuma nada sem confirmar." in content

    def test_read_missing_document_raises(self, fake_repo):
        from mcp_server.errors import DocumentNotFoundError

        with pytest.raises(DocumentNotFoundError):
            documents.read_text("global/nao_existe.md")

    def test_read_rejects_non_readable_extension(self, fake_repo):
        (fake_repo / "segredo.env").write_text("X=1", encoding="utf-8")
        with pytest.raises(UnsupportedExtensionError):
            documents.read_text("segredo.env")


class TestSearch:
    def test_finds_match_with_line_number(self, fake_repo):
        results = documents.search("presumir")
        assert any(r["path"] == "global/rules_absolute.md" and r["line"] == 3 for r in results)

    def test_search_is_case_insensitive_by_default(self, fake_repo):
        results = documents.search("REGRAS")
        assert any(r["path"] == "global/rules_absolute.md" for r in results)

    def test_search_respects_max_results(self, fake_repo):
        (fake_repo / "projects" / "muitos.md").write_text("achar\n" * 10, encoding="utf-8")
        results = documents.search("achar", max_results=3)
        assert len(results) == 3


class TestSections:
    def test_replace_section_body(self, fake_repo):
        target = "projects/x.md"
        documents.write_text(target, "# X\n## Papel\nAntigo.\n## Stack\nPython.\n")
        documents.replace_section(target, "Papel", "Novo papel.")
        updated = documents.read_text(target)
        assert "Novo papel." in updated
        assert "Antigo." not in updated
        assert "Python." in updated  # outra seção intacta

    def test_append_to_section_keeps_existing(self, fake_repo):
        target = "projects/y.md"
        documents.write_text(target, "# Y\n## Pendências conhecidas\nItem 1.\n")
        documents.replace_section(target, "Pendências conhecidas", "Item 2.", append=True)
        updated = documents.read_text(target)
        assert "Item 1." in updated
        assert "Item 2." in updated

    def test_missing_section_raises(self, fake_repo):
        target = "projects/z.md"
        documents.write_text(target, "# Z\n## Papel\nX.\n")
        with pytest.raises(SectionNotFoundError):
            documents.replace_section(target, "Não existe", "Y.")
