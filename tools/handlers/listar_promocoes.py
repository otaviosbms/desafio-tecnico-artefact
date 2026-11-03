from store import catalog
from store.models import Product, Promotion

from ..contracts import ToolContext, ToolHandler, ToolInput, ToolResult


class ListarPromocoesInput(ToolInput):
    pass


class ListarPromocoes(ToolHandler):
    name = 'listar_promocoes'
    description = (
        'Lista as promoções ativas no momento, com preço original, desconto e preço final. '
        'Use quando o cliente perguntar sobre ofertas ou promoções.'
    )
    input_model = ListarPromocoesInput

    def execute(self, ctx: ToolContext, args: ListarPromocoesInput) -> ToolResult:
        promotions = Promotion.objects.filter(is_active=True).values_list('product_id', flat=True)
        products = catalog.with_prices(Product.objects.filter(pk__in=promotions)).order_by('final_price')
        return ToolResult(data={
            'promocoes_ativas': [catalog.summary(p) for p in products],
            'regras': 'Promoções não são cumulativas: o desconto do PIX não vale sobre preço promocional.',
        })
