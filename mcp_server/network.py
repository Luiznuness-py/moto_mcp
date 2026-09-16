# mcp_server/network.py
#
# Garantia estrutural do modo de rede (streamable-http): o servidor só
# sobe se o host configurado for um endereço da faixa do Tailscale
# (100.64.0.0/10, CGNAT — é a faixa que o Tailscale usa pra todo
# dispositivo do tailnet). Mesma filosofia de mcp_server/paths.py
# (ensure_writable) — a regra vive numa função só, chamada uma vez no
# ponto de entrada, não checada espalhada.
#
# Isso não é autenticação — é impedir, antes mesmo de abrir o socket,
# que uma configuração errada (esquecer de setar MOTO_MCP_NETWORK_HOST,
# ou setar "0.0.0.0" por engano) exponha o servidor além do Tailscale.
# A decisão de usar o Tailscale como fronteira de confiança (em vez de
# token/auth própria) está registrada em to-do.md, "Transporte de
# rede" — condicionada a continuar sendo só dispositivo do próprio
# usuário; não é uma garantia contra alguém que já está no tailnet.

from __future__ import annotations

import ipaddress

from mcp_server.errors import UnsafeBindHostError

# Faixa CGNAT que o Tailscale atribui a todo dispositivo do tailnet
# (documentado pelo próprio Tailscale). Qualquer host fora disso é
# recusado, mesmo que seja um IP privado "normal" (ex: 192.168.x.x) —
# a intenção explícita é só a interface do Tailscale, não a LAN.
_TAILSCALE_RANGE = ipaddress.ip_network("100.64.0.0/10")


def ensure_safe_bind_host(host: str) -> None:
    """Levanta UnsafeBindHostError se `host` não for um endereço IPv4
    dentro da faixa do Tailscale (100.64.0.0/10). Vazio, wildcard
    ("0.0.0.0"/"::"), IP público ou IP de LAN comum são todos
    recusados — a intenção é restringir ao mínimo, não à LAN inteira."""
    if not host:
        raise UnsafeBindHostError(
            "MOTO_MCP_NETWORK_HOST não configurado. O modo de rede exige "
            "o IP da interface do Tailscale desta máquina (formato "
            "100.x.x.x, confirme com `tailscale ip -4`) — sem isso o "
            "servidor não sobe, de propósito."
        )

    try:
        addr = ipaddress.ip_address(host)
    except ValueError as exc:
        raise UnsafeBindHostError(
            f"'{host}' não é um endereço IP válido."
        ) from exc

    if addr not in _TAILSCALE_RANGE:
        raise UnsafeBindHostError(
            f"'{host}' está fora da faixa do Tailscale (100.64.0.0/10). "
            "O modo de rede só sobe bindado na interface do Tailscale — "
            "nunca em '0.0.0.0', '::' ou IP de LAN/rede pública. Confirme "
            "o IP certo com `tailscale ip -4`."
        )
