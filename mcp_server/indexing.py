# mcp_server/indexing.py
#
# (Re)indexação do repositório no banco vetorial.
#
# Não existem duas versões separadas "indexação inicial" e "reindexação
# incremental" — é o MESMO algoritmo, descrito em
# knowledge/vector-search/embeddings-e-busca-semantica.md (seção 7): a
# primeira vez que roda, o índice (`store.list_indexed()`) está vazio,
# então todo chunk conta como "novo" e é upsertado; nas vezes seguintes,
# só o que mudou de verdade (comparado por `content_hash`, não mtime) é
# reprocessado. Por isso uma função só, chamável a qualquer momento,
# cobre os dois itens do to-do.md ("escrever a indexação inicial" e
# "reindexação incremental").
#
# `reindex()` recebe `store`/`embedder` já prontos (injeção de
# dependência, mesmo padrão de mcp_server/vectorstore.py e
# mcp_server/embeddings.py) — não instancia LanceDBVectorStore nem
# OllamaEmbeddingProvider aqui dentro. Isso mantém este módulo testável
# com fakes, sem precisar do pacote `lancedb` nem de um Ollama rodando
# (ver tests/test_indexing.py). Quem monta as instâncias de verdade é o
# script de linha de comando (scripts/reindex.py).

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from mcp_server import documents
from mcp_server.embeddings import EmbeddingProvider
from mcp_server.errors import DocumentNotFoundError
from mcp_server.vectorstore import VectorStore

# Raízes escaneadas por padrão: "" = a raiz do repositório inteira,
# recursivamente. Decisão revista — a primeira versão deste módulo
# limitava a knowledge/+projects/+clients/, copiando sem questionar o
# raciocínio de Settings.WRITABLE_PREFIXES (que protege agents/+global/
# contra ESCRITA por um agente conectado via MCP). Mas proteção contra
# escrita não tem nada a ver com fazer sentido estar no índice de
# BUSCA — um teste manual real (perguntar "quem é o Bill" e não achar
# `agents/bill.md`, que nem estava indexado) expôs esse erro. moto_mcp é
# "base de conhecimento e time de agentes" (README.md) — o índice
# precisa cobrir o repositório inteiro, personas incluídas, não só uma
# fatia dele.
#
# `documents.list_entries("", recursive=True)` já resolve isso sozinho,
# reusando a mesma lógica testada em test_documents.py: pula pastas
# ignoradas (`.git`, `.venv`, `.vector_index` — o próprio índice não se
# autoindexar —, etc.) e qualquer dotfile/dotdir, e filtra por
# `READABLE_EXTENSIONS` (só .md/.txt — nunca código, nunca binário). Não
# precisa mais listar pasta por pasta.
DEFAULT_ROOTS: tuple[str, ...] = ("",)

# Categoria usada pra chunks de arquivos soltos na raiz do repositório
# (AGENTS.md, CLAUDE.md, README.md, to-do.md...) — esses `entry.path`
# não têm "/" (não vêm de dentro de nenhuma pasta), então não há um
# primeiro segmento de path que sirva de categoria.
ROOT_CATEGORY = "(raiz)"


@dataclass
class IndexingReport:
    """Resultado de uma chamada a `reindex()` — o que mudou, não o
    estado inteiro do índice (que já está em `store.list_indexed()`)."""

    upserted: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: int = 0

    @property
    def total_current(self) -> int:
        """Quantos chunks existem no índice depois desta chamada (os que
        mudaram/foram criados agora + os que já estavam certos)."""
        return len(self.upserted) + self.unchanged


def _content_hash(body: str) -> str:
    """sha256 do corpo do chunk — ver seção 7 do doc de embeddings pra o
    raciocínio completo de por que é hash de conteúdo por chunk, não
    mtime nem hash do arquivo inteiro."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _current_chunks(roots: tuple[str, ...]) -> dict[str, dict]:
    """
    Varre as raízes indicadas (recursivamente) e monta o estado ATUAL do
    repositório em disco: chunk_id -> {path, section, category,
    content_hash, body}.

    `category` é derivado do próprio `entry.path` (primeiro segmento —
    ex: "knowledge/x.md" -> "knowledge"), não da raiz escaneada — assim
    bate exatamente com a definição da seção 7 do doc de embeddings, e
    continua correto mesmo se `roots` tiver mais de uma entrada ou uma
    raiz aninhada dentro de outra (sem risco de um chunk "roubar" a
    categoria errada por causa de qual raiz foi escaneada primeiro).

    `body` só existe pra uso interno (é o texto que vai pro embedder) —
    não é um dos campos da metadata definidos na seção 7 (esses são
    montados em `reindex()`, na hora do upsert).
    """
    chunks: dict[str, dict] = {}
    for root in roots:
        try:
            entries = documents.list_entries(root, recursive=True)
        except DocumentNotFoundError:
            # Raiz que ainda não existe neste repositório (ex: um fork
            # do moto_mcp que apagou uma pasta opcional) — não é erro,
            # só não há nada pra indexar ali.
            continue

        for entry in entries:
            if entry.type != "file":
                continue

            text = documents.read_text(entry.path)
            for section, body in documents.split_sections(text).items():
                if not body.strip():
                    # Cabeçalho sem corpo (ex: dois "## " seguidos, ou só
                    # espaço em branco) não vira chunk — não há texto pra
                    # gerar embedding.
                    continue

                chunk_id = f"{entry.path}#{section}"
                category = entry.path.split("/", 1)[0] if "/" in entry.path else ROOT_CATEGORY
                chunks[chunk_id] = {
                    "path": entry.path,
                    "section": section,
                    "category": category,
                    "content_hash": _content_hash(body),
                    "body": body,
                }
    return chunks


def reindex(
    store: VectorStore,
    embedder: EmbeddingProvider,
    *,
    categories: tuple[str, ...] = DEFAULT_ROOTS,
) -> IndexingReport:
    """
    Compara o estado atual do repositório (`_current_chunks`) contra o
    que já está no `store` (`list_indexed()`) e aplica só a diferença:

    - chunk novo, ou com `content_hash` diferente do salvo -> gera
      embedding e `upsert`.
    - chunk que sumiu (arquivo apagado, seção removida/renomeada) ->
      `delete`.
    - chunk igual (mesmo `content_hash`) -> não faz nada, nem chama o
      embedder — é o passo caro que este algoritmo existe pra evitar.

    Os embeddings são gerados em lote (`embed_batch`), não um por um —
    ver docstring de `EmbeddingProvider.embed_batch`.
    """
    report = IndexingReport()
    current = _current_chunks(categories)
    indexed = store.list_indexed()

    to_embed_ids = [
        chunk_id
        for chunk_id, chunk in current.items()
        if chunk_id not in indexed or indexed[chunk_id].get("content_hash") != chunk["content_hash"]
    ]
    report.unchanged = len(current) - len(to_embed_ids)

    if to_embed_ids:
        bodies = [current[chunk_id]["body"] for chunk_id in to_embed_ids]
        vectors = embedder.embed_batch(bodies)
        indexed_at = datetime.now(timezone.utc).isoformat()

        for chunk_id, vector in zip(to_embed_ids, vectors):
            chunk = current[chunk_id]
            metadata = {
                "path": chunk["path"],
                "section": chunk["section"],
                "category": chunk["category"],
                "content_hash": chunk["content_hash"],
                "indexed_at": indexed_at,
            }
            store.upsert(chunk_id, vector, chunk["body"], metadata)
            report.upserted.append(chunk_id)

    stale_ids = [chunk_id for chunk_id in indexed if chunk_id not in current]
    for chunk_id in stale_ids:
        store.delete(chunk_id)
        report.deleted.append(chunk_id)

    return report
