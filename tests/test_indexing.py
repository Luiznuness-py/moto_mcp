# tests/test_indexing.py
#
# Testa mcp_server.indexing.reindex() com fakes de embedder e de banco
# vetorial — mesmo espírito de tests/test_embeddings.py (cliente Ollama
# falso): aqui não é o LanceDB nem o Ollama que estão sob teste (isso já
# é coberto por tests/test_vectorstore.py e tests/test_embeddings.py),
# é a ORQUESTRAÇÃO (o que reindex() decide upsertar/deletar/pular). Por
# isso um FakeVectorStore em memória é suficiente e correto aqui, mesmo
# test_vectorstore.py explicitamente não usando fake pra o adaptador
# real do LanceDB — camadas diferentes, filosofias de teste diferentes.
#
# Usa o fixture `fake_repo` (tests/conftest.py), acrescentando
# knowledge/ diretamente em cada teste (fake_repo não inclui essa pasta
# por padrão, e mudar o fixture compartilhado só pra isso arriscaria
# afetar os outros testes que já o usam).

from __future__ import annotations

from mcp_server.indexing import DEFAULT_ROOTS, ROOT_CATEGORY, reindex
from mcp_server.vectorstore import SearchResult


class _FakeEmbeddingProvider:
    """Vetor determinístico (tamanho do texto) — só precisa ser
    verificável, não precisa fazer sentido semanticamente (ver
    _FakeOllamaClient em test_embeddings.py, mesma ideia)."""

    def __init__(self):
        self.calls = []

    def embed(self, text):
        return self.embed_batch([text])[0]

    def embed_batch(self, texts):
        self.calls.append(list(texts))
        return [[float(len(text))] for text in texts]


class _FakeVectorStore:
    """Implementação mínima de VectorStore, em memória — só o suficiente
    pra reindex() funcionar e pra testes inspecionarem o que foi
    chamado."""

    def __init__(self):
        self._rows: dict[str, dict] = {}
        self.upsert_calls: list[str] = []
        self.delete_calls: list[str] = []

    def upsert(self, chunk_id, vector, text, metadata):
        self._rows[chunk_id] = {"vector": vector, "text": text, "metadata": metadata}
        self.upsert_calls.append(chunk_id)

    def delete(self, chunk_id):
        self._rows.pop(chunk_id, None)
        self.delete_calls.append(chunk_id)

    def search(self, query_vector, top_k=5):
        return [
            SearchResult(chunk_id=cid, text=row["text"], metadata=row["metadata"], score=0.0)
            for cid, row in list(self._rows.items())[:top_k]
        ]

    def list_indexed(self):
        return {cid: row["metadata"] for cid, row in self._rows.items()}

    def compact(self, *, older_than_days=None):
        pass


def _write_knowledge_file(fake_repo, relative_path: str, content: str) -> None:
    path = fake_repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_default_roots_scan_the_whole_repository():
    # Decisão revista (ver comentário em mcp_server/indexing.py):
    # restringir a knowledge/projects/clients copiava sem necessidade o
    # raciocínio de WRITABLE_PREFIXES (proteção de ESCRITA), que não se
    # aplica a escopo de BUSCA. moto_mcp é "base de conhecimento e time
    # de agentes" (README.md) inteiro, não uma fatia dele.
    assert DEFAULT_ROOTS == ("",)


def test_first_run_indexes_every_section_as_new(fake_repo):
    _write_knowledge_file(
        fake_repo,
        "knowledge/exemplo.md",
        "## Seção A\nConteúdo A.\n## Seção B\nConteúdo B.\n",
    )
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()

    report = reindex(store, embedder, categories=("knowledge",))

    assert set(report.upserted) == {
        "knowledge/exemplo.md#Seção A",
        "knowledge/exemplo.md#Seção B",
    }
    assert report.deleted == []
    assert report.unchanged == 0
    assert report.total_current == 2
    assert set(store.list_indexed()) == set(report.upserted)


def test_second_run_without_changes_skips_everything(fake_repo):
    _write_knowledge_file(
        fake_repo, "knowledge/exemplo.md", "## Seção A\nConteúdo A.\n"
    )
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()
    reindex(store, embedder, categories=("knowledge",))
    embedder.calls.clear()
    store.upsert_calls.clear()

    report = reindex(store, embedder, categories=("knowledge",))

    assert report.upserted == []
    assert report.unchanged == 1
    assert embedder.calls == []  # não chamou o "Ollama" de novo
    assert store.upsert_calls == []


def test_editing_one_section_only_reembeds_that_chunk(fake_repo):
    _write_knowledge_file(
        fake_repo,
        "knowledge/exemplo.md",
        "## Seção A\nConteúdo A.\n## Seção B\nConteúdo B.\n",
    )
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()
    reindex(store, embedder, categories=("knowledge",))

    _write_knowledge_file(
        fake_repo,
        "knowledge/exemplo.md",
        "## Seção A\nConteúdo A EDITADO.\n## Seção B\nConteúdo B.\n",
    )
    embedder.calls.clear()

    report = reindex(store, embedder, categories=("knowledge",))

    assert report.upserted == ["knowledge/exemplo.md#Seção A"]
    assert report.unchanged == 1
    assert embedder.calls == [["Conteúdo A EDITADO."]]


def test_removed_section_gets_deleted_not_left_orphaned(fake_repo):
    _write_knowledge_file(
        fake_repo,
        "knowledge/exemplo.md",
        "## Seção A\nConteúdo A.\n## Seção B\nConteúdo B.\n",
    )
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()
    reindex(store, embedder, categories=("knowledge",))

    _write_knowledge_file(fake_repo, "knowledge/exemplo.md", "## Seção A\nConteúdo A.\n")

    report = reindex(store, embedder, categories=("knowledge",))

    assert report.deleted == ["knowledge/exemplo.md#Seção B"]
    assert "knowledge/exemplo.md#Seção B" not in store.list_indexed()
    assert "knowledge/exemplo.md#Seção A" in store.list_indexed()


def test_deleted_file_removes_all_its_chunks(fake_repo):
    _write_knowledge_file(
        fake_repo, "knowledge/vai_sumir.md", "## Única\nTexto.\n"
    )
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()
    reindex(store, embedder, categories=("knowledge",))

    (fake_repo / "knowledge" / "vai_sumir.md").unlink()

    report = reindex(store, embedder, categories=("knowledge",))

    assert report.deleted == ["knowledge/vai_sumir.md#Única"]
    assert store.list_indexed() == {}


def test_empty_section_body_is_not_indexed(fake_repo):
    # Cabeçalho seguido de outro cabeçalho, sem corpo -> não vira chunk
    # (não há texto pra gerar embedding).
    _write_knowledge_file(
        fake_repo, "knowledge/exemplo.md", "## Vazia\n## Preenchida\nTexto.\n"
    )
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()

    report = reindex(store, embedder, categories=("knowledge",))

    assert report.upserted == ["knowledge/exemplo.md#Preenchida"]


def test_missing_category_folder_is_not_an_error(fake_repo):
    # fake_repo não cria knowledge/ por padrão — simula um repositório
    # onde essa pasta ainda não existe.
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()

    report = reindex(store, embedder, categories=("knowledge", "projects", "clients"))

    assert report.deleted == []
    # projects/ e clients/ do fake_repo só têm _TEMPLATE.md — indexa
    # normalmente, só knowledge/ (ausente) é pulada sem erro.
    assert any(chunk_id.startswith("projects/") for chunk_id in report.upserted)


def test_chunk_id_and_metadata_match_documented_schema(fake_repo):
    _write_knowledge_file(fake_repo, "knowledge/exemplo.md", "## Só\nTexto.\n")
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()

    reindex(store, embedder, categories=("knowledge",))

    metadata = store.list_indexed()["knowledge/exemplo.md#Só"]
    assert metadata["path"] == "knowledge/exemplo.md"
    assert metadata["section"] == "Só"
    assert metadata["category"] == "knowledge"
    assert len(metadata["content_hash"]) == 64  # sha256 hexdigest
    assert "indexed_at" in metadata


def test_preamble_with_real_content_is_indexed_under_empty_section_key(fake_repo):
    # Conteúdo antes do primeiro "## " vira a seção "" (ver
    # documents.split_sections) — se tiver corpo de verdade (não só um
    # "# Título" solto), é um chunk válido como qualquer outro, com
    # chunk_id "path#" (seção vazia). Ver seção 7 do doc de embeddings.
    _write_knowledge_file(
        fake_repo,
        "knowledge/exemplo.md",
        "# Exemplo\n\nParágrafo de introdução com conteúdo de verdade.\n\n## Seção A\nConteúdo A.\n",
    )
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()

    report = reindex(store, embedder, categories=("knowledge",))

    assert set(report.upserted) == {"knowledge/exemplo.md#", "knowledge/exemplo.md#Seção A"}
    metadata = store.list_indexed()["knowledge/exemplo.md#"]
    assert metadata["section"] == ""


def test_title_only_preamble_still_counts_as_content(fake_repo):
    # Registra o comportamento real (não um bug): um "# Título" sozinho,
    # sem mais nada antes do primeiro "## ", TEM corpo não-vazio pra
    # split_sections (a própria linha do título) — então também vira
    # chunk. É um chunk de baixo valor semântico, mas inofensivo (não
    # atrapalha ranking de busca — ver calibração de score na seção 4 do
    # doc de embeddings) e consistente com a regra simples "corpo vazio
    # não indexa, corpo não-vazio indexa", sem heurística extra pra
    # distinguir "título sozinho" de "preâmbulo de verdade".
    _write_knowledge_file(fake_repo, "knowledge/exemplo.md", "# Só o título\n\n## Seção A\nConteúdo A.\n")
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()

    report = reindex(store, embedder, categories=("knowledge",))

    assert "knowledge/exemplo.md#" in report.upserted


def test_default_scan_reaches_previously_excluded_folders(fake_repo):
    # Regressão direta do caso real que motivou a mudança de escopo:
    # "agents/" não estava em DEFAULT_CATEGORIES antes, então
    # `agents/bill.md` nunca era indexado — uma pergunta tipo "quem é o
    # Bill" não tinha como achar o chunk certo. Com DEFAULT_ROOTS = ("",)
    # (escaneia o repositório inteiro), roda `reindex()` SEM passar
    # `categories` (usa o default de verdade) e confirma que uma pasta
    # fora do antigo escopo entra no índice.
    (fake_repo / "agents").mkdir()
    (fake_repo / "agents" / "bill.md").write_text(
        "# Bill\n\n## Identidade e papel\nEspecialista em marketing digital.\n", encoding="utf-8"
    )
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()

    report = reindex(store, embedder)  # sem `categories=` -> usa DEFAULT_ROOTS

    assert "agents/bill.md#Identidade e papel" in report.upserted
    assert store.list_indexed()["agents/bill.md#Identidade e papel"]["category"] == "agents"


def test_root_level_loose_file_gets_root_category(fake_repo):
    # Arquivos soltos na raiz do repo (AGENTS.md, CLAUDE.md, README.md,
    # to-do.md...) não têm "/" no path — não há um primeiro segmento
    # que sirva de categoria, então usam ROOT_CATEGORY.
    (fake_repo / "AGENTS.md").write_text("## Ponte\nInstruções pra este agente.\n", encoding="utf-8")
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()

    report = reindex(store, embedder)

    assert "AGENTS.md#Ponte" in report.upserted
    assert store.list_indexed()["AGENTS.md#Ponte"]["category"] == ROOT_CATEGORY


def test_default_scan_does_not_touch_its_own_vector_index_folder(fake_repo):
    # .vector_index/ (onde o LanceDB guarda os dados binários do próprio
    # índice) está em IGNORED_DIR_NAMES — o scan da raiz inteira não pode
    # tentar ler os arquivos internos do banco como se fossem conteúdo.
    (fake_repo / ".vector_index").mkdir()
    (fake_repo / ".vector_index" / "nao_e_conteudo.md").write_text("## X\nY\n", encoding="utf-8")
    store = _FakeVectorStore()
    embedder = _FakeEmbeddingProvider()

    report = reindex(store, embedder)

    assert not any(chunk_id.startswith(".vector_index") for chunk_id in report.upserted)
