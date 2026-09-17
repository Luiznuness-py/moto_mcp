# mcp_server/websearch.py
#
# Adaptador simples pra uma instância própria de SearXNG (ver
# docker-compose.yml na raiz) — metabuscador que agrega resultado de
# vários motores sem exigir chave de API nenhuma.
#
# Sem Protocol/contrato de troca de provedor aqui, ao contrário de
# embeddings.py/vectorstore.py: aqueles têm um plano concreto de trocar
# de implementação. Não há
# plano equivalente de trocar o motor de busca web — construir essa
# abstração agora seria abstração prematura sem justificativa real (ver
# global/workflow.md). Se um dia precisar trocar, generaliza então.

from __future__ import annotations

import httpx

from mcp_server.errors import WebSearchError


def search_web(
    query: str,
    max_results: int = 10,
    page: int = 1,
    *,
    client: httpx.Client | None = None,
) -> list[dict]:
    """
    Busca `query` na instância de SearXNG configurada
    (`Settings.SEARXNG_BASE_URL`) e devolve os `max_results` primeiros
    resultados de `page` como `{"title", "url", "content"}`.

    `page` usa a paginação nativa do SearXNG (`pageno`) — pra ver mais
    resultados da mesma busca, pede `page=2`, `page=3` etc., em vez de
    tentar caber tudo numa resposta só (ou truncar o conteúdo de cada
    resultado, que perderia informação). Confirmado com dado real que
    páginas diferentes trazem resultado majoritariamente diferente, não
    sobreposto.

    `client` existe só pra permitir injetar um `httpx.Client` falso nos
    testes, sem chamada de rede real — mesmo padrão de
    `OllamaEmbeddingProvider` (ver mcp_server/embeddings.py).
    """
    from mcp_server.config import settings

    owns_client = client is None
    http_client = client or httpx.Client(timeout=10.0)
    try:
        response = http_client.get(
            f"{settings.SEARXNG_BASE_URL}/search",
            params={"q": query, "format": "json", "pageno": page},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise WebSearchError(
            f"Falha ao consultar o SearXNG em '{settings.SEARXNG_BASE_URL}'. "
            "Confirme que o container está rodando (`podman compose -p moto-mcp "
            "-f docker-compose.yml up -d searxng`) e que o formato JSON está "
            "habilitado em searxng/settings.yml (`search.formats` precisa "
            "incluir `json`)."
        ) from exc
    finally:
        if owns_client:
            http_client.close()

    try:
        payload = response.json()
    except ValueError as exc:
        raise WebSearchError(
            "Resposta do SearXNG não é JSON válido — confirme que "
            "`search.formats` inclui `json` em searxng/settings.yml "
            "(por padrão o SearXNG recusa esse formato)."
        ) from exc

    results = payload.get("results", [])
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        }
        for r in results[:max_results]
    ]
