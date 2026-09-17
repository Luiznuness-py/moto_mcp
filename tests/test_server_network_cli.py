# tests/test_server_network_cli.py
#
# Regressão: rodar `python -m mcp_server.server_network`
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
    # Sobrescreve com string vazia, não só remove — o repositório pode ter
    # um .env real configurado (ex: deploy em modo "lan" de verdade, com
    # host e token reais) e, no pydantic-settings, variável de ambiente
    # explícita tem prioridade sobre .env. Só remover a chave do dict não
    # basta: o processo filho leria o valor real do .env do mesmo jeito.
    # NETWORK_PORT fica de fora intencionalmente — tem default seguro (8765) e
    # é int, então "" quebraria o parsing sem testar nada de relevante aqui.
    env = dict(os.environ)
    env["MOTO_MCP_NETWORK_HOST"] = ""
    env["MOTO_MCP_AUTH_TOKEN"] = ""
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
