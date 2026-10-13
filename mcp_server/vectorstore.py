"""Contrato vetorial, SQLite e fábrica do LanceDB com fallback."""
from __future__ import annotations

import heapq
import json
import math
import re
import sqlite3
from threading import Lock
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
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


class SQLiteVectorStore:
    """Persistência local sem extensão vetorial; busca exata em todos os vetores."""

    def __init__(self, db_path: str | None = None, table_name: str = "chunks",
                 dimensions: int | None = None) -> None:
        from mcp_server.config import settings

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name) or table_name.lower() in {"vector_store_config", "vector_fallback_state"}:
            raise VectorStoreError("Nome de tabela inválido.")
        # SQLite identifica tabelas sem distinguir maiúsculas de minúsculas.
        table_name = table_name.lower()
        self._dimensions = settings.EMBEDDING_DIMENSIONS if dimensions is None else dimensions
        if not isinstance(self._dimensions, int) or self._dimensions <= 0:
            raise VectorStoreError("A dimensão deve ser um inteiro positivo.")
        self._table = table_name
        directory = Path(db_path or settings.VECTOR_DB_PATH)
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise VectorStoreError(f"Não foi possível criar o diretório do índice: {exc}") from exc
        # Arquivo separado preserva o índice LanceDB existente; reindexação cria o novo.
        self._path = directory / "vectors.sqlite3"
        with self._connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS vector_store_config (name TEXT PRIMARY KEY, dimensions INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO vector_store_config VALUES (?, ?)", (table_name, self._dimensions))
            dimension = db.execute("SELECT dimensions FROM vector_store_config WHERE name = ?", (table_name,)).fetchone()[0]
            if dimension != self._dimensions:
                raise VectorStoreError("Dimensão diferente da registrada no índice; use outro diretório e reindexe.")
            db.execute(f'CREATE TABLE IF NOT EXISTS "{self._table}" (id TEXT PRIMARY KEY, vector TEXT NOT NULL, text TEXT NOT NULL, metadata_json TEXT NOT NULL)')

    @contextmanager
    def _connection(self):
        try:
            db = sqlite3.connect(self._path, timeout=30)
            try:
                with db:
                    yield db
            finally:
                db.close()
        except sqlite3.Error as exc:
            raise VectorStoreError(f"Falha no índice SQLite: {exc}") from exc

    def _normalize(self, vector: list[float]) -> list[float]:
        if len(vector) != self._dimensions:
            raise VectorStoreError(f"Vetor deve ter {self._dimensions} dimensões.")
        try:
            values = [float(value) for value in vector]
            norm = math.hypot(*values)
        except (TypeError, ValueError, OverflowError) as exc:
            raise VectorStoreError("Vetor deve conter números finitos.") from exc
        if not all(math.isfinite(value) for value in values) or not math.isfinite(norm) or norm == 0:
            raise VectorStoreError("Vetor deve ser finito e ter norma não nula.")
        return [value / norm for value in values]

    def upsert(self, chunk_id: str, vector: list[float], text: str, metadata: dict) -> None:
        normalized = self._normalize(vector)
        with self._connection() as db:
            db.execute(f'INSERT INTO "{self._table}" VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET vector=excluded.vector, text=excluded.text, metadata_json=excluded.metadata_json',
                       (chunk_id, json.dumps(normalized, allow_nan=False), text, json.dumps(metadata, ensure_ascii=False, allow_nan=False)))

    def delete(self, chunk_id: str) -> None:
        with self._connection() as db:
            db.execute(f'DELETE FROM "{self._table}" WHERE id = ?', (chunk_id,))

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        if not isinstance(top_k, int) or top_k <= 0:
            raise VectorStoreError("top_k deve ser um inteiro positivo.")
        query = self._normalize(query_vector)
        with self._connection() as db:
            rows = db.execute(f'SELECT id, vector, text, metadata_json FROM "{self._table}" ORDER BY id')
            def results():
                for chunk_id, vector_json, text, metadata_json in rows:
                    vector = json.loads(vector_json)
                    score = math.fsum(a * b for a, b in zip(query, vector))
                    yield SearchResult(chunk_id, text, json.loads(metadata_json), max(-1.0, min(1.0, score)))
            return heapq.nlargest(top_k, results(), key=lambda result: result.score)

    def list_indexed(self) -> dict[str, dict]:
        with self._connection() as db:
            return {chunk_id: json.loads(metadata) for chunk_id, metadata in
                    db.execute(f'SELECT id, metadata_json FROM "{self._table}"')}

    def compact(self, *, older_than_days: int | None = None) -> None:
        """Libera espaço com VACUUM. SQLite não mantém histórico por idade."""
        if older_than_days is not None and older_than_days < 0:
            raise VectorStoreError("older_than_days não pode ser negativo.")
        with self._connection() as db:
            db.execute("VACUUM")


_factory_lock = Lock()
_default_store = None


def get_vector_store() -> VectorStore:
    """Compartilha um único processo LanceDB entre startup e ferramentas."""
    global _default_store
    with _factory_lock:
        if _default_store is None:
            from mcp_server.fallback import AutomaticVectorStore
            _default_store = AutomaticVectorStore()
        return _default_store
