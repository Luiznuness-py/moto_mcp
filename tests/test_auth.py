# tests/test_auth.py
#
# BearerTokenMiddleware é a checagem obrigatoria no modo "lan" (ver
# mcp_server/network.py) e opcional nos demais. Testado com uma app
# Starlette minima, sem precisar do servidor MCP de verdade.

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_server.auth import BearerTokenMiddleware


_VALID_TOKEN = "a" * 32  # mesmo piso de tamanho exigido em modo "lan" (mcp_server/network.py)


def _make_app(token: str) -> Starlette:
    async def ok(request):
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/", ok)])
    app.add_middleware(BearerTokenMiddleware, token=token)
    return app


class TestBearerTokenMiddleware:
    def test_rejects_missing_header(self):
        client = TestClient(_make_app(_VALID_TOKEN))
        resp = client.get("/")
        assert resp.status_code == 401

    def test_rejects_wrong_token(self):
        client = TestClient(_make_app(_VALID_TOKEN))
        resp = client.get("/", headers={"Authorization": "Bearer token-errado"})
        assert resp.status_code == 401

    def test_accepts_correct_token(self):
        client = TestClient(_make_app(_VALID_TOKEN))
        resp = client.get("/", headers={"Authorization": f"Bearer {_VALID_TOKEN}"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
