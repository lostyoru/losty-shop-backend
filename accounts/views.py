import pyotp
import qrcode
import base64
from io import BytesIO
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import MultiPartParser
from django.contrib.auth.hashers import check_password, make_password
from cryptography.fernet import Fernet
from django.conf import settings

from core.permissions import IsUser, IsSeller, IsAdmin
from core.utils.cloudinary import upload_profile_picture
from .models import User, Seller, Admin
from .serializers import (
    UserSerializer, CreateUserSerializer, 
    SellerSerializer, CreateSellerSerializer, SellerPublicSerializer,
    AdminSerializer, CreateAdminSerializer, ChangePasswordSerializer
)

fernet = Fernet(base64.urlsafe_b64encode(settings.ENCRYPTION_KEY.encode('utf-8')))

def encrypt_secret(secret: str) -> str:
    return fernet.encrypt(secret.encode()).decode()

def decrypt_secret(encrypted_secret: str) -> str:
    return fernet.decrypt(encrypted_secret.encode()).decode()

def generate_tokens(entity, user_type: str):
    refresh = RefreshToken()
    refresh['userType'] = user_type
    refresh['sub'] = str(entity.id)
    
    access = refresh.access_token
    access['userType'] = user_type
    
    entity.hashed_refresh_token = make_password(str(refresh))
    entity.save(update_fields=['hashed_refresh_token'])
    
    return {
        'accessToken': str(access),
        'refreshToken': str(refresh),
        'user': {
            'id': str(entity.id),
            'email': entity.email,
            'role': entity.role,
            'userType': user_type,
            'twoFactorEnabled': getattr(entity, 'two_factor_enabled', False),
        }
    }


# --- AUTH ENDPOINTS ---

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    serializer = CreateUserSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(generate_tokens(user, 'user'), status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
def register_seller(request):
    serializer = CreateSellerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.validated_data['password'] = make_password(serializer.validated_data['password'])
    seller = Seller.objects.create(**serializer.validated_data)
    return Response(generate_tokens(seller, 'seller'), status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
def register_admin(request):
    serializer = CreateAdminSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.validated_data['password'] = make_password(serializer.validated_data['password'])
    admin = Admin.objects.create(**serializer.validated_data)
    return Response(generate_tokens(admin, 'admin'), status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    
    # Check Admin
    admin = Admin.objects.filter(email=email).first()
    if admin and check_password(password, admin.password):
        return Response(generate_tokens(admin, 'admin'))

    # Check Seller
    seller = Seller.objects.filter(email=email).first()
    if seller and check_password(password, seller.password):
        if seller.two_factor_enabled:
            return Response({
                'requires2FA': True,
                'userId': str(seller.id),
                'userType': 'seller',
                'message': '2FA verification required'
            })
        return Response(generate_tokens(seller, 'seller'))

    # Check User
    user = User.objects.filter(email=email).first()
    if user and user.check_password(password):
        if user.two_factor_enabled:
            return Response({
                'requires2FA': True,
                'userId': str(user.id),
                'userType': 'user',
                'message': '2FA verification required'
            })
        return Response(generate_tokens(user, 'user'))

    return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_2fa_login(request):
    user_id = request.data.get('userId')
    code = request.data.get('code')

    user_type = request.data.get('userType')

    entity = None
    resolved_type = None
    if user_type == 'seller':
        entity = Seller.objects.filter(id=user_id).first()
        resolved_type = 'seller'
    elif user_type == 'user':
        entity = User.objects.filter(id=user_id).first()
        resolved_type = 'user'
    else:
        entity = User.objects.filter(id=user_id).first()
        if entity:
            resolved_type = 'user'
        else:
            entity = Seller.objects.filter(id=user_id).first()
            resolved_type = 'seller' if entity else None

    if not entity or not getattr(entity, 'two_factor_secret', None):
        return Response({'detail': 'Account or 2FA not found'}, status=status.HTTP_400_BAD_REQUEST)

    totp = pyotp.TOTP(decrypt_secret(entity.two_factor_secret))
    if totp.verify(code):
        return Response(generate_tokens(entity, resolved_type or 'user'))
        
    return Response({'detail': 'Invalid 2FA code'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    request.auth_entity.hashed_refresh_token = None
    request.auth_entity.save(update_fields=['hashed_refresh_token'])
    return Response({'message': 'Logged out successfully'})


@api_view(['GET'])
@permission_classes([AllowAny])
def social_session_login(request):
    """Exchange an authenticated Django session (allauth) for API JWT tokens."""
    django_user = getattr(request._request, 'user', None)
    if not django_user or not django_user.is_authenticated:
        return Response({'detail': 'No active social session'}, status=status.HTTP_401_UNAUTHORIZED)

    user = User.objects.filter(id=django_user.id).first()
    if not user:
        return Response({'detail': 'Unsupported account type for API login'}, status=status.HTTP_400_BAD_REQUEST)

    return Response(generate_tokens(user, 'user'))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_2fa(request):
    user_type = getattr(request, 'auth_user_type', None)
    if user_type not in ('user', 'seller'):
        return Response({'detail': '2FA is only available for user/seller accounts'}, status=status.HTTP_400_BAD_REQUEST)

    user = request.auth_entity
    secret = pyotp.random_base32()
    user.two_factor_secret = encrypt_secret(secret)
    user.two_factor_enabled = False
    user.save(update_fields=['two_factor_secret', 'two_factor_enabled'])

    issuer = 'LostyShop'
    otp_uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=issuer)

    img = qrcode.make(otp_uri)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return Response({
        'qrCode': f'data:image/png;base64,{qr_base64}',
        'secret': secret,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enable_2fa(request):
    user_type = getattr(request, 'auth_user_type', None)
    if user_type not in ('user', 'seller'):
        return Response({'detail': '2FA is only available for user/seller accounts'}, status=status.HTTP_400_BAD_REQUEST)

    code = request.data.get('code')
    if not code:
        return Response({'detail': 'Code is required'}, status=status.HTTP_400_BAD_REQUEST)

    user = request.auth_entity
    if not user.two_factor_secret:
        return Response({'detail': '2FA is not initialized. Generate QR first.'}, status=status.HTTP_400_BAD_REQUEST)

    totp = pyotp.TOTP(decrypt_secret(user.two_factor_secret))
    if not totp.verify(code):
        return Response({'detail': 'Invalid 2FA code'}, status=status.HTTP_400_BAD_REQUEST)

    user.two_factor_enabled = True
    user.save(update_fields=['two_factor_enabled'])
    return Response({'message': '2FA enabled successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disable_2fa(request):
    user_type = getattr(request, 'auth_user_type', None)
    if user_type not in ('user', 'seller'):
        return Response({'detail': '2FA is only available for user/seller accounts'}, status=status.HTTP_400_BAD_REQUEST)

    password = request.data.get('password')
    if not password:
        return Response({'detail': 'Password is required'}, status=status.HTTP_400_BAD_REQUEST)

    user = request.auth_entity
    is_password_valid = user.check_password(password) if hasattr(user, 'check_password') else check_password(password, user.password)
    if not is_password_valid:
        return Response({'detail': 'Wrong password'}, status=status.HTTP_400_BAD_REQUEST)

    user.two_factor_enabled = False
    user.two_factor_secret = None
    user.save(update_fields=['two_factor_enabled', 'two_factor_secret'])
    return Response({'message': '2FA disabled successfully'})


# --- DASHBOARD & PROFILE VIEWSETS ---

class UserViewSet(viewsets.ViewSet):
    permission_classes = [IsUser]

    @action(detail=False, methods=['get'])
    def profile(self, request):
        return Response(UserSerializer(request.auth_entity).data)

    @action(detail=False, methods=['patch'])
    def profile_update(self, request):
        serializer = UserSerializer(request.auth_entity, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.auth_entity
        if not user.check_password(serializer.validated_data['current_password']):
            return Response({'detail': 'Wrong current password'}, status=400)
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])
        return Response({'message': 'Password changed'})

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser])
    def avatar(self, request):
        file = request.FILES.get('file')
        if not file: return Response({'detail': 'No file'}, status=400)
        result = upload_profile_picture(file)
        user = request.auth_entity
        user.profile_picture = result['secure_url']
        user.save(update_fields=['profile_picture'])
        return Response(UserSerializer(user).data)


class SellerViewSet(viewsets.ViewSet):
    permission_classes = [IsSeller]

    @action(detail=False, methods=['get'])
    def profile(self, request):
        return Response(SellerSerializer(request.auth_entity).data)

    @action(detail=False, methods=['patch'])
    def profile_update(self, request):
        serializer = SellerSerializer(request.auth_entity, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser])
    def avatar(self, request):
        file = request.FILES.get('file')
        if not file: return Response({'detail': 'No file'}, status=400)
        result = upload_profile_picture(file)
        seller = request.auth_entity
        seller.profile_picture = result['secure_url']
        seller.save(update_fields=['profile_picture'])
        return Response(SellerSerializer(seller).data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny], url_path='public')
    def public(self, request):
        sellers = Seller.objects.all().order_by('-created_at')
        return Response(SellerPublicSerializer(sellers, many=True).data)

    # Public method
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def store(self, request, pk=None):
        seller = Seller.objects.filter(id=pk).first()
        if not seller: return Response(status=404)

        # Keep public seller list lightweight; include products only on storefront detail.
        from catalog.serializers import ProductSerializer

        data = SellerPublicSerializer(seller).data
        data['products'] = ProductSerializer(
            seller.products.all().order_by('-created_at'), many=True
        ).data
        return Response(data)
