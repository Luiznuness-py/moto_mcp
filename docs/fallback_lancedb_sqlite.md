# LanceDB isolado com fallback automático para SQLite

Nota sobre esta cópia: as evidências históricas com 175 chunks e Codex foram obtidas em `moto_mcp_luiz`. Nenhum dado pessoal, configuração local ou índice desse checkout foi transportado para `moto_mcp`.

Data: 13 de outubro de 2026. Implementação e validação local no Intel Celeron N4500.

## Problema e decisão

O wheel oficial LanceDB 0.38.0 encerra Python com SIGILL (Illegal instruction) nesta CPU, que não oferece AVX/AVX2. A investigação anterior identificou `vxorps`; o código original v0.38.0 configura Haswell e AVX2/FMA/F16C para Linux x86_64. Isso descreve a incompatibilidade observada no N4500, não em todos os Celerons.

A primeira solução substituiu LanceDB por SQLite e recuperou a busca semântica. A pedido do usuário, a solução final mantém LanceDB como primeira opção e SQLite como alternativa automática. Não existe import nativo de LanceDB no processo MCP. Não se faz um teste de import seguido de outro import desprotegido: o processo auxiliar que inicializa LanceDB permanece atendendo às operações enquanto estiver saudável.

## Fluxo e persistência

1. `get_vector_store()` compartilha uma instância `AutomaticVectorStore` entre startup e ferramentas. Scripts de busca e indexação usam a mesma fábrica.
2. O adaptador abre SQLite, depois inicia um único processo auxiliar com `multiprocessing` em modo `spawn`. Filas locais transportam operações e resultados; nenhuma porta ou serviço de rede adicional é aberto.
3. O auxiliar carrega `LanceDBVectorStore`, reconcilia o índice com o espelho SQLite e informa que está pronto. As buscas e listagens passam a usar LanceDB nesse processo.
4. Upserts e exclusões são confirmados primeiro em SQLite; depois seguem para LanceDB. O espelho inclui vetores, texto e metadados, permitindo continuar a busca sem gerar novamente embeddings quando LanceDB falha.
5. Erro Python, término do auxiliar, falha ao criar o processo ou ausência de resposta durante 30 segundos ativa SQLite. A busca que falhou é repetida no SQLite; gravações já confirmadas ficam preservadas. O motivo vai para stderr, sem contaminar stdout do MCP.
6. Após a falha, a sessão permanece em SQLite. Reiniciar o MCP tenta LanceDB novamente e sincroniza também alterações e exclusões feitas durante o fallback. O auxiliar é encerrado na troca e na saída normal do processo.

Um índice SQLite já existente é a fonte atual da reconciliação. Quando há somente um índice LanceDB anterior e ele pode ser lido, os registros são copiados para SQLite em uma transação, sem pedir novos embeddings. Uma marca persistente evita reimportar registros antigos depois de exclusões. Se LanceDB não puder sequer abrir o índice antigo, não é possível recuperar seus vetores nessa CPU: a indexação dos documentos reconstrói o SQLite. Os arquivos nativos não são apagados pela migração. A reconciliação pode atualizar ou excluir registros obsoletos no índice LanceDB; ele é um índice derivado dos documentos.

Falhas do próprio SQLite continuam sendo erros explícitos; o fallback não oculta disco cheio, corrupção ou uma configuração de dimensão incompatível. Entradas inválidas são rejeitadas antes da chamada nativa.

## Componentes alterados

- `mcp_server/fallback.py`: controle do processo, espelho durável, timeout, fechamento e troca de backend.
- `mcp_server/_lancedb.py`: adaptador original, carregado exclusivamente no auxiliar.
- `mcp_server/vectorstore.py`: SQLite e fábrica compartilhada; mantém o contrato `VectorStore` e `SearchResult`.
- Startup, ferramentas e scripts passaram a usar a fábrica. O schema público das ferramentas permanece o mesmo.
- `pyproject.toml` e `poetry.lock` voltaram a declarar LanceDB. O lock foi gerado e conferido com Poetry 2.4.3.
- README e documentação de busca foram atualizados. Relatórios que descreviam somente a substituição do LanceDB foram removidos.

A proteção anterior que apenas detectava SIGILL sem recuperar busca não é a solução atual: agora as operações realmente continuam em SQLite.

## Inicialização e embeddings

Permanece o ajuste que inicia a reindexação em thread daemon, permitindo o handshake MCP antes de uma inferência lenta. A indexação salva lotes de até oito chunks e retoma pelos hashes persistidos; lotes incompletos do provedor geram erro explícito.

O bge-m3 continua gerando embeddings reais de 1024 dimensões no Ollama. SQLite não substitui o modelo: armazena vetores normalizados e calcula cosseno em Python. No N4500, bge-m3 F16 continua lento. Na primeira indexação, as buscas podem retornar somente os chunks já salvos.

## Validação da versão com fallback

- A bateria final passou em 183 testes. Inclui processos reais que permanecem ativos, SIGILL induzido na inicialização e nas operações, timeout, erro Python, falha de criação do processo, persistência, concorrência, exclusões, reabertura e validação de entradas. Há dois avisos de depreciação existentes nas dependências.
- Os testes da sincronização e da importação legada executam o código de produção com API LanceDB simulada e SQLite real. Uma importação com vetor inválido foi revertida integralmente. Isso não é uma execução bem-sucedida da extensão LanceDB nesta CPU.
- O LanceDB 0.38.0 foi reinstalado do PyPI no ambiente real. O auxiliar encerrou com código -4 (SIGILL), o pai permaneceu vivo e o backend mudou para SQLite. Upsert, search, list_indexed, compact e delete funcionaram em banco temporário.
- Após instalar as dependências do lock, um cliente SDK repetiu search_semantic: oito resultados com os seis campos públicos e a seção esperada do workflow. A atualização em segundo plano reindexou quatro chunks de documentação, preservou 171 e terminou sem pendências.
- O índice real com 175 chunks passou em `PRAGMA integrity_check`, busca top-8 e compactação após o SIGILL.
- Um cliente MCP SDK listou 13 ferramentas e executou get_capabilities, reindex_search, compact_search_index e get_capabilities. A reindexação confirmou 175 chunks sem mudança; a compactação preservou todos os identificadores e metadados.
- O Codex CLI realizou get_capabilities, read_document de START_HERE.md e search_semantic sobre o ciclo de desenvolvimento. As três chamadas terminaram com status completed e sem erro. O stderr do próprio servidor registrou o SIGILL e o fallback. A busca retornou a seção de global/workflow.md e o Codex respondeu em português.
- O teste Codex usou configuração temporária, modo somente leitura, shell do agente desabilitado e somente as três ferramentas previamente autorizadas. Foram verificados os eventos de chamadas, não apenas a resposta textual.

O caminho saudável do processo foi validado com adaptador simulado. A execução bem-sucedida de LanceDB real em uma CPU compatível ainda precisa de validação em outra máquina. Nesta CPU, o teste real comprova a falha nativa e a recuperação por SQLite.

## Evidência anterior da busca SQLite

Antes deste fallback, 175 chunks foram indexados com bge-m3 F16 real. Os scores SQLite concordaram com um cálculo independente de cosseno nos 175 registros, dentro de 1e-12. A calibração original marcou 7/8: a pergunta ampla sobre regras esperava START_HERE.md#Regras gerais, que ficou em 28º. A fonte normativa global/rules_absolute.md# ficou em primeiro lugar. A referência foi corrigida explicitamente, sem mudar pergunta, top-8 ou algoritmo, e a calibração passou 8/8. Essa correção não elimina a limitação de recuperação da seção START_HERE.

Esse 8/8 é evidência anterior do mesmo adaptador SQLite; nesta etapa foi repetida a chamada semântica real pelo Codex após a falha do LanceDB. Não foi repetida toda a geração inicial de embeddings.

## Como reproduzir

Na raiz do repositório, com Poetry compatível com grupos de dependências:

```sh
poetry install --with dev
poetry run python -m pytest -q
ollama pull bge-m3
poetry run python scripts/reindex.py
poetry run python scripts/verify_search.py
poetry run python -m mcp_server.server
```

O cliente MCP deve executar o último comando com cwd na raiz do projeto. Não é necessário selecionar SQLite manualmente. O registro esperado neste N4500 é:

```text
[moto_mcp] LanceDB falhou (Processo LanceDB encerrou com código -4 (SIGILL)); usando SQLite nesta sessão.
```

## Limites e publicação

- LanceDB saudável usa um processo adicional, comunicação entre processos e armazenamento duplicado. Na inicialização, o espelho é reconciliado antes de usar LanceDB.
- Cada operação/inicialização tem limite de resposta de 30 segundos. Uma operação nativa lenta também pode provocar fallback; isso prioriza manter o MCP disponível.
- Busca SQLite é exata e linear. Bases grandes, Windows, macOS e GPU não foram validados.
- Compactação executa VACUUM no SQLite e optimize no LanceDB quando ativo. older_than_days só seleciona histórico no LanceDB; SQLite não mantém versões por idade.
- Falhas de Ollama ou modelo de embedding não são falhas de LanceDB e não são corrigidas por trocar o banco.
- Trocar o modelo de embedding requer reconstruir o índice, mesmo com igual dimensão.

Nenhum commit, push ou PR foi criado. A publicação depende da aprovação do usuário.

Referências: [processos e modo spawn no Python](https://docs.python.org/3/library/multiprocessing.html), [upsert e exclusões no LanceDB](https://docs.lancedb.com/tables/update), [configuração original v0.38.0](https://github.com/lancedb/lancedb/blob/v0.38.0/.cargo/config.toml).

## Transporte e validação no checkout moto_mcp

Em 13 de outubro de 2026, foram transportados 27 arquivos de código, testes e documentação de `moto_mcp_luiz` para `/mnt/sda/git/moto_mcp`. O README recebeu somente a mudança referente ao fallback, preservando suas instruções próprias. Perfil, clientes, projetos, regras pessoais, configurações OpenCode, .env e índices não foram copiados.

O ambiente Python próprio do destino estava vazio. As dependências do lock foram instaladas com Poetry 2.4.3 temporário, incluindo o grupo dev; o Poetry global permaneceu inalterado. `poetry check --lock` passou. O Poetry global 2.1 não reconhece esse lock com grupos PEP 735; para futuras instalações, use Poetry compatível, como 2.4.3.

A bateria no destino passou em **183 testes**, com dois avisos de depreciação, em 19,99 segundos. O wheel real LanceDB 0.38.0 provocou SIGILL no auxiliar; SQLite completou upsert, busca com vetor sintético, compactação e exclusão em um diretório temporário. O cliente SDK iniciou o transporte stdio, listou 13 ferramentas e executou get_capabilities e read_document de README.md.

O teste de protocolo desativou o Ollama apenas no ambiente temporário do subprocesso, para evitar indexação demorada. Não foi gerado um novo índice neural completo nem repetido o teste com Codex neste checkout. As evidências anteriores de embeddings reais e Codex descritas acima pertencem ao checkout de origem. Os arquivos particulares e configurações preexistentes do destino foram conferidos por hash e permaneceram iguais. Nenhum commit, push ou PR foi criado.
