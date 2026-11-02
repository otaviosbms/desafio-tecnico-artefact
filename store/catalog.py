"""Consultas ao catálogo: busca aproximada, preços com promoção e disponibilidade."""

from difflib import SequenceMatcher

from django.db import connection
from django.db.models import DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce

from .models import Category, Product, Promotion
from .pricing import price_info
from .text import normalize

STOPWORDS = {'de', 'da', 'do', 'das', 'dos', 'para', 'com', 'e', 'o', 'a', 'os', 'as', 'um', 'uma', 'em'}
MIN_SCORE = 0.5
RELATIVE_SCORE = 0.75  # descarta resultados bem piores que o melhor
AMBIGUITY_MARGIN = 0.1
LOW_STOCK = 2


def with_prices(queryset):
    """Anota desconto ativo e preço final (promoções não são cumulativas: vale a maior)."""
    best_promo = Promotion.objects.filter(product=OuterRef('pk'), is_active=True).order_by('-discount_percent')
    discount = Coalesce(Subquery(best_promo.values('discount_percent')[:1]), Value(0))
    return queryset.select_related('category').annotate(
        discount=discount,
        promotion_name=Subquery(best_promo.values('description')[:1]),
        final_price=ExpressionWrapper(
            F('price_brl') * (Value(100) - discount) / Value(100),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        ),
    )


def available_q():
    return Q(status=Product.Status.ACTIVE, stock_quantity__gt=0)


def availability(product: Product) -> dict:
    if product.status == Product.Status.DISCONTINUED:
        return {'disponivel': False, 'situacao': 'Fora de linha: não faz mais parte do catálogo.'}
    if product.status == Product.Status.COMING_SOON:
        return {'disponivel': False, 'situacao': 'Em breve: ainda não está à venda.'}
    if product.stock_quantity == 0:
        return {'disponivel': False, 'situacao': 'Esgotado no momento.'}
    situacao = 'Últimas unidades em estoque.' if product.stock_quantity <= LOW_STOCK else 'Disponível em estoque.'
    return {'disponivel': True, 'situacao': situacao, 'estoque': product.stock_quantity}


def product_price(product: Product):
    """Preço do produto; usa as anotações de `with_prices` quando existirem."""
    if hasattr(product, 'discount'):
        return price_info(product.price_brl, product.discount, product.promotion_name)
    promo = product.promotions.filter(is_active=True).order_by('-discount_percent').first()
    return price_info(product.price_brl, promo and promo.discount_percent, promo and promo.description)


def summary(product: Product) -> dict:
    return {
        'id': product.id,
        'nome': product.name,
        'categoria': product.category.name,
        **product_price(product).as_dict(),
        **availability(product),
    }


def _tokens(term: str) -> list[str]:
    return [t for t in normalize(term).split() if t not in STOPWORDS]


def _python_score(tokens: list[str], search_name: str) -> float:
    """Fallback sem pg_trgm: média, por termo, da melhor semelhança com uma palavra do nome."""
    words = search_name.split()

    def token_score(token):
        best = max(
            (1.0 if len(token) >= 3 and w.startswith(token) else SequenceMatcher(None, token, w).ratio())
            for w in words
        )
        return best if best >= 0.6 else 0.0  # termo sem correspondência não soma pontos

    return sum(token_score(t) for t in tokens) / len(tokens)


def scored(queryset, term: str) -> list[tuple[Product, float]]:
    """(produto, pontuação) ordenados por semelhança com o termo, sem os resultados fracos."""
    tokens = _tokens(term)
    if not tokens:
        return [(p, 1.0) for p in queryset]

    if connection.vendor == 'postgresql':
        from django.contrib.postgres.search import TrigramWordSimilarity

        similarity = sum(TrigramWordSimilarity(t, 'search_name') for t in tokens[1:]) + TrigramWordSimilarity(tokens[0], 'search_name')
        results = [(p, p.score) for p in queryset.annotate(score=similarity / len(tokens))]
    else:
        results = [(p, _python_score(tokens, p.search_name)) for p in queryset]

    if not results:
        return []
    cutoff = max(MIN_SCORE, max(s for _, s in results) * RELATIVE_SCORE)
    results = [(p, s) for p, s in results if s >= cutoff]
    results.sort(key=lambda ps: (-ps[1], ps[0].final_price))
    return results


def resolve_category(name: str) -> Category | None:
    """Aceita variações ("violao", "Violões", "ukulele")."""
    wanted = normalize(name)
    best, best_score = None, 0.0
    for category in Category.objects.all():
        candidate = normalize(category.name)
        score = 1.0 if wanted and (wanted in candidate or candidate in wanted) else SequenceMatcher(None, wanted, candidate).ratio()
        if score > best_score:
            best, best_score = category, score
    return best if best_score >= 0.6 else None


def search(term=None, category=None, min_price=None, max_price=None, only_available=True, limit=5) -> dict:
    queryset = with_prices(Product.objects.all())
    if category:
        cat = resolve_category(category)
        if cat is None:
            names = ', '.join(Category.objects.values_list('name', flat=True))
            return {'produtos': [], 'erro': f'Categoria "{category}" não encontrada. Categorias: {names}.'}
        queryset = queryset.filter(category=cat)
    if min_price is not None:
        queryset = queryset.filter(final_price__gte=min_price)
    if max_price is not None:
        queryset = queryset.filter(final_price__lte=max_price)

    products = [p for p, _ in scored(queryset, term)] if term else list(queryset.order_by('final_price'))
    available = [p for p in products if p.is_available]
    unavailable = [p for p in products if not p.is_available]
    shown = available if only_available else products

    result = {
        'total_encontrado': len(shown),
        'produtos': [summary(p) for p in shown[:limit]],
    }
    if len(shown) > limit:
        result['observacao'] = (
            f'Listados {limit} de {len(shown)}. Os outros {len(shown) - limit} também atendem à busca '
            f'(e estão disponíveis, se apenas_disponiveis=true); para vê-los, aumente o limite ou refine a busca.'
        )
    if only_available and unavailable:
        # Ajuda o agente a dizer "esgotado/fora de linha" em vez de "não temos".
        result['fora_de_venda'] = {
            'aviso': 'Também correspondem à busca, mas NÃO estão à venda e NÃO entram no total acima.',
            'produtos': [{'id': p.id, 'nome': p.name, **availability(p)} for p in unavailable[:5]],
        }
        if not available:
            # Política 7.3: produto indisponível -> sugerir alternativas semelhantes.
            result['alternativas'] = alternatives(unavailable[0])
    return result


def alternatives(product: Product, limit=3) -> list[dict]:
    """Produtos disponíveis da mesma categoria, com preço próximo."""
    price = product_price(product).final
    queryset = with_prices(Product.objects.filter(available_q(), category=product.category_id).exclude(pk=product.pk))
    closest = sorted(queryset, key=lambda p: abs(p.final_price - price))[:limit]
    return [summary(p) for p in closest]


def find(reference) -> tuple[Product | None, list[Product]]:
    """Encontra um produto por id ou nome. Retorna (produto, candidatos se ambíguo)."""
    queryset = with_prices(Product.objects.all())
    if str(reference).strip().isdigit():
        product = queryset.filter(pk=int(reference)).first()
        if product:
            return product, []
    matches = scored(queryset, str(reference))
    if not matches:
        return None, []
    # Encontrado só se houver um resultado claramente melhor que o segundo.
    if len(matches) == 1 or matches[0][1] - matches[1][1] >= AMBIGUITY_MARGIN:
        return matches[0][0], []
    best = matches[0][1]
    return None, [p for p, s in matches if best - s < AMBIGUITY_MARGIN][:5]


def details(product: Product) -> dict:
    data = summary(product)
    data.update({
        'descricao': product.description,
        'especificacoes': product.specs,
    })
    if not data['disponivel']:
        data['alternativas'] = alternatives(product)
    return data
