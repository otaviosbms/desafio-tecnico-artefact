from pydantic import Field

from store import catalog

from ..contracts import ToolContext, ToolHandler, ToolInput, ToolResult


class DetalhesProdutoInput(ToolInput):
    produto: str = Field(description='Nome do produto ou id.')


class DetalhesProduto(ToolHandler):
    name = 'detalhes_produto'
    description = (
        'Detalhes de um produto específico: preço (com promoção ativa, se houver), estoque, descrição e '
        'especificações. Se estiver indisponível, já traz alternativas semelhantes. '
        'Use quando o cliente perguntar sobre um modelo específico (ex.: "quanto custa o Takamine GD20?").'
    )
    input_model = DetalhesProdutoInput

    def execute(self, ctx: ToolContext, args: DetalhesProdutoInput) -> ToolResult:
        product, candidates = catalog.find(args.produto)
        if product:
            return ToolResult(data=catalog.details(product))
        if candidates:
            return ToolResult(error='ambiguous', data={
                'ambiguo': True,
                'mensagem': 'Mais de um produto corresponde. Pergunte ao cliente qual deles.',
                'candidatos': [catalog.summary(p) for p in candidates],
            })
        return ToolResult(
            error='not_found',
            error_message=f'Nenhum produto encontrado para "{args.produto}". Tente buscar_produtos com outro termo.',
        )
