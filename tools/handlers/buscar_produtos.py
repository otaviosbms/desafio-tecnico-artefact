from pydantic import Field

from store import catalog
from store.models import Category

from ..contracts import ToolContext, ToolHandler, ToolInput, ToolResult


class BuscarProdutosInput(ToolInput):
    termo: str | None = Field(None, description='Nome, marca ou característica (ex.: "yamaha", "7 cordas", "elétrico").')
    categoria: str | None = None
    preco_min: float | None = Field(None, description='Preço mínimo em reais.')
    preco_max: float | None = Field(None, description='Preço máximo em reais.')
    apenas_disponiveis: bool = Field(True, description='Padrão true: só itens à venda e em estoque.')
    limite: int = Field(5, description='Máximo de resultados (padrão 5, máx. 20).')


class BuscarProdutos(ToolHandler):
    name = 'buscar_produtos'
    description = (
        'Busca instrumentos no catálogo da loja por nome/marca/tipo, categoria e faixa de preço. '
        'Use para perguntas como "quais violões até R$ 1000?" ou "vocês têm guitarra Fender?". '
        'Retorna preço atual (já com promoção, se houver) e disponibilidade em estoque.'
    )
    input_model = BuscarProdutosInput

    def parameters(self):
        schema = super().parameters()
        # As categorias vêm do banco, então o enum é montado na hora.
        names = list(Category.objects.order_by('name').values_list('name', flat=True))
        schema['properties']['categoria'] = {'type': 'string', 'enum': names}
        return schema

    def execute(self, ctx: ToolContext, args: BuscarProdutosInput) -> ToolResult:
        result = catalog.search(
            term=args.termo,
            category=args.categoria,
            min_price=args.preco_min,
            max_price=args.preco_max,
            only_available=args.apenas_disponiveis,
            limit=max(1, min(args.limite, 20)),
        )
        if 'erro' in result:  # categoria inexistente
            message = result.pop('erro')
            return ToolResult(data=result, error='not_found', error_message=message)
        return ToolResult(data=result)
