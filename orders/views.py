import stripe
import requests
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from core.permissions import IsUser, IsSeller, IsUserOrSeller
from core.utils.mail import send_purchase_notification
from catalog.models import Product
from accounts.models import Seller, User
from .models import Order, OrderItem, Payment, PaymentProvider, PaymentStatus, OrderStatus
from .serializers import (
    OrderSerializer, PaymentSerializer, CreateOrderSerializer, CreateCheckoutSerializer
)

stripe.api_key = settings.STRIPE_SECRET_KEY

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer

    def _resolve_buyer_user(self):
        user_type = getattr(self.request, 'auth_user_type', None)
        if user_type == 'user':
            return self.request.auth_entity

        if user_type == 'seller':
            seller = self.request.auth_entity
            buyer = User.objects.filter(email=seller.email).first()
            if buyer:
                return buyer

            # Create a linked buyer profile for seller email if missing.
            return User.objects.create_user(
                email=seller.email,
                full_name=getattr(seller, 'full_name', ''),
                username=f"seller_{str(seller.id)[:8]}"
            )

        return None

    def get_queryset(self):
        user_type = getattr(self.request, 'auth_user_type', None)
        if user_type == 'seller':
            scope = self.request.query_params.get('scope')
            if scope == 'buyer':
                buyer = self._resolve_buyer_user()
                if not buyer:
                    return Order.objects.none()
                return Order.objects.filter(user=buyer)
            return Order.objects.filter(seller=self.request.auth_entity)
        return Order.objects.filter(user=self.request.auth_entity)

    def get_permissions(self):
        if self.action in ['create']:
            return [IsUserOrSeller()]
        if self.action in ['ship', 'confirm']:
            return [IsSeller()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        order = self.get_object()
        if order.status != OrderStatus.PENDING:
            return Response({'detail': 'Only pending orders can be confirmed'}, status=400)

        order.status = OrderStatus.PAID
        order.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(order).data)

    def create(self, request, *args, **kwargs):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items_data = serializer.validated_data['items']
        shipping_address = serializer.validated_data['shippingAddress']

        # Group items by seller to create sub-orders
        seller_items = {}
        for item_data in items_data:
            try:
                product = Product.objects.get(id=item_data['productId'])
                if product.stock < item_data['quantity']:
                    return Response({'detail': f'Insufficient stock for {product.name}'}, status=400)
                
                seller_id = product.seller_id
                if seller_id not in seller_items:
                    seller_items[seller_id] = []
                seller_items[seller_id].append({'product': product, 'quantity': item_data['quantity']})
            except Product.DoesNotExist:
                return Response({'detail': f'Product not found'}, status=400)

        created_orders = []
        for seller_id, items in seller_items.items():
            seller = Seller.objects.get(id=seller_id)
            buyer_user = self._resolve_buyer_user()
            if not buyer_user:
                return Response({'detail': 'Buyer account not available'}, status=400)

            order = Order.objects.create(
                user=buyer_user,
                seller=seller,
                shipping_address=shipping_address,
                total_amount=0
            )
            
            total = 0
            for item in items:
                product = item['product']
                quantity = item['quantity']
                # Decrease stock
                product.stock -= quantity
                product.save()
                
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price
                )
                total += (product.price * quantity)
            
            order.total_amount = total
            order.save()
            created_orders.append(order)

        # Return the first order created (simplification for frontend array handling)
        return Response(OrderSerializer(created_orders[0] if len(created_orders) == 1 else created_orders, many=len(created_orders) > 1).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        order = self.get_object()
        if order.status != OrderStatus.PAID:
            return Response({'detail': 'Order is not paid'}, status=400)
        
        order.status = OrderStatus.SHIPPED
        order.save()
        return Response(self.get_serializer(order).data)


@api_view(['POST'])
@permission_classes([IsUserOrSeller])
def create_checkout(request):
    serializer = CreateCheckoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if getattr(request, 'auth_user_type', None) == 'seller':
        buyer_user = User.objects.filter(email=request.auth_entity.email).first()
    else:
        buyer_user = request.auth_entity

    order = Order.objects.filter(id=serializer.validated_data['orderId'], user=buyer_user).first()
    if not order:
        return Response({'detail': 'Order not found'}, status=404)
        
    provider = serializer.validated_data['provider']
    
    if provider == PaymentProvider.STRIPE:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': f'Order #{order.id}'},
                    'unit_amount': int(order.total_amount * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{settings.FRONTEND_URL}/payment/success?orderId={order.id}",
            cancel_url=f"{settings.FRONTEND_URL}/payment/cancel",
            client_reference_id=str(order.id),
        )
        
        payment = Payment.objects.create(
            order=order,
            provider=PaymentProvider.STRIPE,
            amount=order.total_amount,
            currency='USD',
            checkout_url=session.url,
            provider_payment_id=session.id
        )
        return Response({'checkoutUrl': session.url})
        
    elif provider == PaymentProvider.CHARGILY:
        url = 'https://pay.chargily.net/test/api/v2/checkouts'
        headers = {
            'Authorization': f"Bearer {settings.CHARGILY_SECRET_KEY}",
            'Content-Type': 'application/json'
        }
        payload = {
            'amount': int(order.total_amount),
            'currency': 'dzd',
            'success_url': f"{settings.FRONTEND_URL}/payment/success?orderId={order.id}",
            'failure_url': f"{settings.FRONTEND_URL}/payment/cancel",
            'webhook_endpoint': f"{settings.BACKEND_URL}/api/orders/webhook/chargily",
            'metadata': [{'order_id': str(order.id)}]
        }
        
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code >= 400:
            return Response({'detail': 'Chargily error'}, status=res.status_code)
            
        data = res.json()
        Payment.objects.create(
            order=order,
            provider=PaymentProvider.CHARGILY,
            amount=order.total_amount,
            currency='DZD',
            checkout_url=data.get('checkout_url'),
            provider_payment_id=data.get('id')
        )
        return Response({'checkoutUrl': data.get('checkout_url')})


@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    sig_header = request.headers.get('stripe-signature')
    try:
        event = stripe.Webhook.construct_event(
            request.body, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return Response(status=400)
    except stripe.error.SignatureVerificationError:
        return Response(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session.get('client_reference_id')
        
        payment = Payment.objects.filter(order_id=order_id).first()
        if payment:
            payment.status = PaymentStatus.SUCCESS
            payment.save()
            
            order = payment.order
            order.status = OrderStatus.PAID
            order.save()
            
            # Send email
            send_purchase_notification(order.user.email, str(order.id))

    return Response({'status': 'success'})

@api_view(['POST'])
@permission_classes([AllowAny])
def chargily_webhook(request):
    signature = request.headers.get('signature', '')
    import hmac
    import hashlib
    computed = hmac.new(
        settings.CHARGILY_SECRET_KEY.encode('utf-8'),
        request.body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(computed, signature):
        return Response(status=403)

    data = request.data
    if data.get('type') == 'checkout.paid':
        checkout = data.get('data', {})
        metadata = checkout.get('metadata', [])
        order_id = next((item['order_id'] for item in metadata if 'order_id' in item), None)
        
        if order_id:
            payment = Payment.objects.filter(order_id=order_id).first()
            if payment:
                payment.status = PaymentStatus.SUCCESS
                payment.save()
                
                order = payment.order
                order.status = OrderStatus.PAID
                order.save()
                
                send_purchase_notification(order.user.email, str(order.id))

    return Response({'status': 'success'})
