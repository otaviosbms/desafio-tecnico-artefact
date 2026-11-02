from django.db import models

from .text import normalize


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'categoria'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Ativo'
        COMING_SOON = 'coming_soon', 'Em breve'
        DISCONTINUED = 'discontinued', 'Descontinuado'

    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    description = models.TextField(blank=True)
    price_brl = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    specs = models.JSONField(default=dict, blank=True)
    created_at = models.DateField(null=True, blank=True)
    # Nome + categoria normalizados (ver store.text.normalize), usado na busca.
    search_name = models.CharField(max_length=300, blank=True, editable=False)

    class Meta:
        verbose_name = 'produto'
        ordering = ['name']

    def __str__(self):
        return self.name

    def build_search_name(self):
        return normalize(f'{self.name} {self.category.name}')

    def save(self, *args, **kwargs):
        self.search_name = self.build_search_name()
        super().save(*args, **kwargs)

    @property
    def is_available(self):
        return self.status == self.Status.ACTIVE and self.stock_quantity > 0


class Promotion(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='promotions')
    discount_percent = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=100)
    is_active = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'promoção'
        verbose_name_plural = 'promoções'

    def __str__(self):
        return f'{self.description} - {self.product} ({self.discount_percent}%)'


class Customer(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    city = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'cliente'
        ordering = ['name']

    def __str__(self):
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Aguardando pagamento'
        CONFIRMED = 'confirmed', 'Pagamento confirmado'
        SHIPPED = 'shipped', 'Enviado'
        DELIVERED = 'delivered', 'Entregue'
        CANCELLED = 'cancelled', 'Cancelado'

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    order_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices)
    total_brl = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=30)
    tracking_code = models.CharField(max_length=20, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'pedido'
        ordering = ['-order_date']

    def __str__(self):
        return f'Pedido #{self.pk}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'item do pedido'
        verbose_name_plural = 'itens do pedido'

    def __str__(self):
        return f'{self.quantity}x {self.product}'
