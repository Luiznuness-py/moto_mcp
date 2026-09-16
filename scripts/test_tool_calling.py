#!/usr/bin/env python
# scripts/test_tool_calling.py
#
# Testa se um modelo do Ollama emite tool_calls estruturado de verdade
# — mesmo método usado manualmente pra descartar/confirmar
# qwen2.5-coder:14b, qwen3:4b/8b/14b e mistral-nemo:12b (ver to-do.md).
# Chama a API nativa do Ollama (/api/chat) direto, sem OpenCode no
# meio.
#
# Uso:
#   poetry run python scripts/test_tool_calling.py qwen3:8b
#   poetry run python scripts/test_tool_calling.py qwen3:8b --host http://192.168.1.10:11434
#
# IMPORTANTE — o que este script prova e o que NÃO prova:
# Passar aqui confirma que o modelo consegue emitir tool_calls
# estruturado quando as tools são a única coisa no prompt (teste
# isolado, ~10 tools reais do moto_mcp). NÃO prova que funciona dentro
# do OpenCode de verdade — o OpenCode soma um system prompt próprio +
# ferramentas nativas (bash/edit/grep/etc.) ao pedido, e isso já se
# mostrou capaz de quebrar um modelo que passa aqui (mistral-nemo:12b
# passou isolado — não testado antes deste script existir — mas falhou
# de verdade dentro do OpenCode, inventando uma chamada de tool que
# nunca executou). Trate isto como um filtro rápido de descarte (se
# falhar aqui, com certeza falha no OpenCode também), não como
# aprovação final — confirme sempre com `opencode run` de verdade
# antes de recomendar um modelo.

from __future__ import annotations

import argparse
import sys

import httpx

# Subconjunto representativo das tools reais do moto_mcp (mesmo
# esquema usado nos testes manuais desta sessão) — não é o conjunto
# completo nem inclui o overhead de system prompt do OpenCode, ver
# aviso acima.
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "Lista arquivos/pastas do repositorio",
            "parameters": {
                "type": "object",
                "properties": {"subpath": {"type": "string"}, "recursive": {"type": "boolean"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Le um arquivo md/txt",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Busca texto no repositorio",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_agents",
            "description": "Lista os agentes definidos em agents/",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Busca na internet via SearXNG",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_semantic",
            "description": "Busca por sentido no repositorio",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reindex_search",
            "description": "Reindexa o repositorio",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_template",
            "description": "Retorna um template",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_entry",
            "description": "Registra um projeto/cliente novo",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_capabilities",
            "description": "Catalogo de tools deste servidor",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def check_tool_call(host: str, model: str, prompt: str, expected_tool: str) -> tuple[bool, str]:
    """Manda `prompt` pro modelo com as tools acima disponíveis; devolve
    (passou, detalhe) — passou = True só se `tool_calls` veio
    estruturado e chamou exatamente `expected_tool`."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "tools": _TOOLS,
        "stream": False,
    }
    try:
        resp = httpx.post(f"{host}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return False, f"Falha de conexão com o Ollama em '{host}': {exc}"

    message = resp.json().get("message", {})
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        leaked = (message.get("content") or "").strip()
        return False, f"Nenhum tool_calls estruturado. content vazou como texto: {leaked[:200]!r}"

    called_names = [tc.get("function", {}).get("name") for tc in tool_calls]
    if expected_tool not in called_names:
        return False, f"Chamou tool errada: {called_names} (esperado: {expected_tool!r})"

    return True, f"OK — chamou {called_names}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Testa se um modelo do Ollama faz tool-calling estruturado de verdade.")
    parser.add_argument("model", help="nome do modelo no Ollama, ex: qwen3:8b")
    parser.add_argument("--host", default="http://127.0.0.1:11434", help="endereço do Ollama (padrão: local)")
    args = parser.parse_args()

    cases = [
        ("Chame a funcao list_agents (sem argumentos) e me diga o retorno exato.", "list_agents"),
        ("Preciso saber quais agentes existem nesse repositorio. Use a ferramenta adequada.", "list_agents"),
    ]

    print(f"Testando '{args.model}' em {args.host} — {len(_TOOLS)} tools disponíveis (subconjunto representativo do moto_mcp, ver aviso no topo do script).\n")

    all_passed = True
    for prompt, expected in cases:
        passed, detail = check_tool_call(args.host, args.model, prompt, expected)
        status = "PASSOU" if passed else "FALHOU"
        print(f"[{status}] {prompt}\n         {detail}\n")
        all_passed = all_passed and passed

    print("=" * 60)
    if all_passed:
        print(f"'{args.model}' passou no teste isolado de tool-calling.")
        print("Isso NÃO garante funcionamento dentro do OpenCode de verdade —")
        print("confirme com `opencode run` antes de recomendar este modelo.")
    else:
        print(f"'{args.model}' FALHOU — não recomendado para tool-calling com o moto_mcp.")
        sys.exit(1)


if __name__ == "__main__":
    main()
