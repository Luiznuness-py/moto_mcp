# tests/test_write_restrictions.py
#
# Garantia central deste servidor: nenhuma tool consegue escrever fora
# de projects/, clients/ ou profile/. Em particular, as regras de
# comportamento (global/, agents/, knowledge/) são só leitura por aqui —
# um agente conectado neste MCP não pode reescrever as próprias regras
# através dele. Isto é a regressão que este projeto existe pra prevenir.
#
# profile/ é a exceção deliberada (dado sobre o usuário, não regra de
# comportamento — ver docs/mcp_server.md, "Modelo de segurança") —
# coberta por test_writes_inside_projects_clients_and_profile_are_allowed
# abaixo, não pela lista de bloqueio.

import pytest

from mcp_server import documents
from mcp_server.errors import PathNotWritableError


class TestWriteRestrictions:
    @pytest.mark.parametrize(
        "path",
        [
            "global/rules_absolute.md",
            "global/workflow.md",
            "knowledge/security/security_testing_baseline.md",
            "agents/bill.md",
            "README.md",
            "START_HERE.md",
            "templates/algum_prompt.md",
        ],
    )
    def test_cannot_write_governance_files(self, fake_repo, path):
        with pytest.raises(PathNotWritableError):
            documents.write_text(path, "conteúdo indevido")

    def test_replace_section_also_blocked_outside_whitelist(self, fake_repo):
        with pytest.raises(PathNotWritableError):
            documents.replace_section("global/rules_absolute.md", "Não presumir contexto", "novo conteúdo")

    def test_writes_inside_projects_clients_and_profile_are_allowed(self, fake_repo):
        documents.write_text("projects/ok.md", "# OK\n")
        documents.write_text("clients/ok.md", "# OK\n")
        documents.write_text("profile/profile.md", "# OK\n")
        assert documents.read_text("projects/ok.md") == "# OK\n"
        assert documents.read_text("clients/ok.md") == "# OK\n"
        assert documents.read_text("profile/profile.md") == "# OK\n"

    def test_replace_section_works_on_profile(self, fake_repo):
        # profile/ é a exceção deliberada: dado sobre o usuário, não
        # regra de comportamento do agente — ver comentário no topo do
        # arquivo e docs/mcp_server.md, "Modelo de segurança".
        documents.write_text("profile/profile.md", "# Perfil\n\n## Como ele/ela pensa\nPlaceholder.\n")
        documents.replace_section("profile/profile.md", "Como ele/ela pensa", "Analítico, direto ao ponto.")
        assert "Analítico, direto ao ponto." in documents.read_text("profile/profile.md")
