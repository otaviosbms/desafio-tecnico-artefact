from store import orders

from ..contracts import ToolContext, ToolHandler, ToolInput, ToolResult


class ConsultarPedidoInput(ToolInput):
    numero_pedido: str
    email_ou_telefone: str


class ConsultarPedido(ToolHandler):
    name = 'consultar_pedido'
    description = (
        'Consulta status, itens, rastreio e prazos de troca/devolução/garantia de um pedido. '
        'Exige o número do pedido E o e-mail ou telefone do cadastro do cliente (proteção de dados). '
        'Se o cliente não informou os dois, peça antes de chamar.'
    )
    input_model = ConsultarPedidoInput

    def execute(self, ctx: ToolContext, args: ConsultarPedidoInput) -> ToolResult:
        order = orders.find_order(args.numero_pedido, args.email_ou_telefone)
        if order is None:
            # Mesma resposta para "pedido não existe" e "dados não conferem": não revela qual dos dois.
            return ToolResult(
                error='verification_failed',
                error_message='Não encontramos um pedido com esse número para o e-mail/telefone informado. '
                              'Peça ao cliente para conferir os dados.',
            )
        return ToolResult(data=orders.order_details(order, ctx.now.date()))
