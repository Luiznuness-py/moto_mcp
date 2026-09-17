# mcp_server/auth.py
#
# Middleware Starlette para validar Bearer token no transporte de rede.
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
        # hmac.compare_digest faz comparação em tempo constante.
        if not hmac.compare_digest(auth_header, self._expected):
            return JSONResponse({"detail": "Token ausente ou inválido."}, status_code=401)
        return await call_next(request)
