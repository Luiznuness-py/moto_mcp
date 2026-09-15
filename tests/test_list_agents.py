# tests/test_list_agents.py
#
# Testa tools.list_agents() contra o fixture fake_repo (tests/conftest.py),
# acrescentando agents/ diretamente em cada teste — fake_repo não inclui
# essa pasta por padrão (mesmo motivo já documentado em
# tests/test_indexing.py: mudar o fixture compartilhado só pra isso
# arriscaria afetar os outros testes que já o usam).

from __future__ import annotations

from mcp_server import tools


def _write_agent(fake_repo, filename: str, content: str) -> None:
    agents_dir = fake_repo / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / filename).write_text(content, encoding="utf-8")


async def test_extracts_nome_e_papel_from_title_line(fake_repo):
    _write_agent(
        fake_repo,
        "bill.md",
        "# Bill — Especialista em Marketing Digital\n\n## Identidade e papel\nMeu nome é Bill.\n",
    )

    result = await tools.list_agents()

    assert result == [
        {"nome": "Bill", "papel": "Especialista em Marketing Digital", "arquivo": "agents/bill.md"}
    ]


async def test_lists_every_agent_file_sorted(fake_repo):
    _write_agent(fake_repo, "red.md", "# Red — Analista de Testes e Segurança\n")
    _write_agent(fake_repo, "bill.md", "# Bill — Especialista em Marketing Digital\n")

    result = await tools.list_agents()

    # documents.list_entries já ordena por nome de arquivo — bill.md
    # antes de red.md.
    assert [a["arquivo"] for a in result] == ["agents/bill.md", "agents/red.md"]


async def test_title_without_em_dash_still_appears_with_empty_papel(fake_repo):
    # Não é erro nem é omitido — só não segue a convenção "Nome — Papel".
    _write_agent(fake_repo, "solto.md", "# Só um título qualquer\nTexto.\n")

    result = await tools.list_agents()

    assert result == [{"nome": "Só um título qualquer", "papel": "", "arquivo": "agents/solto.md"}]


async def test_empty_file_does_not_crash(fake_repo):
    _write_agent(fake_repo, "vazio.md", "")

    result = await tools.list_agents()

    assert result == [{"nome": "", "papel": "", "arquivo": "agents/vazio.md"}]


async def test_missing_agents_folder_returns_empty_list_not_error(fake_repo):
    # fake_repo não cria agents/ por padrão — simula um fork do moto_mcp
    # que ainda não tem nenhum agente definido.
    result = await tools.list_agents()

    assert result == []


async def test_mike_and_mike_review_are_distinct_entries(fake_repo):
    # Caso real conferido no repositório: "mike_review.md" também tem
    # título "# Mike — ..." (é descrito como um MODO do Mike, não uma
    # identidade concorrente — ver agents/mike.md), então list_agents()
    # legitimamente devolve duas entradas com nome="Mike" e `arquivo`
    # diferente — isso não é bug, é o dado real.
    _write_agent(fake_repo, "mike.md", "# Mike — Assistente pessoal e orquestrador\n")
    _write_agent(fake_repo, "mike_review.md", "# Mike — Revisor de Código, Arquitetura e Segurança\n")

    result = await tools.list_agents()

    nomes_e_arquivos = [(a["nome"], a["arquivo"]) for a in result]
    assert ("Mike", "agents/mike.md") in nomes_e_arquivos
    assert ("Mike", "agents/mike_review.md") in nomes_e_arquivos
