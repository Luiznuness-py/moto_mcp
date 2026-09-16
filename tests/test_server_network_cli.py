# tests/test_server_network_cli.py
#
# Achado real (2026-09-16): rodar `python -m mcp_server.server_network`
# sem nenhuma variável de ambiente configurada (cenário exato de quem
# clona o repositório pela primeira vez) devolvia um stack trace cru do
# Python — péssima experiência pro público que este servidor mira
# (pouco conhecimento técnico). Este teste sobe o processo de verdade,
# via subprocess, exatamente como um usuário rodaria, e confirma que a
# saída agora é uma mensagem limpa, não um traceback.

import os
import subprocess
import sys

import pytest


def _run_without_network_env(extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("MOTO_MCP_NETWORK") and k != "MOTO_MCP_AUTH_TOKEN"}
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-m", "mcp_server.server_network"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


class TestServerNetworkCliErrors:
    def test_missing_host_prints_clean_message_not_traceback(self):
        result = _run_without_network_env()

        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "MOTO_MCP_NETWORK_HOST" in result.stderr

    def test_lan_mode_missing_token_prints_clean_message_not_traceback(self):
        result = _run_without_network_env(
            {"MOTO_MCP_NETWORK_MODE": "lan", "MOTO_MCP_NETWORK_HOST": "192.168.1.10"}
        )

        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "AUTH_TOKEN" in result.stderr
