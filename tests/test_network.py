# tests/test_network.py
#
# ensure_safe_bind_host é a garantia estrutural que impede o modo de
# rede de subir fora da fronteira escolhida (tailscale/lan/local) — ver
# mcp_server/network.py.

import pytest

from mcp_server.errors import UnsafeBindHostError
from mcp_server.network import ensure_safe_bind_host


class TestModeInvalido:
    def test_rejects_unknown_mode(self):
        with pytest.raises(UnsafeBindHostError):
            ensure_safe_bind_host("100.64.0.1", "vpn")


class TestModeTailscale:
    @pytest.mark.parametrize(
        "host",
        ["", "0.0.0.0", "::", "127.0.0.1", "192.168.1.10", "10.0.0.5", "8.8.8.8", "not-an-ip"],
    )
    def test_rejects_unsafe_hosts(self, host):
        with pytest.raises(UnsafeBindHostError):
            ensure_safe_bind_host(host, "tailscale")

    @pytest.mark.parametrize("host", ["100.64.0.1", "100.100.100.100", "100.127.255.254"])
    def test_accepts_tailscale_range_hosts(self, host):
        ensure_safe_bind_host(host, "tailscale")

    def test_token_not_required(self):
        # Tailscale já autentica dispositivo — token é opcional aqui.
        ensure_safe_bind_host("100.64.0.1", "tailscale", auth_token="")


class TestModeLocal:
    @pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
    def test_accepts_loopback(self, host):
        ensure_safe_bind_host(host, "local")

    @pytest.mark.parametrize("host", ["", "0.0.0.0", "192.168.1.10", "100.64.0.1", "8.8.8.8"])
    def test_rejects_non_loopback(self, host):
        with pytest.raises(UnsafeBindHostError):
            ensure_safe_bind_host(host, "local")

    def test_token_not_required(self):
        ensure_safe_bind_host("127.0.0.1", "local", auth_token="")


_VALID_LAN_TOKEN = "a" * 32  # so precisa bater o piso de tamanho pro teste


class TestModeLan:
    @pytest.mark.parametrize(
        "host",
        ["192.168.1.10", "10.0.0.5", "172.16.0.1", "172.31.255.254", "169.254.1.1"],
    )
    def test_accepts_private_ranges_with_token(self, host):
        ensure_safe_bind_host(host, "lan", auth_token=_VALID_LAN_TOKEN)

    @pytest.mark.parametrize("host", ["", "0.0.0.0", "::", "8.8.8.8", "100.64.0.1", "not-an-ip"])
    def test_rejects_hosts_outside_lan_ranges(self, host):
        with pytest.raises(UnsafeBindHostError):
            ensure_safe_bind_host(host, "lan", auth_token=_VALID_LAN_TOKEN)

    def test_requires_token_even_with_valid_lan_host(self):
        # Garantia central deste modo: LAN sem token nao sobe, mesmo com
        # host valido.
        with pytest.raises(UnsafeBindHostError):
            ensure_safe_bind_host("192.168.1.10", "lan", auth_token="")

    @pytest.mark.parametrize("token", ["", "1", "curto", "a" * 31])
    def test_rejects_token_shorter_than_minimum(self, token):
        with pytest.raises(UnsafeBindHostError):
            ensure_safe_bind_host("192.168.1.10", "lan", auth_token=token)

    def test_accepts_token_at_exact_minimum_length(self):
        ensure_safe_bind_host("192.168.1.10", "lan", auth_token="a" * 32)
