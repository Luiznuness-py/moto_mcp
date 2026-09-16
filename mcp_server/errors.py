# mcp_server/errors.py


class FrameworkServerError(Exception):
    """Base de todas as exceções deste servidor."""


class PathOutsideRepoError(FrameworkServerError):
    """O caminho pedido resolve pra fora da raiz do repositório (ou passa
    por uma pasta ignorada, como .git/.venv)."""


class PathNotWritableError(FrameworkServerError):
    """O caminho pedido não está numa pasta com permissão de escrita
    (ver Settings.WRITABLE_PREFIXES)."""


class UnsupportedExtensionError(FrameworkServerError):
    """A extensão do arquivo não está em Settings.READABLE_EXTENSIONS."""


class DocumentNotFoundError(FrameworkServerError):
    """Arquivo não existe no caminho pedido."""


class EntryAlreadyExistsError(FrameworkServerError):
    """Já existe um projeto/cliente com esse slug — passe overwrite=True
    pra sobrescrever de propósito."""


class TemplateNotFoundError(FrameworkServerError):
    """O template (_TEMPLATE.md) esperado não foi encontrado em
    projects/ ou clients/."""


class SectionNotFoundError(FrameworkServerError):
    """A seção markdown ('## <nome>') pedida não existe no documento."""


class EmbeddingProviderError(FrameworkServerError):
    """Falha ao gerar embedding (provedor não instalado, Ollama fora do
    ar, modelo não baixado, etc.)."""


class VectorStoreError(FrameworkServerError):
    """Falha no banco vetorial (pacote não instalado, tabela corrompida,
    etc.)."""


class WebSearchError(FrameworkServerError):
    """Falha ao consultar o SearXNG (instância fora do ar, resposta
    inesperada, etc.)."""


class UnsafeBindHostError(FrameworkServerError):
    """O host/config do modo de rede (streamable-http) não bate com a
    fronteira do modo escolhido (Settings.NETWORK_MODE:
    "tailscale"/"lan"/"local") — inclui host vazio, wildcard
    ("0.0.0.0"/"::"), host fora da faixa do modo, modo inválido, ou
    (em modo "lan") token de autenticação ausente/curto demais. Ver
    mcp_server/network.py, ensure_safe_bind_host."""
