"""Processos reais exercitam falha nativa, timeout e continuidade dos dados."""
import os
import signal
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from mcp_server import fallback
from mcp_server.errors import VectorStoreError
from mcp_server.vectorstore import VectorStore, SQLiteVectorStore


def healthy_worker(requests, responses, path, table, dimensions, legacy):
    store = SQLiteVectorStore(path + "-native-test", table, dimensions)
    mirror = SQLiteVectorStore(path, table, dimensions)
    with mirror._connection() as db:
        for chunk_id, vector, text, metadata in db.execute(f'SELECT * FROM "{table}"'):
            import json
            store.upsert(chunk_id, json.loads(vector), text, json.loads(metadata))
    for chunk_id in store.list_indexed().keys() - mirror.list_indexed().keys():
        store.delete(chunk_id)
    responses.put((True, None))
    while True:
        method, args, kwargs = requests.get()
        responses.put((True, getattr(store, method)(*args, **kwargs)))


def crash_at_start(*args):
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.kill(os.getpid(), signal.SIGILL)


def crash_on_request(requests, responses, *args):
    responses.put((True, None))
    requests.get()
    crash_at_start()


def error_on_request(requests, responses, *args):
    responses.put((True, None))
    requests.get()
    responses.put((False, "RuntimeError: falha de leitura"))


def hang_at_start(*args):
    time.sleep(60)


def hang_on_request(requests, responses, *args):
    responses.put((True, None))
    requests.get()
    time.sleep(60)


@pytest.fixture
def make_store(tmp_path, monkeypatch):
    stores = []
    def make(worker=healthy_worker, path=None):
        monkeypatch.setattr(fallback, "_run_worker", worker)
        store = fallback.AutomaticVectorStore(str(path or tmp_path / 'index'), dimensions=3)
        stores.append(store)
        return store
    yield make
    for store in stores:
        store.close()


def test_healthy_process_stays_alive_and_mirrors_every_operation(make_store):
    store = make_store()
    assert isinstance(store, VectorStore)
    assert store.backend == 'lancedb'
    process = store._process
    store.upsert("a'", [1, 0, 0], 'Olá', {'x': 1})
    store.upsert("a'", [0, 1, 0], 'Atualizado', {'x': 2})
    assert store.list_indexed() == {"a'": {'x': 2}}
    result = store.search([0, 1, 0])[0]
    assert result.text == 'Atualizado'
    assert result.score == pytest.approx(1)
    store.compact()
    assert store._sqlite.list_indexed() == store.list_indexed()
    store.delete("a'")
    assert store.search([1, 0, 0]) == []
    assert store._sqlite.list_indexed() == {}
    assert store._process is process and process.is_alive()
    store.close()
    assert not process.is_alive()


@pytest.mark.skipif(os.name != 'posix', reason='SIGILL test uses POSIX signal')
def test_sigill_at_start_falls_back_and_parent_survives(make_store, capsys):
    store = make_store(crash_at_start)
    assert store.backend == 'sqlite'
    assert '-4' in store.failure_reason
    assert 'usando SQLite' in capsys.readouterr().err
    store.upsert('a', [1, 0, 0], 'válido', {})
    assert store.search([1, 0, 0])[0].chunk_id == 'a'


@pytest.mark.parametrize('worker', [crash_on_request, error_on_request, hang_on_request])
def test_failure_during_write_keeps_committed_mirror(make_store, monkeypatch, worker):
    store = make_store(worker)
    monkeypatch.setattr(store, '_timeout', 0.3)
    store.upsert('a', [1, 0, 0], 'salvo antes da falha', {'x': 'ç'})
    assert store.backend == 'sqlite'
    assert store._process is None
    assert store.search([1, 0, 0])[0].text == 'salvo antes da falha'
    assert store.list_indexed() == {'a': {'x': 'ç'}}
    store.compact()
    store.delete('a')
    assert store.list_indexed() == {}


@pytest.mark.parametrize('worker', [crash_on_request, error_on_request, hang_on_request])
def test_failure_during_search_retries_same_query_on_sqlite(make_store, tmp_path, monkeypatch, worker):
    path = tmp_path / 'preexisting'
    SQLiteVectorStore(str(path), dimensions=3).upsert('a', [1, 0, 0], 'pré-existente', {})
    store = make_store(worker, path)
    monkeypatch.setattr(store, '_timeout', 0.3)
    assert store.search([1, 0, 0])[0].chunk_id == 'a'
    assert store.backend == 'sqlite'


def test_timeout_at_start_terminates_worker(make_store, monkeypatch):
    monkeypatch.setattr(fallback.AutomaticVectorStore, '_timeout', 0.3)
    store = make_store(hang_at_start)
    assert store.backend == 'sqlite'
    assert 'Tempo limite' in store.failure_reason
    assert store._process is None


def test_invalid_input_never_disables_healthy_worker(make_store):
    store = make_store()
    with pytest.raises(VectorStoreError):
        store.upsert('a', [0, 0, 0], '', {})
    with pytest.raises(VectorStoreError):
        store.search([1, 0, 0], top_k=0)
    with pytest.raises(VectorStoreError):
        store.compact(older_than_days=-1)
    assert store.backend == 'lancedb'


def test_concurrent_operations_and_restart_preserve_latest_vectors(make_store):
    store = make_store()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: store.upsert(str(i), [1, i, 1], str(i), {}), range(12)))
    assert len(store.list_indexed()) == 12
    store.close()
    # Mesmo metadata; alteração de vetor/texto durante fallback deve ser replicada.
    store.upsert('0', [0, 0, 1], 'novo', {})
    reopened = make_store()
    assert reopened.backend == 'lancedb'
    assert reopened.search([0, 0, 1])[0].text == 'novo'
    assert len(reopened.list_indexed()) == 12


def test_sqlite_failure_is_not_hidden(make_store, monkeypatch):
    store = make_store()
    def fail(*args):
        raise VectorStoreError('SQLite disco cheio')
    monkeypatch.setattr(store._sqlite, 'upsert', fail)
    with pytest.raises(VectorStoreError, match='disco cheio'):
        store.upsert('a', [1, 0, 0], '', {})
    assert store.backend == 'lancedb'


def test_factory_is_shared_between_callers(monkeypatch):
    from mcp_server import vectorstore, tools
    from unittest.mock import Mock
    expected = object()
    constructor = Mock(return_value=expected)
    monkeypatch.setattr(vectorstore, '_default_store', None)
    monkeypatch.setattr(fallback, 'AutomaticVectorStore', constructor)
    assert vectorstore.get_vector_store() is expected
    assert tools._vector_store() is expected
    constructor.assert_called_once()


def test_process_start_failure_falls_back(make_store, monkeypatch):
    from multiprocessing.process import BaseProcess
    def fail(*args):
        raise OSError('processo indisponível')
    monkeypatch.setattr(BaseProcess, 'start', fail)
    store = make_store()
    assert store.backend == 'sqlite'
    assert 'processo indisponível' in store.failure_reason
    store.upsert('a', [1, 0, 0], 'continua', {})
    assert store.list_indexed() == {'a': {}}


def test_dead_worker_during_delete_does_not_resurrect_on_restart(make_store):
    store = make_store()
    store.upsert('a', [1, 0, 0], 'apagado', {})
    process = store._process
    process.terminate()
    process.join(timeout=2)
    store.delete('a')
    assert store.backend == 'sqlite'
    reopened = make_store()
    assert reopened.list_indexed() == {}


def test_missing_package_falls_back(make_store, monkeypatch):
    def not_installed(*args):
        raise VectorStoreError("ImportError: Pacote 'lancedb' não instalado")
    monkeypatch.setattr(fallback.AutomaticVectorStore, '_receive', not_installed)
    store = make_store()
    assert store.backend == 'sqlite'
    assert 'não instalado' in store.failure_reason


class _ArrowRows:
    def __init__(self, rows):
        self.rows = rows
    def to_pylist(self):
        return self.rows


class _NativeTable:
    def __init__(self, store):
        self.store = store
    def to_arrow(self):
        import json
        with self.store._connection() as db:
            return _ArrowRows([{'id': i, 'vector': json.loads(v), 'text': t, 'metadata_json': m}
                               for i, v, t, m in db.execute('SELECT * FROM chunks')])
    def merge_insert(self, key):
        assert key == 'id'
        return self
    def when_matched_update_all(self):
        return self
    def when_not_matched_insert_all(self):
        return self
    def execute(self, rows):
        import json
        for row in rows:
            self.store.upsert(row['id'], row['vector'], row['text'], json.loads(row['metadata_json']))


class _NativeAdapter:
    """Simula a API LanceDB; persistência SQLite real, sem extensão nativa."""
    def __init__(self, path, table, dimensions):
        self.store = SQLiteVectorStore(path + '-adapter', table, dimensions)
        self._table = _NativeTable(self.store)
    def upsert(self, *args):
        return self.store.upsert(*args)
    def list_indexed(self):
        return self.store.list_indexed()
    def delete(self, *args):
        return self.store.delete(*args)


def _exercise_production_worker(monkeypatch, path, legacy):
    import sys
    import types
    import queue
    monkeypatch.setitem(sys.modules, 'mcp_server._lancedb', types.SimpleNamespace(LanceDBVectorStore=_NativeAdapter))
    monkeypatch.setattr(fallback.os, 'dup2', lambda *args: None)
    if os.name == 'posix':
        import resource
        monkeypatch.setattr(resource, 'setrlimit', lambda *args: None)
    requests, responses = queue.Queue(), queue.Queue()
    requests.put(('list_indexed', (), {}))
    requests.put(('unauthorized_operation', (), {}))
    fallback._run_worker(requests, responses, str(path), 'chunks', 3, legacy)
    return [responses.get_nowait() for _ in range(responses.qsize())]


def test_production_worker_migrates_legacy_vectors_without_embedding(tmp_path, monkeypatch):
    path = tmp_path / 'legacy'
    native = _NativeAdapter(str(path), 'chunks', 3)
    native.upsert("a'", [1, 0, 0], 'legado', {'é': True})
    monkeypatch.setattr(fallback, '_run_worker', hang_at_start)
    monkeypatch.setattr(fallback.AutomaticVectorStore, '_timeout', 0.1)
    setup = fallback.AutomaticVectorStore(str(path), dimensions=3)
    setup.close()
    monkeypatch.undo()
    responses = _exercise_production_worker(monkeypatch, path, True)
    assert responses[:2] == [(True, None), (True, {"a'": {'é': True}})]
    assert responses[-1][0] is False  # operação arbitrária foi rejeitada
    assert SQLiteVectorStore(str(path), dimensions=3).list_indexed() == {"a'": {'é': True}}


def test_production_worker_replays_sqlite_and_removes_stale_native_rows(tmp_path, monkeypatch):
    path = tmp_path / 'replay'
    native = _NativeAdapter(str(path), 'chunks', 3)
    native.upsert('obsolete', [1, 0, 0], 'antigo', {})
    monkeypatch.setattr(fallback, '_run_worker', hang_at_start)
    monkeypatch.setattr(fallback.AutomaticVectorStore, '_timeout', 0.1)
    setup = fallback.AutomaticVectorStore(str(path), dimensions=3)
    setup.upsert('a', [0, 1, 0], 'atual', {})
    setup.close()
    monkeypatch.undo()
    responses = _exercise_production_worker(monkeypatch, path, False)
    assert responses[:2] == [(True, None), (True, {'a': {}})]
    assert SQLiteVectorStore(str(path) + '-adapter', dimensions=3).list_indexed() == {'a': {}}


def test_production_worker_legacy_import_rolls_back_invalid_vectors(tmp_path, monkeypatch):
    path = tmp_path / 'invalid-legacy'
    native = _NativeAdapter(str(path), 'chunks', 3)
    native.upsert('valid', [1, 0, 0], 'válido', {})
    with native.store._connection() as db:
        db.execute('INSERT INTO chunks VALUES (?, ?, ?, ?)', ('invalid', '[0, 0, 0]', 'inválido', '{}'))
    monkeypatch.setattr(fallback, '_run_worker', hang_at_start)
    monkeypatch.setattr(fallback.AutomaticVectorStore, '_timeout', 0.1)
    setup = fallback.AutomaticVectorStore(str(path), dimensions=3)
    setup.close()
    monkeypatch.undo()
    responses = _exercise_production_worker(monkeypatch, path, True)
    assert len(responses) == 1 and not responses[0][0]
    mirror = SQLiteVectorStore(str(path), dimensions=3)
    assert mirror.list_indexed() == {}
    with mirror._connection() as db:
        assert db.execute('SELECT initialized FROM vector_fallback_state WHERE name="chunks"').fetchone() == (0,)
