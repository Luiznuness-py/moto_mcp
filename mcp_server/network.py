# mcp_server/network.py
#
# Garantia estrutural do modo de rede (streamable-http): o servidor só
# sobe se o host configurado bater com o modo escolhido
# (Settings.NETWORK_MODE) — mesma filosofia de mcp_server/paths.py
# (ensure_writable): a regra vive numa função só, chamada uma vez no
# ponto de entrada, não checada espalhada.
#
# Três modos, três fronteiras de confiança diferentes:
#
# - "tailscale" (padrão): só IP da faixa 100.64.0.0/10 (CGNAT que o
#   Tailscale atribui a todo dispositivo do tailnet). O próprio
#   Tailscale já autentica o dispositivo (WireGuard) — nenhum token
#   extra é exigido aqui, embora seja aceito como camada extra opcional
#   se configurado.
# - "lan": rede local/doméstica (10.0.0.0/8, 172.16.0.0/12,
#   192.168.0.0/16, link-local 169.254.0.0/16). LAN não autentica nada
#   sozinha — qualquer dispositivo na mesma rede alcançaria a porta.
#   Por isso este modo EXIGE Settings.AUTH_TOKEN configurado; sem
#   token, o servidor recusa subir (fail-closed, não silencioso).
# - "local": só 127.0.0.1/::1 — mesma máquina, nem LAN nem Tailscale.
#   Token continua opcional (a superfície já é a menor possível).
#
# Isso não substitui pensar no problema — é impedir, antes mesmo de
# abrir o socket, que uma configuração errada (esquecer de setar
# MOTO_MCP_NETWORK_HOST, setar "0.0.0.0" por engano, ou ligar "lan" sem
# token) exponha o servidor além do que foi escolhido de propósito.

from __future__ import annotations

import ipaddress

from mcp_server.errors import UnsafeBindHostError

_TAILSCALE_RANGE = ipaddress.ip_network("100.64.0.0/10")

_LAN_RANGES = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local, ex: sem DHCP
)

_LOCAL_ADDRESSES = (
    ipaddress.ip_address("127.0.0.1"),
    ipaddress.ip_address("::1"),
)

_VALID_MODES = ("tailscale", "lan", "local")


def ensure_safe_bind_host(host: str, mode: str, auth_token: str = "") -> None:
    """Levanta UnsafeBindHostError se `host` não bater com a fronteira
    de `mode`, ou se `mode == "lan"` sem `auth_token` configurado.
    Vazio, wildcard ("0.0.0.0"/"::"), ou endereço fora da faixa do modo
    escolhido são todos recusados — a intenção é restringir ao que foi
    pedido explicitamente, nunca abrir mais que isso."""
    if mode not in _VALID_MODES:
        raise UnsafeBindHostError(
            f"MOTO_MCP_NETWORK_MODE='{mode}' inválido — precisa ser um de: "
            f"{', '.join(_VALID_MODES)}."
        )

    if not host:
        raise UnsafeBindHostError(
            "MOTO_MCP_NETWORK_HOST não configurado. Sem isso o servidor "
            "não sobe, de propósito — veja docs/mcp_server.md, "
            "'Transporte de rede', pra saber qual IP usar no modo "
            f"'{mode}'."
        )

    try:
        addr = ipaddress.ip_address(host)
    except ValueError as exc:
        raise UnsafeBindHostError(f"'{host}' não é um endereço IP válido.") from exc

    if mode == "tailscale":
        if addr not in _TAILSCALE_RANGE:
            raise UnsafeBindHostError(
                f"'{host}' está fora da faixa do Tailscale (100.64.0.0/10). "
                "Modo 'tailscale' só sobe bindado na interface do "
                "Tailscale — nunca em '0.0.0.0', '::' ou IP de LAN/rede "
                "pública. Confirme o IP certo com `tailscale ip -4`, ou "
                "troque MOTO_MCP_NETWORK_MODE pra 'lan'/'local' se for "
                "essa a intenção."
            )
        return

    if mode == "local":
        if addr not in _LOCAL_ADDRESSES:
            raise UnsafeBindHostError(
                f"'{host}' não é loopback (127.0.0.1/::1). Modo 'local' só "
                "aceita a própria máquina."
            )
        return

    # mode == "lan"
    if not any(addr in net for net in _LAN_RANGES):
        raise UnsafeBindHostError(
            f"'{host}' está fora das faixas de LAN/rede doméstica "
            "(10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, "
            "169.254.0.0/16) — nunca em '0.0.0.0'/'::'/IP público. "
            "Modo 'lan' é pra rede doméstica, não a internet."
        )
    if not auth_token:
        raise UnsafeBindHostError(
            "Modo 'lan' exige MOTO_MCP_AUTH_TOKEN configurado — LAN não "
            "autentica ninguém sozinha, qualquer dispositivo na mesma "
            "rede alcançaria leitura/escrita sem isso. Gere um token "
            '(`python -c "import secrets; print(secrets.token_hex(32))"`) '
            "e configure antes de subir. Ver docs/mcp_server.md, "
            "'Transporte de rede'."
        )
