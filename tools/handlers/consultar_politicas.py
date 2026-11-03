from pydantic import Field, field_validator

from knowledge.policies import TOPICS, consultar_politicas

from ..contracts import ToolContext, ToolHandler, ToolInput, ToolResult


class ConsultarPoliticasInput(ToolInput):
    # Sem Literal de propósito: um tópico inválido volta com a lista dos válidos (ver consultar_politicas).
    topicos: list[str] = Field(json_schema_extra={'items': {'type': 'string', 'enum': list(TOPICS)}, 'minItems': 1})

    @field_validator('topicos', mode='before')
    @classmethod
    def _um_topico_vira_lista(cls, value):
        return [value] if isinstance(value, str) else value


class ConsultarPoliticas(ToolHandler):
    name = 'consultar_politicas'
    description = (
        'Consulta o manual de políticas da loja. Use para dúvidas sobre regras e informações gerais '
        '(não para preço/estoque de produtos nem status de pedidos). Pode pedir vários tópicos de uma vez. '
        'Tópicos: ' + '; '.join(f'{name} ({desc})' for name, desc in TOPICS.items()) + '.'
    )
    input_model = ConsultarPoliticasInput

    def execute(self, ctx: ToolContext, args: ConsultarPoliticasInput) -> ToolResult:
        result = consultar_politicas(args.topicos, now=ctx.now)
        if 'erro' in result:
            return ToolResult(error='invalid_topic', error_message=result['erro'])
        return ToolResult(data=result)
