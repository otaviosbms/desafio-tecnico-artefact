from django.contrib import admin

from .models import Category, Customer, Order, OrderItem, Product, Promotion


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'price_brl', 'stock_quantity', 'status']
    list_filter = ['category', 'status']
    search_fields = ['name']


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'description', 'discount_percent', 'is_active']
    list_filter = ['is_active']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'phone', 'city']
    search_fields = ['name', 'email']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'order_date', 'status', 'total_brl', 'payment_method']
    list_filter = ['status']
    inlines = [OrderItemInline]
