# mcp_server/embeddings.py
#
# Contrato de provedor de embedding + adaptador para o Ollama.
#
# Este módulo isola completamente a escolha do modelo de embedding (hoje:
# `bge-m3` via Ollama, local) do resto do código que vai consumir embeddings
# (chunking, indexação, busca vetorial). Trocar de modelo, ou de forma de
# gerar embedding (ex: uma API paga, à critério de quem instalar), significa
# escrever um novo adaptador que implemente `EmbeddingProvider` — nada além
# disso deveria precisar mudar. Ver knowledge/vector-search/ para o
# raciocínio completo por trás dessas decisões.
#
# Nota sobre a filosofia "sem chamada de rede" deste servidor (ver
# tests/test_write_restrictions.py e docs/mcp_server.md): a única chamada
# feita por este módulo é local, para o Ollama rodando na própria máquina
# (http://127.0.0.1:11434 por padrão) — nunca sai pra internet. `bge-m3` foi
# escolhido justamente por rodar 100% offline.

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mcp_server.errors import EmbeddingProviderError


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Contrato que qualquer provedor de embedding precisa cumprir."""

    def embed(self, text: str) -> list[float]:
        """Gera o embedding de um único texto."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Gera embeddings de vários textos de uma vez. Deve ser preferido a
        chamar `embed` em loop sempre que possível — é mais eficiente pra
        maioria dos provedores (inclusive o Ollama)."""


class OllamaEmbeddingProvider:
    """
    Adaptador para o Ollama, usando o modelo `bge-m3` por padrão.

    `bge-m3` não precisa de nenhum prefixo de instrução na pergunta
    (diferente das versões antigas da linha BGE, tipo `bge-large-en-v1.5`,
    que exigem algo como "Represent this sentence for searching relevant
    passages:" antes da pergunta pra funcionar bem) — o texto é passado
    exatamente como está, tanto pra indexar quanto pra buscar.

    O parâmetro `client` existe só pra permitir injetar um cliente falso
    nos testes, sem precisar do pacote `ollama` de verdade instalado nem de
    um Ollama rodando — ver tests/test_embeddings.py.
    """

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        client: object | None = None,
    ) -> None:
        from mcp_server.config import settings

        self._model = model or settings.EMBEDDING_MODEL

        if client is not None:
            self._client = client
            return

        try:
            import ollama
        except ImportError as exc:
            raise EmbeddingProviderError(
                "Pacote 'ollama' não instalado. Ver "
                "knowledge/vector-search/dependencias.md (`poetry add ollama`)."
            ) from exc

        # Sempre explícito — nunca deixa o cliente Ollama decidir sozinho
        # (ver o comentário em Settings.OLLAMA_HOST sobre o bug real do
        # "0.0.0.0" herdado da variável de ambiente OLLAMA_HOST).
        effective_host = host or settings.OLLAMA_HOST
        self._client = ollama.Client(host=effective_host)

    def embed(self, text: str) -> list[float]:
        """Gera o embedding de um único texto, via `embed_batch` com uma
        lista de um item só (evita duplicar a lógica de chamada/erro)."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Gera embeddings de vários textos numa única chamada ao Ollama —
        mais eficiente que chamar `embed` em loop (ver nota em
        knowledge/vector-search/dependencias.md sobre gerar em lote).

        Lista vazia devolve lista vazia sem chamar o Ollama. Qualquer falha
        de conexão (Ollama fora do ar, modelo não baixado, etc.) vira
        `EmbeddingProviderError` com uma mensagem acionável, em vez de
        vazar a exceção crua do cliente Ollama.
        """
        if not texts:
            return []

        try:
            response = self._client.embed(model=self._model, input=texts)
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Falha ao gerar embedding via Ollama (modelo '{self._model}'). "
                "Confirme que o Ollama está rodando e que o modelo foi baixado "
                f"(`ollama pull {self._model}`)."
            ) from exc

        try:
            embeddings = response["embeddings"]
        except (TypeError, KeyError):
            embeddings = getattr(response, "embeddings", None)

        if embeddings is None:
            raise EmbeddingProviderError(
                "Resposta do Ollama não trouxe o campo 'embeddings' esperado."
            )

        return [list(vector) for vector in embeddings]
