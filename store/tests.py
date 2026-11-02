from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from store import catalog, orders, pricing
from store.models import Order, Product
from store.text import normalize


class LoadedDataTestCase(TestCase):
    """Usa os CSVs reais de data/ como massa de teste."""

    @classmethod
    def setUpTestData(cls):
        call_command('load_data', stdout=StringIO())


class NormalizeTests(SimpleTestCase):
    def test_normaliza_acentos_pontuacao_e_numeros(self):
        self.assertEqual(normalize('Violão Takamine GD-20'), 'violao takamine gd 20')
        self.assertEqual(normalize('GD20'), normalize('gd 20'))


class PricingTests(SimpleTestCase):
    def test_formato_brl(self):
        self.assertEqual(pricing.brl(2199), 'R$ 2.199,00')
        self.assertEqual(pricing.brl(Decimal('1234567.891')), 'R$ 1.234.567,89')

    def test_preco_promocional(self):
        info = pricing.price_info(Decimal('2399'), 18, 'Desconto Exclusivo')
        self.assertEqual(info.final, Decimal('1967.18'))
        self.assertEqual(info.as_dict()['preco_original'], 'R$ 2.399,00')

    def test_faixas_de_parcelamento(self):
        cases = {49: 1, 100: 2, 150: 3, 479: 5, 480: 6, 1199: 11, 1200: 12, 50000: 12}
        for total, expected in cases.items():
            with self.subTest(total=total):
                self.assertEqual(pricing.max_installments(total), expected)

    def test_pix_nao_acumula_com_promocao(self):
        conditions = pricing.payment_conditions(total=1000, promo_total=400)
        self.assertEqual(conditions['pix']['valor'], 'R$ 970,00')  # 5% só sobre os R$ 600 sem promoção
        self.assertIn('observacao', conditions['pix'])

    def test_frete_e_pagamento_combinado(self):
        self.assertEqual(pricing.payment_conditions(500)['frete_regiao_metropolitana_campo_grande'], 'R$ 35,00')
        self.assertEqual(pricing.payment_conditions(500.01)['frete_regiao_metropolitana_campo_grande'], 'Grátis')
        self.assertFalse(pricing.payment_conditions(2000)['pode_combinar_formas_de_pagamento'])
        self.assertTrue(pricing.payment_conditions(2000.01)['pode_combinar_formas_de_pagamento'])

    def test_rotulo_forma_de_pagamento(self):
        self.assertEqual(pricing.payment_method_label('credit_12x'), 'Cartão de crédito em 12x')
        self.assertEqual(pricing.payment_method_label('pix'), 'PIX')


class LoadDataTests(LoadedDataTestCase):
    def test_contagens_e_campo_de_busca(self):
        self.assertEqual(Product.objects.count(), 65)
        self.assertEqual(Order.objects.count(), 20)
        self.assertEqual(Product.objects.get(pk=95).search_name, 'takamine gd 20 dreadnought natural violoes')

    def test_recarregar_e_idempotente(self):
        call_command('load_data', stdout=StringIO())
        self.assertEqual(Product.objects.count(), 65)


class CatalogTests(LoadedDataTestCase):
    def test_encontra_produto_com_variacoes_de_escrita(self):
        for reference in ['Takamine GD20', 'takamine gd 20', 'TAKAMINE GD-20', '95']:
            with self.subTest(reference=reference):
                product, _ = catalog.find(reference)
                self.assertEqual(product.pk, 95)

    def test_referencia_ambigua_retorna_candidatos(self):
        product, candidates = catalog.find('Taylor')
        self.assertIsNone(product)
        self.assertEqual({p.pk for p in candidates}, {94, 106})

    def test_busca_por_categoria_e_preco_final(self):
        result = catalog.search(category='violao', max_price=1000, limit=50)
        self.assertEqual(result['total_encontrado'], 12)
        self.assertTrue(all(p['categoria'] == 'Violões' and p['disponivel'] for p in result['produtos']))
        self.assertNotIn(96, [p['id'] for p in result['produtos']])  # esgotado

    def test_preco_com_promocao_ativa(self):
        product, _ = catalog.find('Crafter HT-100')
        data = catalog.summary(product)
        self.assertEqual((data['preco_original'], data['desconto'], data['preco']), ('R$ 2.399,00', '18%', 'R$ 1.967,18'))

    def test_promocao_inativa_nao_e_aplicada(self):
        product, _ = catalog.find('Takamine GD20')
        self.assertEqual(catalog.summary(product)['preco'], 'R$ 2.199,00')
        self.assertNotIn('desconto', catalog.summary(product))

    def test_indisponiveis_sao_sinalizados(self):
        result = catalog.search(term='shelby 7 cordas')
        self.assertEqual(result['produtos'], [])
        self.assertEqual(result['fora_de_venda']['produtos'][0]['id'], 113)
        self.assertTrue(result['alternativas'])  # nada disponível: sugere semelhantes

    def test_paginacao_explica_os_nao_listados(self):
        result = catalog.search(category='Violões', max_price=1000)
        self.assertEqual((result['total_encontrado'], len(result['produtos'])), (12, 5))
        self.assertIn('Os outros 7', result['observacao'])
        self.assertIn('NÃO entram no total', result['fora_de_venda']['aviso'])

    def test_situacoes_de_disponibilidade(self):
        situations = {
            96: 'Esgotado',  # ativo sem estoque
            113: 'Fora de linha',  # descontinuado
            130: 'Em breve',  # coming_soon com estoque
            136: 'Fora de linha',  # descontinuado com estoque
        }
        for pk, expected in situations.items():
            with self.subTest(pk=pk):
                availability = catalog.availability(Product.objects.get(pk=pk))
                self.assertFalse(availability['disponivel'])
                self.assertTrue(availability['situacao'].startswith(expected))

    def test_detalhes_de_indisponivel_trazem_alternativas(self):
        data = catalog.details(Product.objects.get(pk=96))
        self.assertTrue(data['alternativas'])
        self.assertTrue(all(a['disponivel'] and a['categoria'] == 'Violões' for a in data['alternativas']))


class OrderTests(LoadedDataTestCase):
    def test_verificacao_por_email_ou_telefone(self):
        # Pedido 4 é do cliente 1: lucas.mendes@jmail.com / (67) 99812-3456
        for contact in ['lucas.mendes@jmail.com', 'LUCAS.MENDES@JMAIL.COM', '(67) 99812-3456', '998123456']:
            with self.subTest(contact=contact):
                self.assertIsNotNone(orders.find_order('4', contact))

    def test_contato_errado_ou_pedido_inexistente(self):
        for number, contact in [('4', 'outra@pessoa.com'), ('4', '3456'), ('999', 'lucas.mendes@jmail.com'), ('abc', 'x')]:
            with self.subTest(number=number, contact=contact):
                self.assertIsNone(orders.find_order(number, contact))

    def test_prazos_de_pedido_entregue(self):
        order = Order.objects.get(pk=4)  # entregue, previsão 2025-12-22, compra 2025-12-10
        inside = orders.return_windows(order, today=date(2025, 12, 25))
        self.assertTrue(inside['arrependimento']['dentro_do_prazo'])
        self.assertEqual(inside['arrependimento']['dias_restantes'], 4)
        self.assertTrue(inside['troca_por_defeito']['dentro_do_prazo'])

        outside = orders.return_windows(order, today=date(2026, 11, 2))
        self.assertFalse(outside['arrependimento']['dentro_do_prazo'])
        self.assertFalse(outside['garantia_legal']['dentro_do_prazo'])
        self.assertIn('fabricante', outside['observacao'])

    def test_pedido_nao_entregue_e_cancelado(self):
        shipped = orders.return_windows(Order.objects.get(pk=8), today=date(2026, 2, 20))
        self.assertNotIn('arrependimento', shipped)
        cancelled = orders.return_windows(Order.objects.get(pk=17), today=date(2026, 2, 20))
        self.assertIn('cancelado', cancelled['observacao'])

    def test_detalhes_do_pedido(self):
        data = orders.order_details(Order.objects.get(pk=15), today=date(2026, 3, 20))
        self.assertEqual(data['status'], 'Aguardando pagamento')
        self.assertEqual(len(data['itens']), 2)
        self.assertEqual(data['forma_pagamento'], 'Cartão de crédito em 12x')
