# tests/conftest.py
#
# fake_repo cria uma versão mínima, mas estruturalmente fiel, do
# moto_mcp real (mesmos nomes de pasta, mesmos cabeçalhos de template) e
# aponta Settings.REPO_ROOT pra ela via monkeypatch. Nenhum teste toca o
# repositório real.

import pytest

from mcp_server import config


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    (tmp_path / "global").mkdir()
    (tmp_path / "global" / "rules_absolute.md").write_text(
        "# Regras\n\n## Não presumir contexto\nNão presuma nada sem confirmar.\n",
        encoding="utf-8",
    )

    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "_TEMPLATE.md").write_text(
        "# [Nome do projeto]\n"
        "Repositório: `[caminho ou URL do repositório]`.\n"
        "## Papel\n"
        "## Decisões de arquitetura\n"
        "## Stack\n"
        "## Estado atual\n"
        "## Pendências conhecidas\n",
        encoding="utf-8",
    )

    (tmp_path / "clients").mkdir()
    (tmp_path / "clients" / "_TEMPLATE.md").write_text(
        "# [Nome do cliente] — Memória\n"
        "## Confirmado\n"
        "## Hipóteses\n"
        "## Decisões\n"
        "## Pendências\n"
        "## Próximo passo\n",
        encoding="utf-8",
    )

    (tmp_path / "INDEX.md").write_text(
        "# Index\n\n"
        "## Projetos e clientes registrados\n\n"
        "Nenhum ainda — use `projects/_TEMPLATE.md` e `clients/_TEMPLATE.md` para criar o primeiro.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(config.settings, "REPO_ROOT", tmp_path)
    return tmp_path
