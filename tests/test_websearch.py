# tests/test_websearch.py
#
# Testa mcp_server.websearch.search_web com um cliente httpx falso —
# nenhum teste aqui faz chamada de rede real nem depende de um SearXNG
# rodando. Mesmo padrão de tests/test_embeddings.py (cliente Ollama
# falso injetado via `client=`).

from __future__ import annotations

import httpx
import pytest

from mcp_server.errors import WebSearchError
from mcp_server.websearch import search_web


class _FakeResponse:
    def __init__(self, json_data=None, status_code=200, raise_json_error=False):
        self._json_data = json_data
        self.status_code = status_code
        self._raise_json_error = raise_json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://fake/search")
            raise httpx.HTTPStatusError("erro fake", request=request, response=self)

    def json(self):
        if self._raise_json_error:
            raise ValueError("não é JSON")
        return self._json_data


class _FakeHttpClient:
    def __init__(self, response=None, raise_connect_error=False):
        self._response = response
        self._raise_connect_error = raise_connect_error
        self.calls: list[dict] = []

    def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        if self._raise_connect_error:
            raise httpx.ConnectError("conexão recusada (fake)")
        return self._response

    def close(self):
        pass


class TestSearchWeb:
    def test_returns_parsed_results(self):
        fake_response = _FakeResponse(
            json_data={
                "results": [
                    {"title": "A", "url": "http://a", "content": "conteudo a"},
                    {"title": "B", "url": "http://b", "content": "conteudo b"},
                ]
            }
        )
        client = _FakeHttpClient(response=fake_response)

        results = search_web("teste", max_results=10, client=client)

        assert results == [
            {"title": "A", "url": "http://a", "content": "conteudo a"},
            {"title": "B", "url": "http://b", "content": "conteudo b"},
        ]
        assert client.calls[0]["params"]["q"] == "teste"
        assert client.calls[0]["params"]["format"] == "json"
        assert client.calls[0]["params"]["pageno"] == 1

    def test_page_param_forwarded_as_pageno(self):
        client = _FakeHttpClient(response=_FakeResponse(json_data={"results": []}))

        search_web("teste", page=3, client=client)

        assert client.calls[0]["params"]["pageno"] == 3

    def test_respects_max_results(self):
        fake_response = _FakeResponse(
            json_data={"results": [{"title": str(i), "url": "", "content": ""} for i in range(20)]}
        )
        client = _FakeHttpClient(response=fake_response)

        results = search_web("teste", max_results=3, client=client)

        assert len(results) == 3

    def test_empty_results_is_not_error(self):
        client = _FakeHttpClient(response=_FakeResponse(json_data={"results": []}))
        assert search_web("nada encontrado", client=client) == []

    def test_connection_failure_raises_websearcherror(self):
        client = _FakeHttpClient(raise_connect_error=True)
        with pytest.raises(WebSearchError):
            search_web("teste", client=client)

    def test_http_error_status_raises_websearcherror(self):
        client = _FakeHttpClient(response=_FakeResponse(status_code=500))
        with pytest.raises(WebSearchError):
            search_web("teste", client=client)

    def test_invalid_json_raises_websearcherror(self):
        client = _FakeHttpClient(response=_FakeResponse(raise_json_error=True))
        with pytest.raises(WebSearchError):
            search_web("teste", client=client)
