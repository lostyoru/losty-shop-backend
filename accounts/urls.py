from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('users', views.UserViewSet, basename='user')
router.register('sellers', views.SellerViewSet, basename='seller')

urlpatterns = [
    # Auth
    path('auth/register/user/', views.register_user),
    path('auth/register/seller/', views.register_seller),
    path('auth/register/admin/', views.register_admin),
    path('auth/login/', views.login),
    path('auth/logout/', views.logout),
    path('auth/verify-2fa/', views.verify_2fa_login),
    path('auth/2fa/generate/', views.generate_2fa),
    path('auth/2fa/enable/', views.enable_2fa),
    path('auth/2fa/disable/', views.disable_2fa),
    path('auth/social/session/', views.social_session_login),
    path('auth/google/', RedirectView.as_view(url='/api/accounts/auth/google/login/', permanent=False)),
    
    # Routers for Profile Management
    path('', include(router.urls)),
]
