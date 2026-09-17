# mcp_server/verification_questions.py
#
# Perguntas usadas por scripts/verify_search.py para validar que a busca
# semântica encontra chunks esperados. Os chunks esperados não devem ficar
# em pastas excluídas do índice semântico.

VERIFICATION_QUESTIONS: list[dict[str, str]] = [
    {
        "question": "Quais são as regras gerais que o agente deve seguir?",
        "expected_chunk_id": "START_HERE.md#Regras gerais",
    },
    {
        "question": "Quais tools o servidor MCP oferece para leitura e busca?",
        "expected_chunk_id": "README.md#Servidor MCP",
    },
    {
        "question": "Qual modelo de embedding é usado por padrão?",
        "expected_chunk_id": "knowledge/vector-search/embeddings-e-busca-semantica.md#Modelo padrão",
    },
    {
        "question": "Quais cuidados de segurança valem para tools MCP?",
        "expected_chunk_id": "knowledge/security/security_test_master_checklist.md#Itens MCP",
    },
    {
        "question": "Como identificar a qual cliente uma mensagem se refere?",
        "expected_chunk_id": "clients/_index.md#Regras do índice",
    },
    {
        "question": "Qual agente é usado para revisão técnica?",
        "expected_chunk_id": "agents/mike_review.md#Identidade e papel",
    },
    {
        "question": "Qual ciclo de desenvolvimento deve ser seguido?",
        "expected_chunk_id": "global/workflow.md#Ciclo de desenvolvimento",
    },
    {
        "question": "Onde descrever comandos para executar um projeto?",
        "expected_chunk_id": "projects/_TEMPLATE.md#Como rodar",
    },
]
