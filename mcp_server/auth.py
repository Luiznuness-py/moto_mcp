# mcp_server/auth.py
#
# Middleware Starlette pra validar um token Bearer simples no modo de
# rede — mesma forma de checagem (comparação de tempo constante) que o
# mcp_gateway/auth.py do moto_ocr usa pro JWE dele, só que aqui é um
# segredo compartilhado direto (sem JWE/tenant/scope — o moto_mcp não
# tem esse conceito, é servidor pessoal de um usuário só). Ver
# to-do.md/docs/mcp_server.md, "Transporte de rede", pro raciocínio
# completo de por que isso é suficiente aqui e não seria no moto_ocr.
#
# Só é montado (ver server_network.py) quando Settings.AUTH_TOKEN está
# configurado — obrigatório em modo "lan" (mcp_server/network.py),
# opcional em "tailscale"/"local".

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class BearerTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._expected = f"Bearer {token}"

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization", "")
        # hmac.compare_digest evita timing attack (comparação de tempo
        # constante) — mesma técnica já usada no ecossistema pro JWE do
        # moto_ocr, aqui aplicada a um segredo compartilhado simples.
        if not hmac.compare_digest(auth_header, self._expected):
            return JSONResponse({"detail": "Token ausente ou inválido."}, status_code=401)
        return await call_next(request)
