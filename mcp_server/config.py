# mcp_server/config.py
#
# REPO_ROOT é calculado por padrão a partir da posição deste arquivo no
# disco (uma pasta acima: mcp_server/ -> raiz do moto_mcp). Este
# pacote vive na RAIZ do repositório — moto_mcp não tem uma subpasta
# "servidor", o repositório inteiro é o projeto Python (pyproject.toml
# também na raiz). Isso é proposital: o moto_mcp é genérico e feito pra
# ser compartilhado — não deve depender de um caminho absoluto de uma
# máquina específica.
#
# Suporte a arquivo .env (reintroduzido 2026-09-16): tinha sido
# removido de propósito quando a única coisa configurável era
# REPO_ROOT (nenhum cenário real pra sobrescrever isso). Deixou de ser
# verdade com o modo de rede — NETWORK_HOST/NETWORK_MODE/AUTH_TOKEN são
# configuração real que precisa persistir entre sessões de terminal, e
# reexportar isso toda vez (especialmente um token) é fricção real e
# risco de erro de digitação. `.env` fica fora do git (`.gitignore`) —
# nunca committar segredo; `.env.example` é o modelo sem segredo. Se
# `.env` não existir, tudo continua funcionando só com variável de
# ambiente direta, como sempre foi — nada quebra pra quem não usa.

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_vector_db_path() -> Path:
    # Mesma lógica de auto-localização do REPO_ROOT (ver comentário no
    # topo do arquivo) — não depende de nenhum caminho absoluto de
    # máquina específica.
    return Path(__file__).resolve().parents[1] / ".vector_index"


class Settings(BaseSettings):
    """
    Configuração do servidor MCP que expõe o próprio moto_mcp.

    Nenhum segredo vive aqui — este serviço só lê/escreve arquivos de
    texto dentro do próprio repositório, num subconjunto de pastas
    explicitamente permitido (ver WRITABLE_PREFIXES).
    """

    model_config = SettingsConfigDict(
        env_prefix="MOTO_MCP_",
        case_sensitive=True,
        extra="ignore",
        # Caminho absoluto (raiz do repo, mesma lógica de
        # _default_repo_root() abaixo) — não relativo ao cwd de quem
        # roda o comando, senão rodar de fora da raiz do repositório
        # faria o .env não ser encontrado silenciosamente.
        env_file=_default_repo_root() / ".env",
        env_file_encoding="utf-8",
    )

    REPO_ROOT: Path = Field(default_factory=_default_repo_root)

    # Extensões que este servidor está disposto a ler. Deliberadamente
    # restrito a texto/documentação — nunca serve binários, nem
    # arquivos de config que possam ter segredo (mesmo que o .gitignore
    # do repositório já devesse excluir isso).
    READABLE_EXTENSIONS: list[str] = Field(default=[".md", ".txt"])

    # Pastas (relativas à raiz do repo) onde ESCRITA é permitida por
    # este servidor. Tudo fora disso — global/, agents/, knowledge/,
    # templates/, handoff/, os arquivos-ponte na raiz (CLAUDE.md,
    # AGENTS.md etc.) — é só leitura por aqui, de propósito: um agente
    # conectado neste MCP não deve conseguir reescrever as próprias
    # regras/comportamento através dele. Ver docs/mcp_server.md,
    # "Modelo de segurança".
    #
    # `profile/` é a exceção deliberada a essa regra: não guarda regra
    # de comportamento do agente, guarda dado SOBRE o usuário (perfil,
    # estilo de trabalho, preferências) — natureza diferente de
    # `global/rules_absolute.md` e companhia. Faz sentido o próprio
    # agente atualizar isso via replace_section/append_to_section (ex:
    # "Mike, anota que eu prefiro respostas diretas"), então é
    # deliberadamente gravável, ao contrário do resto de fora de
    # projects/clients. Movido de `global/user_profile.md` pra cá por
    # causa exatamente disso — ver profile/profile.md.
    WRITABLE_PREFIXES: list[str] = Field(default=["projects", "clients", "profile"])

    # Pastas nunca listadas/lidas, mesmo que tecnicamente dentro do
    # repo (controle de versão, caches, ambientes virtuais). ".vector_index"
    # entrou junto com o VECTOR_DB_PATH abaixo — é dado gerado (arquivos
    # binários do LanceDB), não conteúdo pra listar/ler/buscar como os
    # outros .md/.txt do repositório.
    IGNORED_DIR_NAMES: list[str] = Field(
        default=[".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".vector_index"]
    )

    # Modelo de embedding usado pela busca semântica (ver
    # knowledge/vector-search/). Servido localmente via Ollama — nenhuma
    # chamada sai da máquina. Trocável por variável de ambiente
    # (MOTO_MCP_EMBEDDING_MODEL) sem tocar em código, desde que o modelo
    # novo já esteja baixado (`ollama pull <modelo>`).
    EMBEDDING_MODEL: str = Field(default="bge-m3")

    # Endereço do Ollama. Default explícito (não deixamos o cliente Ollama
    # decidir sozinho) por causa de um problema real encontrado em teste
    # manual: se a variável de ambiente OLLAMA_HOST estiver configurada
    # como "0.0.0.0:porta" (comum quando o Ollama foi configurado pra
    # aceitar conexão de outros dispositivos na rede), a biblioteca Python
    # do Ollama usa esse mesmo valor como endereço de DESTINO — e
    # "0.0.0.0" não é um endereço válido pra um cliente se conectar, só
    # pro servidor escutar. Resultado: ConnectionError, mesmo com o Ollama
    # rodando normalmente (confirmável em http://localhost:11434). Por
    # isso este servidor sempre usa um valor explícito e seguro por
    # padrão, em vez de herdar essa variável de ambiente.
    OLLAMA_HOST: str = Field(default="http://127.0.0.1:11434")

    # Dimensão do vetor de embedding — 1024 pro bge-m3. O LanceDB fixa
    # isso no schema da tabela no momento da criação (ver
    # mcp_server/vectorstore.py); se trocar de modelo de embedding, essa
    # dimensão também precisa mudar, e a tabela precisa ser recriada do
    # zero (reindexação completa — ver knowledge/vector-search/, "mesmo
    # modelo, não só mesma dimensão").
    EMBEDDING_DIMENSIONS: int = Field(default=1024)

    # Onde o LanceDB guarda os arquivos do índice vetorial. Fica fora de
    # todas as pastas de conteúdo (não é projects/, clients/, knowledge/
    # etc.) e é dado gerado, não fonte — por isso está em
    # IGNORED_DIR_NAMES acima e deveria estar no .gitignore.
    VECTOR_DB_PATH: Path = Field(default_factory=_default_vector_db_path)

    # Endereço/porta do modo de rede (transporte streamable-http,
    # mcp_server/server_network.py) — modo opcional, ao lado do stdio,
    # pra outro dispositivo (fora desta máquina) se conectar. Sem
    # padrão de propósito: NETWORK_HOST vazio força configuração
    # explícita via MOTO_MCP_NETWORK_HOST (o IP da interface do
    # Tailscale, formato 100.x.x.x) em vez de adivinhar ou cair num
    # default que poderia expor a porta sem querer. Validado por
    # mcp_server.network.ensure_safe_bind_host antes de subir o
    # servidor — nunca aceita "0.0.0.0"/"::"/endereço fora da faixa do
    # Tailscale (100.64.0.0/10). Ver docs/mcp_server.md, "Transporte de
    # rede".
    NETWORK_HOST: str = Field(default="")
    NETWORK_PORT: int = Field(default=8765)

    # Qual fronteira de rede o modo de rede aceita — "tailscale" (padrão,
    # só IP da faixa 100.64.0.0/10), "lan" (rede local/doméstica,
    # 10.0.0.0/8 + 172.16.0.0/12 + 192.168.0.0/16) ou "local" (só
    # 127.0.0.1/::1, mesma máquina). Ver mcp_server/network.py pra a
    # validação de verdade — este campo só seleciona qual regra usar.
    # Padrão "tailscale" de propósito: é a fronteira com autenticação de
    # dispositivo de verdade (WireGuard); mudar pra "lan" é escolha
    # explícita do usuário, não default.
    NETWORK_MODE: str = Field(default="tailscale")

    # Token Bearer opcional (obrigatório em modo "lan" — ver
    # mcp_server/network.py, ensure_safe_bind_host). Tailscale já
    # autentica o dispositivo; LAN não autentica nada sozinha, então
    # exige isso pra não virar acesso livre pra qualquer coisa na rede
    # de casa. Nunca tem valor padrão — precisa ser gerado e setado
    # explicitamente (ex: `python -c "import secrets;
    # print(secrets.token_hex(32))"`).
    AUTH_TOKEN: str = Field(default="")

    # Base URL da instância própria de SearXNG (ver docker-compose.yml
    # na raiz — serviço `searxng`, standalone, não a instância do
    # projeto n8n do usuário) usada pela tool search_web. Diferente do
    # Ollama, não tem raciocínio de "0.0.0.0 quebra o cliente" aqui —
    # SearXNG é só um HTTP GET comum, sem biblioteca cliente especial.
    SEARXNG_BASE_URL: str = Field(default="http://127.0.0.1:8080")


settings = Settings()
