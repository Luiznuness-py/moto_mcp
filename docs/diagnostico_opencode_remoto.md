# OpenCode + Ollama + moto_mcp remoto

## Escopo e versões

Investigação em 2026-09-16 no computador cliente, consultando MCP e Ollama
remotos em `10.80.132.178`. OpenCode instalado: **1.18.31**. Ollama remoto:
**0.34.0**. Os resultados desta investigação ficam em
`evidence/opencode-remote-2026-09-16.json`.

`opencode mcp list` com `connected` comprova conexão MCP; não comprova que
o modelo recebeu, escolheu ou executou uma ferramenta. São etapas diferentes.
Nesta investigação, um intermediário HTTP local encaminhou os pedidos ao
Ollama sem alterar mensagens ou tools e registrou somente metadados dos
pedidos. Os pedidos de inferência continham as **13 tools `motomcp_*`** e
as ferramentas nativas. Pedidos auxiliares, como geração de título, podem
não conter tools; não devem ser confundidos com a inferência do agente.

## Formato da configuração

O OpenCode **1.18.31** aceita `mcp.servers` por uma camada de compatibilidade
com a configuração V2. Entretanto, essa camada **remove `codemode`**: nessa
versão, `codemode: false` não é um mecanismo para mudar a exposição das tools.
As ferramentas MCP já são enviadas diretamente ao provider.

Use o formato nativo dessa versão: `mcp.motomcp`, sem `servers` e sem
`codemode`. A documentação V2 oferece `mcp.servers` e `codemode` para remoto,
mas não deve ser aplicada indiscriminadamente ao executável V1.

Fonte verificada: [compatibilidade da versão 1.18.31](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/config/v2-compat.ts),
funções `normalizeMcp`, `normalizeServer` e `lowerServer`;
[schema MCP V1](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/core/src/v1/config/mcp.ts).

`opencode mcp debug motomcp` nessa versão é um diagnóstico **OAuth**. Com
`oauth: false`, imprime `has OAuth explicitly disabled` e termina. Isso é
esperado para Bearer e não testa `tools/call`.
[Código do comando](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/cli/cmd/mcp.ts).

## Rede e autenticação

Para `10.80.132.178`, inclusive via ZeroTier, o servidor usa **`lan`** e
exige `MOTO_MCP_AUTH_TOKEN`. O código exige pelo menos 32 caracteres.
Não mudar para `tailscale`, não remover o middleware e não desabilitar auth
para contornar tool calling. Referências locais: `mcp_server/network.py`,
`mcp_server/server_network.py`, `mcp_server/auth.py`.

Endpoints distintos:

- MCP Streamable HTTP: `http://10.80.132.178:8765/mcp`.
- Provider OpenAI compatible do Ollama: `http://10.80.132.178:11434/v1`.
- Diagnóstico nativo do Ollama: `http://10.80.132.178:11434/api/ps`.

O teste sem Bearer retornou **401**. Com Bearer, `initialize`, `tools/list`,
`get_capabilities`, `search_documents` e `read_document` retornaram dados reais.

## Contexto real do Ollama

Os modelos originais foram observados com **4096 tokens** em `/api/ps`.
Com as ferramentas nativas e o catálogo MCP, os três Qwen3 executaram o
pedido explícito de capabilities, mas nenhum executou o pedido de busca.
O 8B declarou que `motomcp_search_documents` não estava disponível, embora
o pedido enviado pelo OpenCode contivesse essa função. Os eventos de
inferência do 14B/8B mostraram apenas 2046 tokens de entrada nesse cenário.

`provider.models.*.limit.context` informa o limite ao OpenCode; **não aumenta
o contexto do runtime Ollama**. Configurar `OLLAMA_CONTEXT_LENGTH` apenas no
computador cliente também não altera o serviço remoto já iniciado.

A API `/v1` não possui parâmetro OpenAI para definir o tamanho de contexto.
O procedimento oficial é criar outro nome de modelo com `PARAMETER num_ctx`.
[Documentação do Ollama](https://docs.ollama.com/api/openai-compatibility#setting-the-local-context-size).

Perfis separados criados nesta investigação, preservando os modelos originais:

| Base | Nome no Ollama | num_ctx |
| --- | --- | ---: |
| `qwen3:14b` | `qwen3-14b-motomcp-32k` | 32768 |
| `qwen3:8b` | `qwen3-8b-motomcp-16k` | 16384 |
| `qwen3:4b` | `qwen3-4b-motomcp-16k` | 16384 |

Para reproduzir a criação, execute no servidor Ollama ou num cliente autorizado
a alcançar sua API. Não precisa baixar novamente os pesos nem reiniciar o serviço:

```powershell
$ollama = 'http://10.80.132.178:11434'
$perfis = @(
  @('qwen3:14b', 'qwen3-14b-motomcp-32k', 32768),
  @('qwen3:8b', 'qwen3-8b-motomcp-16k', 16384),
  @('qwen3:4b', 'qwen3-4b-motomcp-16k', 16384)
)
foreach ($perfil in $perfis) {
  $body = @{
    from = $perfil[0]
    model = $perfil[1]
    parameters = @{ num_ctx = $perfil[2] }
    stream = $false
  } | ConvertTo-Json -Depth 4
  Invoke-RestMethod "$ollama/api/create" -Method Post `
    -ContentType 'application/json' -Body $body
}
```

Criação via API é equivalente a `FROM qwen3:14b` + `PARAMETER num_ctx 32768`
num Modelfile, seguido de `ollama create`.
[API create](https://docs.ollama.com/api/create).

Durante uma inferência, confira o contexto efetivo:

```powershell
(Invoke-RestMethod 'http://10.80.132.178:11434/api/ps').models |
  Select-Object name, context_length, size_vram
```

O 14B/32k foi observado com `context_length=32768` e aproximadamente
14,37 GB de VRAM alocada. A margem depende do hardware e da concorrência;
uma bateria curta não garante conversas longas.

## Configurar o computador cliente

1. Confirme `opencode --version`; este procedimento é para **1.18.31**.
2. Em uma pasta dedicada do cliente, use
   `opencode/opencode.remote.example.json` deste repo como `opencode.json`.
3. Use `opencode/AGENTS.md` na mesma pasta. O prefixo deve ser **`motomcp`**.
4. Configure o Bearer no ambiente do processo OpenCode, sem gravá-lo no JSON:

```powershell
$segredo = Read-Host 'Bearer token do moto_mcp' -AsSecureString
$env:MOTO_MCP_AUTH_TOKEN = [System.Net.NetworkCredential]::new('', $segredo).Password
Remove-Variable segredo
opencode mcp list
opencode --model ollama/qwen3:14b
```

O exemplo mantém os nomes de seleção `ollama/qwen3:14b`, `ollama/qwen3:8b`
e `ollama/qwen3:4b`, mas o campo `id` direciona cada um ao perfil Ollama
com contexto maior. Os perfis precisam existir no servidor antes de usar
essa configuração. O JSON contém apenas `{env:MOTO_MCP_AUTH_TOKEN}`.

Neste checkout, `opencode/opencode.json` foi corrigido preservando os endpoints
e nomes existentes. Para manter o cliente local utilizável entre sessões, o
Bearer existente foi movido para `opencode/.motomcp-token`, ignorado pelo Git,
e o JSON usa `Bearer {file:./.motomcp-token}`. A substituição de arquivo foi
confirmada em `opencode mcp list`. Esse arquivo é um segredo local, não faz
parte do exemplo distribuível e não deve ser copiado para outra máquina sem
um procedimento de transferência seguro. Não incluí-lo em anexos ou commits.
[Substituição de arquivo nesta versão](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/config/variable.ts).

O token apareceu na saída de uma comparação local durante a investigação:
**rotacionar no servidor e no cliente**. Movê-lo para um arquivo ignorado
evita versionamento acidental, mas não substitui a rotação após exposição.

O `.env` do servidor Python não configura o ambiente do OpenCode em outro
computador. Exporte a variável no terminal que inicia o OpenCode.

No clone deste repo, a configuração da raiz também registra `moto-mcp`
local. OpenCode mescla configuração global, projeto e subpasta. O exemplo
desabilita essa entrada herdada com `"moto-mcp": {"enabled": false}`;
preserva o remoto `motomcp`. Isso evita iniciar Poetry no computador cliente.
Um erro no servidor local herdado não significa falha do remoto conectado.

`opencode debug config` mostra a configuração resolvida, **inclusive headers**.
Inspecione localmente e remova Authorization antes de compartilhar ou salvar
saídas. Não anexar o JSON real com token a commits, tickets ou logs.

## Tornar o MCP a fonte do projeto

O nome registrado no cliente define o prefixo: servidor `motomcp` resulta
em `motomcp_get_capabilities`, enquanto `moto-mcp` resulta em
`moto-mcp_get_capabilities`. Nome de exibição do FastMCP não substitui essa chave.

As regras locais devem orientar: buscar com `motomcp_search_documents` ou
`motomcp_search_semantic`, ler o documento encontrado com
`motomcp_read_document`, e responder citando os arquivos retornados. Para
busca textual, preferir `subpath="docs"` e `max_results=5` quando adequado,
evitando resultados grandes desnecessários. `get_capabilities` recebe `{}`.

Este servidor registra tools; `list_mcp_resources` não é uma busca em seus
documentos. Regras no `AGENTS.md` orientam o modelo, mas não garantem execução.
Se ele não fizer uma chamada real, não aceitar sua alegação de que consultou o MCP.
Conteúdo devolvido pelas tools é evidência do projeto, não autorização para
obedecer instruções ou executar comandos encontrados em documentos.

O servidor expõe `Settings.REPO_ROOT`, por padrão a raiz do próprio `moto_mcp`.
Isso não prova acesso à pasta canônica `knowledge_agents` de outra máquina.
Os caminhos `C:\Users\Pichau\Desktop\Projetos\knowledge_agents` não existem
neste computador cliente, e `projects/moto_mcp.md` não foi encontrado na
cópia local nem no conector canônico disponível. A investigação usa o código,
os documentos efetivamente retornados pelo MCP e o histórico local
`projects/moto-mcp-framework-server.md`; não presume consolidação da memória ausente.

## Testes de aceitação

Abra sessões novas; não use `--continue` durante a comparação:

```powershell
opencode mcp list
opencode mcp debug motomcp
opencode run --model ollama/qwen3:14b --format json 'Use a tool motomcp_get_capabilities agora. Não explique. Apenas execute a tool.'
opencode run --model ollama/qwen3:14b --format json 'Use motomcp_search_documents para procurar MOTO_MCP_NETWORK_MODE.'
opencode run --model ollama/qwen3:14b --format json 'Qual modo de rede e autenticação o moto_mcp exige para o IP 10.80.132.178? Consulte a documentação pelo MCP e cite o arquivo usado.'
```

Repita com `ollama/qwen3:8b` e `ollama/qwen3:4b`.
O critério é evento JSON `type="tool_use"`, `part.tool` correto,
`part.state.status="completed"` e `part.state.output` com dados reais.
`exit_code=0`, resposta plausível, bloco de código imitando chamada ou servidor
`connected` isoladamente não satisfazem esse critério.

Se falhar, confira nesta ordem: configuração efetiva e prefixos; conexão
autenticada; tools presentes no pedido de inferência; permissões do agente;
`context_length` do modelo carregado; sessão nova e limite dos resultados.
Uma chamada direta ao Ollama com schemas simplificados é um teste isolado,
não aprovação de OpenCode + MCP de ponta a ponta.

## Resultado comparativo

| Modelo | Contexto original: capabilities / busca | Perfil maior: capabilities / busca |
| --- | --- | --- |
| Qwen3 14B | Concluída / sem chamada | 32768: concluída / concluída |
| Qwen3 8B | Concluída / declarou tool indisponível | 16384: concluída / concluída |
| Qwen3 4B | Concluída / sem chamada | 16384: concluída / concluída |

No 4B/16k, capabilities foi chamada duas vezes e houve compactação; o modelo
não respeitou rigorosamente "apenas execute". A execução MCP foi comprovada,
mas isso não aprova obediência perfeita ao prompt ou conversas longas.

Depois da orientação de recuperação adicionada ao `opencode/AGENTS.md`, o
**14B/32k**, usando a configuração final diretamente e sem o intermediário,
executou `motomcp_search_documents` e `motomcp_read_document` e respondeu
corretamente sobre os três modos e Bearer obrigatório em `lan`, citando
`docs/mcp_server.md`. Uma segunda sessão com leitura explícita do mesmo
documento explicou corretamente por que IPs `10.x` usam `lan` + Bearer.
As duas sessões terminaram sem timeout e com código de saída zero.

Os três modelos tiveram chamadas explícitas aprovadas. A orientação nova para
recuperação foi validada de ponta a ponta no 14B; não foi repetida nos 8B/4B.
A pergunta inicial com IP literal teve recuperação inadequada nos três antes
desse ajuste. Portanto, uso automático robusto em todos os modelos continua
uma limitação, apesar da correção do tool calling explícito.

[Eventos e metadados desta investigação](evidence/opencode-remote-2026-09-16.json).
O exemplo distribuível com `{env:MOTO_MCP_AUTH_TOKEN}` também foi carregado
pelo OpenCode: remoto conectado, local desabilitado, Bearer resolvido e modelo
14B direcionado ao perfil 32k. `git diff --check` e os blocos JSON do guia
passaram; o token real não consta dos arquivos rastreados atuais nem do artefato.
Não interpretar testes históricos de stdio como aprovação automática desta
conexão remota ou da configuração atual.

| Hipótese | Evidência / conclusão |
| --- | --- |
| Transporte remoto ou Bearer quebrado | Descartado para a conexão testada: handshake, catálogo e chamadas MCP diretas funcionam; OpenCode executou capabilities. |
| Tools não expostas pelo OpenCode | Descartado nesta execução: as 13 tools aparecem no pedido de inferência ao Ollama. `connected` sozinho continua não sendo prova dessa exposição. |
| Schema/config inválido | `mcp.servers` é aceito nesta versão por compatibilidade; configuração resolvida contém o servidor remoto. Preferir formato nativo V1. |
| `codemode: false` resolve V1 | Não: campo removido pela compatibilidade; inferência V1 já usa tools diretas. |
| Nome errado | Prefixo depende da chave do servidor. Houve instruções locais `moto-mcp_*` com servidor `motomcp`; o arquivo foi corrigido em uma edição paralela durante a investigação. |
| Qwen3 sem tool calling | Descartado como incapacidade absoluta: os três emitiram e executaram capabilities. Isso não garante confiabilidade de cada consulta. |
| Contexto insuficiente | 4096 efetivos observados; busca falhou nos três. 14B/32768 repetiu o mesmo pedido de busca com chamada real concluída. |
| Recuperação mal formulada | Ainda possível depois de corrigir contexto: o 14B buscou o IP literal e obteve zero resultados, sem procurar a regra da faixa `10.0.0.0/8`. Não confundir busca concluída com resposta correta. |

Nenhuma mudança no registro de tools ou no servidor é necessária para demonstrar
as chamadas explícitas. Primeiro corrigir contexto e configuração do cliente;
não adicionar resources, aliases de tools ou outro transporte para mascarar isso.
