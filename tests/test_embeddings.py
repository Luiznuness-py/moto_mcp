# tests/test_embeddings.py
#
# Testa o contrato de embedding com um cliente Ollama falso — nenhum teste
# aqui faz chamada de rede nem depende do Ollama/bge-m3 estarem instalados.
# O cliente falso injetado via `client=` é o que faz isso possível (ver
# mcp_server/embeddings.py).

import sys

import pytest

from mcp_server import config
from mcp_server.embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from mcp_server.errors import EmbeddingProviderError


class _FakeOllamaClient:
    """Substitui ollama.Client nos testes. Devolve um vetor determinístico
    (tamanho do texto, repetido) só pra ter algo verificável."""

    def __init__(self):
        self.calls = []

    def embed(self, model, input):
        self.calls.append({"model": model, "input": input})
        return {"embeddings": [[float(len(text))] * 3 for text in input]}


class _FailingOllamaClient:
    def embed(self, model, input):
        raise ConnectionError("Ollama não está rodando")


class _FakeOllamaModule:
    """Substitui o pacote `ollama` inteiro nos testes, só pra capturar com
    quais argumentos `ollama.Client(...)` foi chamado — sem precisar do
    pacote de verdade instalado."""

    def __init__(self):
        self.client_kwargs = None

    def Client(self, **kwargs):
        self.client_kwargs = kwargs
        return _FakeOllamaClient()


def test_ollama_provider_satisfies_protocol():
    provider = OllamaEmbeddingProvider(client=_FakeOllamaClient())
    assert isinstance(provider, EmbeddingProvider)


def test_embed_batch_returns_one_vector_per_text():
    fake = _FakeOllamaClient()
    provider = OllamaEmbeddingProvider(client=fake)

    result = provider.embed_batch(["oi", "mais longo"])

    assert result == [[2.0, 2.0, 2.0], [10.0, 10.0, 10.0]]
    assert fake.calls == [{"model": "bge-m3", "input": ["oi", "mais longo"]}]


def test_embed_batch_empty_list_does_not_call_client():
    fake = _FakeOllamaClient()
    provider = OllamaEmbeddingProvider(client=fake)

    assert provider.embed_batch([]) == []
    assert fake.calls == []


def test_embed_single_text_delegates_to_embed_batch():
    fake = _FakeOllamaClient()
    provider = OllamaEmbeddingProvider(client=fake)

    assert provider.embed("oi") == [2.0, 2.0, 2.0]


def test_uses_embedding_model_from_settings_by_default(monkeypatch):
    monkeypatch.setattr(config.settings, "EMBEDDING_MODEL", "outro-modelo")
    fake = _FakeOllamaClient()

    provider = OllamaEmbeddingProvider(client=fake)
    provider.embed("teste")

    assert fake.calls[0]["model"] == "outro-modelo"


def test_explicit_model_overrides_settings(monkeypatch):
    monkeypatch.setattr(config.settings, "EMBEDDING_MODEL", "outro-modelo")
    fake = _FakeOllamaClient()

    provider = OllamaEmbeddingProvider(model="bge-m3", client=fake)
    provider.embed("teste")

    assert fake.calls[0]["model"] == "bge-m3"


def test_client_failure_raises_embedding_provider_error():
    provider = OllamaEmbeddingProvider(client=_FailingOllamaClient())

    with pytest.raises(EmbeddingProviderError):
        provider.embed("oi")


def test_missing_ollama_package_raises_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "ollama", None)

    with pytest.raises(EmbeddingProviderError):
        OllamaEmbeddingProvider()


def test_default_host_is_explicit_regardless_of_ambient_env(monkeypatch):
    """
    Regressão de um bug real, encontrado testando manualmente: se a
    variável de ambiente OLLAMA_HOST do sistema estiver como
    "0.0.0.0:11434" (configuração comum pra aceitar conexão de outros
    dispositivos), a biblioteca `ollama` usa esse valor como endereço de
    DESTINO por padrão — e "0.0.0.0" não é um endereço que um cliente
    consiga usar pra conectar, só um servidor pra escutar. Resultado era
    ConnectionError mesmo com o Ollama rodando normalmente. Este teste
    garante que `OllamaEmbeddingProvider` sempre passa um host explícito
    pro `ollama.Client(...)`, nunca deixando a decisão pra variável de
    ambiente do sistema.

    `settings.OLLAMA_HOST` é fixado aqui via monkeypatch, não deixado no
    valor real do singleton global: desde que `.env` passou a ser
    suportado (ver mcp_server/config.py), um `.env` real de deploy (modo
    "lan", host de LAN de verdade) legitimamente sobrescreve o default —
    e esse não é o comportamento que este teste específico verifica. O
    que importa aqui é só "o que está em settings.OLLAMA_HOST é passado
    explícito pro Client", não "qual é o valor de settings.OLLAMA_HOST
    nesta máquina".
    """
    monkeypatch.setattr(config.settings, "OLLAMA_HOST", "http://127.0.0.1:11434")
    fake_module = _FakeOllamaModule()
    monkeypatch.setitem(sys.modules, "ollama", fake_module)

    OllamaEmbeddingProvider()

    assert fake_module.client_kwargs == {"host": "http://127.0.0.1:11434"}
