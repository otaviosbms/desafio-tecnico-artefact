"""Uma ferramenta por arquivo. A ordem de `TOOLS` é a ordem dos schemas enviados ao modelo."""

from .buscar_produtos import BuscarProdutos
from .condicoes_pagamento import CondicoesPagamento
from .consultar_pedido import ConsultarPedido
from .consultar_politicas import ConsultarPoliticas
from .detalhes_produto import DetalhesProduto
from .listar_promocoes import ListarPromocoes

TOOLS = [
    BuscarProdutos(),
    DetalhesProduto(),
    ListarPromocoes(),
    CondicoesPagamento(),
    ConsultarPedido(),
    ConsultarPoliticas(),
]
