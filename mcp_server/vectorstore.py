# mcp_server/vectorstore.py
#
# Contrato de banco vetorial + adaptador para o LanceDB.
#
# Mesma lógica de mcp_server/embeddings.py: isola completamente a escolha
# do banco vetorial (hoje: LanceDB, embarcado, sem servidor separado) do
# resto do código (indexação, busca). Trocar de banco — o próximo passo
# planejado é validar Postgres/pgvector, ver to-do.md — significa escrever
# um novo adaptador que implemente VectorStore. Nada além disso deveria
# precisar mudar. Ver knowledge/vector-search/ para o raciocínio completo
# por trás dessas decisões (por que cosseno, por que chunk_id estável,
# etc.).

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from mcp_server.errors import VectorStoreError


@dataclass
class SearchResult:
    chunk_id: str
    text: str
    metadata: dict
    # Similaridade de cosseno do chunk com a busca: 1 = idêntico, 0 = sem
    # relação, -1 = sentido oposto (ver knowledge/vector-search/,
    # "Métricas de similaridade").
    score: float


@runtime_checkable
class VectorStore(Protocol):
    """Contrato que qualquer banco vetorial precisa cumprir."""

    def upsert(self, chunk_id: str, vector: list[float], text: str, metadata: dict) -> None:
        """Grava ou atualiza um chunk. `chunk_id` precisa ser estável e
        determinístico (ex: derivado do caminho do arquivo + nome da
        seção) — reprocessar o mesmo chunk sobrescreve o registro
        existente, nunca duplica."""

    def delete(self, chunk_id: str) -> None:
        """Remove um chunk do índice (ex: seção apagada/renomeada na
        reindexação incremental)."""

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        """Devolve os `top_k` chunks mais parecidos com `query_vector`,
        ordenados do mais parecido pro menos parecido."""

    def list_indexed(self) -> dict[str, dict]:
        """Devolve {chunk_id: metadata} de tudo que já está no índice —
        usado pela reindexação incremental pra comparar contra o estado
        atual dos arquivos (hash/mtime guardado na metadata) e decidir o
        que precisa ser reprocessado."""

    def compact(self, *, older_than_days: int | None = None) -> None:
        """
        Manutenção do backend — libera espaço/organiza o índice sem mudar
        os dados atuais. Sentido exato depende do adaptador (no LanceDB:
        compacta fragmentos pequenos e apaga versões antigas do histórico
        interno — ver knowledge/vector-search/, comentário sobre
        .lance/.manifest/.txn; num backend tipo Postgres/pgvector,
        poderia ser um VACUUM, ou nem existir de verdade). Seguro de
        chamar a qualquer momento — nunca apaga o chunk mais recente de
        nada, só histórico/fragmentação interna. `older_than_days=None`
        usa o padrão do adaptador."""


class LanceDBVectorStore:
    """
    Adaptador para o LanceDB — embarcado, sem servidor separado, guarda os
    dados como arquivos locais em `db_path` (padrão:
    Settings.VECTOR_DB_PATH).

    Cada chunk vira uma linha com: `id` (chave, usada pelo merge_insert
    pra fazer upsert de verdade — atualiza se já existe, insere se não),
    `vector` (tamanho fixo, Settings.EMBEDDING_DIMENSIONS — precisa bater
    com o modelo de embedding em uso), `text` (o conteúdo do chunk) e
    `metadata_json` (metadata serializado como JSON — Arrow/LanceDB não
    tem um tipo "dict solto" simples de schema variável, então
    serializamos pra string e desserializamos na leitura).

    A busca usa métrica de cosseno explicitamente (`.metric("cosine")`) —
    não é o padrão do LanceDB (que é distância euclidiana), e cosseno foi
    a métrica decidida (ver knowledge/vector-search/). O `_distance` que o
    LanceDB devolve pra métrica de cosseno é `1 - similaridade`, não a
    similaridade em si — por isso `search()` converte de volta
    (`score = 1 - _distance`) antes de devolver, pra bater com a
    convenção de "1 = idêntico" usada no resto do projeto.
    """

    def __init__(
        self,
        db_path: str | None = None,
        table_name: str = "chunks",
        dimensions: int | None = None,
    ) -> None:
        from mcp_server.config import settings

        try:
            import lancedb
            from lancedb.pydantic import LanceModel, Vector
        except ImportError as exc:
            raise VectorStoreError(
                "Pacote 'lancedb' não instalado. Ver "
                "knowledge/vector-search/dependencias.md (`poetry add lancedb`)."
            ) from exc

        self._dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
        effective_path = str(db_path or settings.VECTOR_DB_PATH)

        # Definido dinamicamente porque a dimensão do vetor (Vector(dim=...))
        # precisa ser conhecida na hora de montar o schema — não dá pra
        # fixar num tipo estático no topo do arquivo, já que é
        # configurável (Settings.EMBEDDING_DIMENSIONS).
        class Chunk(LanceModel):
            id: str
            vector: Vector(self._dimensions)
            text: str
            metadata_json: str

        self._schema = Chunk

        db = lancedb.connect(effective_path)
        # `table_name in db` (Connection.__contains__), não
        # `db.table_names()`/`db.list_tables()`: ambos são paginados (10
        # tabelas por padrão) e um repositório com mais de 10 tabelas
        # faria essa checagem dar falso-negativo — recriando uma tabela
        # que já existe. `in db` resolve a paginação por baixo,
        # corretamente, sem essa pegadinha (e de quebra não gera o
        # DeprecationWarning de table_names() estar obsoleto).
        if table_name in db:
            self._table = db.open_table(table_name)
        else:
            self._table = db.create_table(table_name, schema=Chunk)

    def upsert(self, chunk_id: str, vector: list[float], text: str, metadata: dict) -> None:
        """Grava ou atualiza a linha de `chunk_id` via `merge_insert` (
        upsert de verdade — nunca duplica uma chave já existente)."""
        row = {
            "id": chunk_id,
            "vector": vector,
            "text": text,
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
        }
        (
            self._table.merge_insert("id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute([row])
        )

    def delete(self, chunk_id: str) -> None:
        """Remove a linha de `chunk_id`. Não é erro deletar um id que não
        existe (predicado só não casa com nada)."""
        # Predicado é SQL-like (string), não parametrizado — escapa aspas
        # simples manualmente pra não quebrar se chunk_id tiver uma (ex:
        # derivado de um caminho/nome de seção com apóstrofo).
        escaped = chunk_id.replace("'", "''")
        self._table.delete(f"id = '{escaped}'")

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        """Busca por cosseno, ordenada do mais parecido pro menos (ver
        docstring da classe pra a conversão distância -> score)."""
        rows = self._table.search(query_vector).metric("cosine").limit(top_k).to_list()
        results = []
        for row in rows:
            distance = row.get("_distance", 0.0)
            results.append(
                SearchResult(
                    chunk_id=row["id"],
                    text=row["text"],
                    metadata=json.loads(row["metadata_json"]),
                    score=1.0 - distance,
                )
            )
        return results

    def list_indexed(self) -> dict[str, dict]:
        """Lê a tabela inteira (sem busca vetorial) e devolve
        {chunk_id: metadata}."""
        # to_pydict() em vez de to_pandas() de propósito — não depende de
        # pandas estar instalado, só do pyarrow que já vem com o lancedb.
        columns = self._table.to_arrow().to_pydict()
        ids = columns.get("id", [])
        metadata_jsons = columns.get("metadata_json", [])
        return {chunk_id: json.loads(metadata_json) for chunk_id, metadata_json in zip(ids, metadata_jsons)}

    def compact(self, *, older_than_days: int | None = None) -> None:
        """Chama `table.optimize()` do LanceDB — compacta fragmentos
        pequenos e apaga versões antigas do histórico interno (ver
        knowledge/vector-search/, comentário sobre .lance/.manifest/.txn).
        Não afeta o conteúdo atual, só o histórico/organização física dos
        arquivos em disco."""
        from datetime import timedelta

        if older_than_days is not None:
            self._table.optimize(cleanup_older_than=timedelta(days=older_than_days))
        else:
            # Padrão do próprio LanceDB (retém 7 dias de histórico de
            # versões antigas, compacta fragmentos pequenos).
            self._table.optimize()
