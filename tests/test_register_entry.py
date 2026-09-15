# tests/test_register_entry.py
#
# register_entry é a tool mais complexa deste servidor: lê o template
# real do disco (não hardcoded), monta o arquivo novo, e faz uma
# atualização estruturada do INDEX.md. Estes testes cobrem os dois
# templates reais (projeto e cliente), overwrite e o caso de template
# ausente.

import pytest

from mcp_server import documents, tools
from mcp_server.errors import EntryAlreadyExistsError, TemplateNotFoundError


class TestRegisterEntry:
    async def test_creates_project_file_from_template(self, fake_repo):
        result = await tools.register_entry(
            kind="projeto",
            nome="Moto MCP Server",
            repositorio="C:\\algum\\caminho",
            secoes={"Papel": "Gateway MCP.", "Stack": "Python."},
        )
        assert result["path"] == "projects/moto-mcp-server.md"
        content = documents.read_text("projects/moto-mcp-server.md")
        assert "Gateway MCP." in content
        assert "Python." in content
        assert "## Decisões de arquitetura" in content  # seção do template preservada mesmo vazia
        assert "C:\\algum\\caminho" in content

    async def test_creates_client_file_from_client_template(self, fake_repo):
        result = await tools.register_entry(kind="cliente", nome="Cliente X", secoes={"Confirmado": "Fato."})
        assert result["path"] == "clients/cliente-x.md"
        content = documents.read_text("clients/cliente-x.md")
        assert "Fato." in content
        assert "## Próximo passo" in content  # seção específica do template de cliente

    async def test_registers_in_index_replacing_placeholder(self, fake_repo):
        await tools.register_entry(kind="projeto", nome="Algo", secoes={})
        index = documents.read_text("INDEX.md")
        assert "Nenhum ainda" not in index
        assert "projects/algo.md" in index

    async def test_refuses_to_overwrite_by_default(self, fake_repo):
        await tools.register_entry(kind="projeto", nome="Dup", secoes={})
        with pytest.raises(EntryAlreadyExistsError):
            await tools.register_entry(kind="projeto", nome="Dup", secoes={})

    async def test_overwrite_true_allows_it(self, fake_repo):
        await tools.register_entry(kind="projeto", nome="Dup2", secoes={"Papel": "V1"})
        await tools.register_entry(kind="projeto", nome="Dup2", secoes={"Papel": "V2"}, overwrite=True)
        content = documents.read_text("projects/dup2.md")
        assert "V2" in content
        assert "V1" not in content

    async def test_missing_template_raises_clear_error(self, fake_repo):
        (fake_repo / "clients" / "_TEMPLATE.md").unlink()
        with pytest.raises(TemplateNotFoundError):
            await tools.register_entry(kind="cliente", nome="X", secoes={})

    async def test_invalid_kind_raises_value_error(self, fake_repo):
        with pytest.raises(ValueError):
            await tools.register_entry(kind="outra-coisa", nome="X", secoes={})

    async def test_unknown_section_key_raises_value_error(self, fake_repo):
        with pytest.raises(ValueError, match="Papeel"):
            await tools.register_entry(kind="projeto", nome="Erro", secoes={"Papeel": "typo"})

    async def test_registering_twice_does_not_duplicate_index_bullet(self, fake_repo):
        await tools.register_entry(kind="projeto", nome="Tri", secoes={"Papel": "V1"})
        await tools.register_entry(kind="projeto", nome="Tri", secoes={"Papel": "V2"}, overwrite=True)
        index = documents.read_text("INDEX.md")
        assert index.count("projects/tri.md") == 1
