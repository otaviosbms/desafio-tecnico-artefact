"""Ferramentas que o agente pode chamar (function calling).

- `contracts.py`: o contrato de uma ferramenta (`ToolHandler`), o contexto (`ToolContext`) e o
  resultado (`ToolResult`);
- `registry.py`: o registro central, preenchido no `ready()` do app com `handlers.TOOLS`;
- `executor.py`: valida os argumentos, executa e devolve um `ToolResult`; nunca lança;
- `handlers/`: um arquivo por ferramenta. Os handlers são finos: as regras ficam em `store/` e
  `knowledge/`.
"""
