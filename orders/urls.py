from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('orders', views.OrderViewSet, basename='order')

urlpatterns = [
    path('checkout', views.create_checkout),
    path('webhook/stripe', views.stripe_webhook),
    path('webhook/chargily', views.chargily_webhook),
    path('', include(router.urls)),
]
