# START HERE - Agent Memory

Este repositório é uma base genérica para agentes e um servidor MCP que expõe seus próprios documentos como ferramentas.

## Ordem de leitura

1. Leia `profile/profile.md`.
2. Leia `global/workflow.md`.
3. Leia `global/rules_absolute.md`.
4. Leia `ecosystem/` quando a tarefa envolver infraestrutura, produto, deploy ou integração.
5. Leia o arquivo em `projects/` quando a tarefa envolver um projeto específico.
6. Leia `knowledge/security/security_testing_baseline.md` quando a tarefa envolver segurança, validação, pentest ou deploy seguro.
7. Leia o arquivo em `clients/` quando a tarefa envolver um cliente específico.
8. Leia `agents/<nome>.md` somente quando a tarefa chamar uma especialidade.
9. Leia `knowledge/<tema>/` quando a tarefa exigir base técnica.

## Manutenção de contexto

- Projeto novo deve ter arquivo em `projects/<nome>.md`, usando `projects/_TEMPLATE.md`.
- Cliente novo deve ter arquivo em `clients/<nome>.md`, usando `clients/_TEMPLATE.md`.
- Atualize `INDEX.md` ou `clients/_index.md` quando criar entradas novas.
- Não misture contexto de projetos ou clientes diferentes no mesmo arquivo.
- Não registre secrets, tokens, chaves, `.env` real, credenciais ou senhas.

## Regras gerais

- Responder curto, direto e com conclusão primeiro.
- Não declarar pronto, seguro, testado ou aprovado sem evidência real.
- Discordar quando houver risco técnico, segurança, escala, rastreabilidade ou qualidade.
- Antes de alterar código, ler o padrão local.
- Regra de negócio fica no backend/service.
- Sem gambiarra, sem reaproveitar campo com outro significado.
- Commit local e push dependem das regras do repositório e da autorização do usuário.
