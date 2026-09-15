# mcp_server/verification_questions.py
#
# Conjunto fixo de perguntas -> chunk esperado, usado pra validar a
# busca semântica de verdade (ver "Verificação obrigatória" em
# knowledge/vector-search/embeddings-e-busca-semantica.md — não é
# opcional, é o que prova que o índice funciona, não só "rodou sem
# erro"). Cada pergunta é uma paráfrase — de propósito NÃO usa as
# palavras do cabeçalho da seção — porque o objetivo é testar busca por
# SENTIDO, não a busca por substring que a tool `search_documents` já
# fazia antes disso existir.
#
# `expected_chunk_id` usa o formato definido na seção 7 do doc de
# embeddings: f"{path}#{section}". Todos os treze abaixo foram
# conferidos contra conteúdo real lido dos arquivos (não inventados só a
# partir dos títulos das seções).
#
# Cobertura deliberada de casos difíceis, não só perguntas fáceis:
# - Q3 e Q6 miram dois arquivos de checklist de segurança que são quase
#   idênticos entre si (`security_test_master_checklist.md` é cópia
#   duplicada de `security_testing_baseline.md`, só com uma seção a mais
#   no fim) — testa se a busca acerta o chunk certo mesmo com conteúdo
#   quase-duplicado competindo.
# - Q9 mira `projects/moto-mcp-server.md` (o projeto ANTIGO, histórico)
#   em vez de `projects/moto-mcp-framework-server.md` (o atual) — os
#   dois têm cabeçalhos de seção idênticos (Papel, Stack, Decisões de
#   arquitetura...) e conteúdo relacionado; testa se a busca não
#   confunde "o servidor atual" com "o que ele substituiu".
# - Q11–Q13 miram `agents/` — a pasta que ficou de fora do escopo até
#   `DEFAULT_ROOTS` passar a escanear o repositório inteiro (ver
#   mcp_server/indexing.py); são o caso real que expôs esse problema
#   ("quem é o Bill" não achava `agents/bill.md`, porque o arquivo nem
#   estava indexado — não era falha da busca).

VERIFICATION_QUESTIONS: list[dict[str, str]] = [
    {
        "question": "Por que a escrita neste servidor é restrita só a projects e clients?",
        "expected_chunk_id": "projects/moto-mcp-framework-server.md#Decisões de arquitetura",
    },
    {
        "question": "Por que a busca vetorial usa similaridade de cosseno em vez de distância euclidiana?",
        "expected_chunk_id": "knowledge/vector-search/embeddings-e-busca-semantica.md#4. Métricas de similaridade — por que cosseno",
    },
    {
        "question": "Qual é o risco de segurança real de um servidor MCP local sem rede nem frontend?",
        "expected_chunk_id": "knowledge/security/security_test_master_checklist.md#Adaptação para este sistema (moto-mcp-framework-server)",
    },
    {
        "question": "Onde eu guardo capturas de tela e links que já reuni sobre um cliente?",
        "expected_chunk_id": "clients/_TEMPLATE.md#Ativos e evidências",
    },
    {
        "question": "Como decidir a qual cliente uma mensagem se refere quando ninguém foi citado?",
        "expected_chunk_id": "clients/_index.md#Regras do índice",
    },
    {
        "question": "De onde vêm as práticas usadas na checklist de segurança dos projetos?",
        "expected_chunk_id": "knowledge/security/security_test_master_checklist.md#Fontes externas consultadas",
    },
    {
        "question": "Por que reindexar o que mudou não precisa de um agente de IA decidindo o que reprocessar?",
        "expected_chunk_id": "knowledge/vector-search/embeddings-e-busca-semantica.md#6. Reindexação incremental (nota lateral)",
    },
    {
        "question": "O que fez o bge-m3 ser escolhido em vez de um modelo de embedding via API paga?",
        "expected_chunk_id": "knowledge/vector-search/embeddings-e-busca-semantica.md#2. Modelo escolhido: bge-m3",
    },
    {
        "question": "Antes do servidor atual existir, o que fazia esse papel no repositório?",
        "expected_chunk_id": "projects/moto-mcp-server.md#Papel (histórico)",
    },
    {
        "question": "Que linguagem, versão e gerenciador de pacote esse servidor usa?",
        "expected_chunk_id": "projects/moto-mcp-framework-server.md#Stack",
    },
    {
        "question": "Quem é o especialista em marketing digital desse time de agentes?",
        "expected_chunk_id": "agents/bill.md#Identidade e papel",
    },
    {
        "question": "Quem decide qual especialista chamar e fala diretamente com o usuário?",
        "expected_chunk_id": "agents/mike.md#Identidade principal",
    },
    {
        "question": "Pra qual agente eu direciono uma dúvida sobre teste de segurança?",
        "expected_chunk_id": "agents/mike.md#Direcionamento de especialistas",
    },
]
