from core.text import has_contact
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
        'Se o cliente ainda não informou os dois nesta conversa, NÃO chame: peça o que falta. '
        'Nunca preencha o contato com valor vazio ou inventado.'
    )
    input_model = ConsultarPedidoInput

    def execute(self, ctx: ToolContext, args: ConsultarPedidoInput) -> ToolResult:
        if not has_contact(args.email_ou_telefone):
            return ToolResult(
                error='missing_contact',
                error_message='Falta o e-mail ou telefone do cadastro. Peça ao cliente; não diga que o '
                              'pedido não foi encontrado.',
            )
        order = orders.find_order(args.numero_pedido, args.email_ou_telefone)
        if order is None:
            # Mesma resposta para "pedido não existe" e "dados não conferem": não revela qual dos dois.
            return ToolResult(
                error='verification_failed',
                error_message='Não encontramos um pedido com esse número para o e-mail/telefone informado. '
                              'Peça ao cliente para conferir os dados.',
            )
        return ToolResult(data=orders.order_details(order, ctx.now.date()))
