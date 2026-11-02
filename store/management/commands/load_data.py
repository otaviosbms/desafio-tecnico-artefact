import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand
from django.core.management.color import no_style
from django.db import connection, transaction

from store.models import Category, Customer, Order, OrderItem, Product, Promotion


def _read_csv(path):
    with open(path, encoding='utf-8', newline='') as f:
        # Remove espaços extras de chaves e valores; vazio vira None.
        return [
            {k.strip(): (v.strip() or None) if v is not None else None for k, v in row.items()}
            for row in csv.DictReader(f)
        ]


def _date(value):
    return date.fromisoformat(value) if value else None


class Command(BaseCommand):
    help = 'Carrega os CSVs da pasta data/ no banco (idempotente: recria todos os registros).'

    def add_arguments(self, parser):
        parser.add_argument('--data-dir', default=settings.BASE_DIR / 'data', type=Path)

    @transaction.atomic
    def handle(self, *args, data_dir, **options):
        for model in (OrderItem, Order, Promotion, Product, Customer, Category):
            model.objects.all().delete()

        Category.objects.bulk_create(
            Category(id=int(r['category_id']), name=r['name'], description=r['description'] or '')
            for r in _read_csv(data_dir / 'categories.csv')
        )

        Product.objects.bulk_create(
            Product(
                id=int(r['product_id']),
                name=r['name'],
                category_id=int(r['category_id']),
                description=r['description'] or '',
                price_brl=Decimal(r['price_brl']),
                stock_quantity=int(r['stock_quantity'] or 0),
                status=r['status'],
                specs=json.loads(r['specs']) if r['specs'] else {},
                created_at=_date(r['created_at']),
            )
            for r in _read_csv(data_dir / 'products.csv')
        )

        Promotion.objects.bulk_create(
            Promotion(
                id=int(r['promotion_id']),
                product_id=int(r['product_id']),
                discount_percent=int(r['discount_percent']),
                description=r['description'],
                is_active=r['is_active'] == '1',
            )
            for r in _read_csv(data_dir / 'promotions.csv')
        )

        Customer.objects.bulk_create(
            Customer(
                id=int(r['customer_id']),
                name=r['name'],
                phone=r['phone'],
                email=r['email'].lower(),
                city=r['city'],
            )
            for r in _read_csv(data_dir / 'customers.csv')
        )

        Order.objects.bulk_create(
            Order(
                id=int(r['order_id']),
                customer_id=int(r['customer_id']),
                order_date=_date(r['order_date']),
                status=r['status'],
                total_brl=Decimal(r['total_brl']),
                payment_method=r['payment_method'],
                tracking_code=r['tracking_code'] or '',
                estimated_delivery=_date(r['estimated_delivery']),
                notes=r['notes'] or '',
            )
            for r in _read_csv(data_dir / 'orders.csv')
        )

        OrderItem.objects.bulk_create(
            OrderItem(
                order_id=int(r['order_id']),
                product_id=int(r['product_id']),
                quantity=int(r['quantity']),
            )
            for r in _read_csv(data_dir / 'order_items.csv')
        )

        # Como os IDs vieram dos CSVs, ajusta as sequences (necessário no Postgres).
        models = [Category, Product, Promotion, Customer, Order, OrderItem]
        with connection.cursor() as cursor:
            for statement in connection.ops.sequence_reset_sql(no_style(), models):
                cursor.execute(statement)

        for model in models:
            self.stdout.write(f'{model._meta.verbose_name_plural}: {model.objects.count()}')
        self.stdout.write(self.style.SUCCESS('Dados carregados com sucesso.'))
