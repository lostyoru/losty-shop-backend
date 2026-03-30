from django.contrib import admin
from unfold.admin import ModelAdmin

from accounts.models import User, Seller, Admin
from catalog.models import Product, Category, Review
from orders.models import Order, OrderItem, Payment
from communications.models import ChatMessage, Notification


@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ['full_name', 'email', 'username', 'role', 'created_at']
    list_filter = ['role', 'two_factor_enabled']
    search_fields = ['full_name', 'email', 'username']

@admin.register(Seller)
class SellerAdmin(ModelAdmin):
    list_display = ['full_name', 'email', 'store_name', 'role', 'created_at']
    search_fields = ['full_name', 'email', 'store_name']

@admin.register(Admin)
class AdminModelAdmin(ModelAdmin):
    list_display = ['username', 'email', 'role', 'created_at']
    search_fields = ['username', 'email']

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ['name', 'price', 'stock', 'is_active', 'seller', 'created_at']
    list_filter = ['is_active', 'category']
    search_fields = ['name', 'description']

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name']

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ['id', 'user', 'seller', 'total_amount', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['id']

@admin.register(OrderItem)
class OrderItemAdmin(ModelAdmin):
    list_display = ['id', 'order', 'product', 'quantity', 'price']

@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ['id', 'order', 'provider', 'status', 'amount', 'currency', 'created_at']
    list_filter = ['status', 'provider']

@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ['id', 'user', 'product', 'rating', 'created_at']
    list_filter = ['rating']

@admin.register(ChatMessage)
class ChatMessageAdmin(ModelAdmin):
    list_display = ['id', 'sender_id', 'sender_type', 'receiver_id', 'is_read', 'created_at']
    list_filter = ['sender_type', 'is_read']

@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ['id', 'recipient_id', 'recipient_type', 'type', 'title', 'is_read', 'created_at']
    list_filter = ['type', 'recipient_type', 'is_read']
    search_fields = ['title', 'message']
