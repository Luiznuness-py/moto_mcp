"""LanceDB isolado; SQLite mantém uma cópia durável para o fallback."""
from __future__ import annotations

import atexit
import json
import multiprocessing
import os
import queue
import signal
import sys
import time
from pathlib import Path
from threading import RLock

from mcp_server.errors import VectorStoreError
from mcp_server.vectorstore import SQLiteVectorStore


def _run_worker(requests, responses, db_path, table_name, dimensions, import_legacy):
    # Bibliotecas nativas não podem escrever no stdout do transporte MCP.
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    if os.name == "posix":
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        from mcp_server._lancedb import LanceDBVectorStore
        native = LanceDBVectorStore(db_path, table_name, dimensions)
        mirror = SQLiteVectorStore(db_path, table_name, dimensions)
        if import_legacy:
            # Uma transação evita deixar uma migração parcial após SIGILL.
            with mirror._connection() as db:
                for row in native._table.to_arrow().to_pylist():
                    vector = mirror._normalize(row["vector"])
                    metadata = json.loads(row["metadata_json"])
                    db.execute(f'INSERT OR IGNORE INTO "{mirror._table}" VALUES (?, ?, ?, ?)',
                               (row["id"], json.dumps(vector), row["text"], json.dumps(metadata, ensure_ascii=False, allow_nan=False)))
        with mirror._connection() as db:
            db.execute("INSERT OR REPLACE INTO vector_fallback_state VALUES (?, 1)", (mirror._table,))
        indexed = native.list_indexed()
        current = mirror.list_indexed()
        # shortcut: Reconciliação em memória; usar lotes para índices grandes.
        with mirror._connection() as db:
            rows = [{"id": chunk_id, "vector": json.loads(vector), "text": text, "metadata_json": metadata}
                    for chunk_id, vector, text, metadata in db.execute(f'SELECT id, vector, text, metadata_json FROM "{mirror._table}"')]
        if rows:
            native._table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(rows)
        for chunk_id in indexed.keys() - current.keys():
            native.delete(chunk_id)
        responses.put((True, None))
        while True:
            method, args, kwargs = requests.get()
            if method not in {"upsert", "delete", "search", "list_indexed", "compact"}:
                raise ValueError("Operação vetorial desconhecida")
            try:
                result = getattr(native, method)(*args, **kwargs)
                responses.put((True, result))
            except Exception as exc:
                responses.put((False, f"{type(exc).__name__}: {exc}"))
    except Exception as exc:
        responses.put((False, f"{type(exc).__name__}: {exc}"))


class AutomaticVectorStore:
    """Grava primeiro em SQLite e prefere leituras no processo LanceDB."""

    _timeout = 30.0

    def __init__(self, db_path=None, table_name="chunks", dimensions=None):
        from mcp_server.config import settings
        directory = Path(db_path or settings.VECTOR_DB_PATH)
        # Um índice SQLite existente é a fonte atual; não ressuscitar exclusões.
        import_legacy = not (directory / "vectors.sqlite3").exists()
        self._sqlite = SQLiteVectorStore(str(directory), table_name, dimensions)
        with self._sqlite._connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS vector_fallback_state (name TEXT PRIMARY KEY, initialized INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO vector_fallback_state VALUES (?, ?)", (self._sqlite._table, int(not import_legacy)))
            import_legacy = not db.execute("SELECT initialized FROM vector_fallback_state WHERE name = ?", (self._sqlite._table,)).fetchone()[0]
        self._lock = RLock()
        self._process = None
        self._requests = self._responses = None
        self.backend = "sqlite"
        self.failure_reason = None
        context = multiprocessing.get_context("spawn")
        try:
            self._requests = context.Queue()
            self._responses = context.Queue()
            self._process = context.Process(target=_run_worker,
                args=(self._requests, self._responses, str(directory), self._sqlite._table,
                      self._sqlite._dimensions, import_legacy), daemon=True, name="lancedb-index")
            self._process.start()
            self._receive()
            self.backend = "lancedb"
        except (OSError, RuntimeError, AssertionError, VectorStoreError) as exc:
            self._fallback(exc)
        if self.backend == "lancedb":
            atexit.register(self.close)

    def _receive(self):
        deadline = time.monotonic() + self._timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise VectorStoreError("Tempo limite de resposta do LanceDB excedido")
            try:
                ok, value = self._responses.get(timeout=min(0.1, remaining))
                if not ok:
                    raise VectorStoreError(value)
                return value
            except queue.Empty:
                if not self._process.is_alive():
                    self._process.join(timeout=0.1)
                    code = self._process.exitcode
                    name = "saída inesperada"
                    if os.name == "posix" and code < 0:
                        name = "SIGILL" if code == -signal.SIGILL else signal.strsignal(-code)
                    raise VectorStoreError(f"Processo LanceDB encerrou com código {code} ({name})")

    def _native(self, method, *args, **kwargs):
        self._requests.put((method, args, kwargs))
        return self._receive()

    def _fallback(self, exc):
        self.failure_reason = str(exc)
        self.backend = "sqlite"
        self.close()
        print(f"[moto_mcp] LanceDB falhou ({exc}); usando SQLite nesta sessão.", file=sys.stderr)

    def close(self):
        atexit.unregister(self.close)
        with self._lock:
            if self._process is not None:
                if self._process.is_alive():
                    self._process.terminate()
                    self._process.join(timeout=1)
                    if self._process.is_alive():
                        self._process.kill()
                        self._process.join(timeout=1)
                self._process = None
            for channel in (self._requests, self._responses):
                if channel is not None:
                    channel.cancel_join_thread()
                    channel.close()
            self._requests = self._responses = None
            self.backend = "sqlite"

    def _write(self, method, *args, **kwargs):
        with self._lock:
            getattr(self._sqlite, method)(*args, **kwargs)
            if method in {"upsert", "delete"}:
                with self._sqlite._connection() as db:
                    db.execute("UPDATE vector_fallback_state SET initialized = 1 WHERE name = ?", (self._sqlite._table,))
            if self.backend == "lancedb":
                try:
                    self._native(method, *args, **kwargs)
                except (OSError, ValueError, VectorStoreError) as exc:
                    self._fallback(exc)

    def upsert(self, chunk_id, vector, text, metadata):
        self._write("upsert", chunk_id, vector, text, metadata)

    def delete(self, chunk_id):
        self._write("delete", chunk_id)

    def compact(self, *, older_than_days=None):
        self._write("compact", older_than_days=older_than_days)

    def _read(self, method, *args, **kwargs):
        with self._lock:
            if self.backend == "lancedb":
                try:
                    return self._native(method, *args, **kwargs)
                except (OSError, ValueError, VectorStoreError) as exc:
                    self._fallback(exc)
            return getattr(self._sqlite, method)(*args, **kwargs)

    def list_indexed(self):
        return self._read("list_indexed")

    def search(self, query_vector, top_k=5):
        query = self._sqlite._normalize(query_vector)
        if not isinstance(top_k, int) or top_k <= 0:
            raise VectorStoreError("top_k deve ser um inteiro positivo.")
        return self._read("search", query, top_k=top_k)
