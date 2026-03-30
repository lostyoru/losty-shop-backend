from rest_framework import serializers
from accounts.serializers import UserSerializer, SellerPublicSerializer
from catalog.serializers import ProductSerializer
from .models import Order, OrderItem, Payment

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    
    class Meta:
        model = OrderItem
        fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)
    seller = SellerPublicSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)

    class Meta:
        model = Order
        fields = '__all__'


# --- Create Logic Serializers ---

class CreateOrderItemSerializer(serializers.Serializer):
    productId = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

class CreateOrderSerializer(serializers.Serializer):
    items = CreateOrderItemSerializer(many=True)
    shippingAddress = serializers.CharField()


class CreateCheckoutSerializer(serializers.Serializer):
    orderId = serializers.UUIDField()
    provider = serializers.ChoiceField(choices=['STRIPE', 'CHARGILY'])
