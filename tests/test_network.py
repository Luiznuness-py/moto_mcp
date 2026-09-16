# tests/test_network.py
#
# ensure_safe_bind_host é a garantia estrutural que impede o modo de
# rede de subir bindado em qualquer coisa fora da interface do
# Tailscale (100.64.0.0/10) — ver mcp_server/network.py.

import pytest

from mcp_server.errors import UnsafeBindHostError
from mcp_server.network import ensure_safe_bind_host


class TestEnsureSafeBindHost:
    @pytest.mark.parametrize(
        "host",
        [
            "",
            "0.0.0.0",
            "::",
            "127.0.0.1",
            "192.168.1.10",
            "10.0.0.5",
            "8.8.8.8",
            "not-an-ip",
        ],
    )
    def test_rejects_unsafe_hosts(self, host):
        with pytest.raises(UnsafeBindHostError):
            ensure_safe_bind_host(host)

    @pytest.mark.parametrize(
        "host",
        [
            "100.64.0.1",
            "100.100.100.100",
            "100.127.255.254",
        ],
    )
    def test_accepts_tailscale_range_hosts(self, host):
        ensure_safe_bind_host(host)
