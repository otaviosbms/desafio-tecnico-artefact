"""Contrato das ferramentas.

Uma definição, dois usos: o `input_model` (Pydantic) gera o schema enviado ao LLM e valida os
argumentos que ele mandou. O schema passa por `parameters_schema`, que tira o que o Pydantic
acrescenta e o modelo não precisa (títulos, defaults, `anyOf` com `null`, `$ref`).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from llm import function_tool


@dataclass(frozen=True)
class ToolContext:
    now: datetime  # relógio da conversa (real ou simulado)
    thread_id: str = ''
    turn_id: str = ''


@dataclass
class ToolResult:
    data: dict | None = None  # payload para o modelo
    error: str | None = None  # código: not_found, ambiguous, verification_failed, tool_invalid_args, ...
    error_message: str | None = None  # texto para o modelo se corrigir (vai como "erro")
    transfer_to_human: bool = False  # pede transferência para a equipe
    meta: dict = field(default_factory=dict)  # dados para o rastro, nunca vão ao LLM

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_model_payload(self) -> dict:
        """O que vira a mensagem `role=tool`. Erros vão como {"erro": ...}, para o modelo se corrigir."""
        payload = dict(self.data or {})
        if self.error_message:
            payload['erro'] = self.error_message
        return payload


class ToolInput(BaseModel):
    # Modelos às vezes mandam números onde o schema pede texto ("numero_pedido": 4).
    model_config = ConfigDict(coerce_numbers_to_str=True)


class ToolHandler(ABC):
    name: ClassVar[str]
    description: ClassVar[str]  # QUANDO usar a ferramenta (o modelo decide por aqui)
    input_model: ClassVar[type[ToolInput]]

    @abstractmethod
    def execute(self, ctx: ToolContext, args: ToolInput) -> ToolResult: ...

    def parameters(self) -> dict[str, Any]:
        """Schema dos argumentos. Sobrescreva para partes dinâmicas (ex.: categorias do banco)."""
        return parameters_schema(self.input_model)

    def definition(self) -> dict[str, Any]:
        return function_tool(self.name, self.description, self.parameters())


DROPPED_KEYS = {'title', 'default'}


def parameters_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    defs = schema.pop('$defs', {})

    def visit(node):
        if isinstance(node, list):
            return [visit(item) for item in node]
        if not isinstance(node, dict):
            return node
        if '$ref' in node:
            node = {**defs[node['$ref'].rsplit('/', 1)[-1]], **{k: v for k, v in node.items() if k != '$ref'}}
        variants = node.get('anyOf')
        if variants and any(v.get('type') == 'null' for v in variants):
            rest = [v for v in variants if v.get('type') != 'null']
            if len(rest) == 1:  # Optional[X] -> X (opcional = fora de `required`)
                node = {**rest[0], **{k: v for k, v in node.items() if k != 'anyOf'}}
        result = {}
        for key, value in node.items():
            if key in DROPPED_KEYS:
                continue
            if key == 'properties':  # nomes de campos, não palavras-chave do schema
                result[key] = {name: visit(prop) for name, prop in value.items()}
            else:
                result[key] = visit(value)
        return result

    return visit(schema)
