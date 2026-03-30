from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

class MultiEntityJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user_type = validated_token.get('userType')
        user_id = validated_token.get('sub')

        if not user_type or not user_id:
            raise AuthenticationFailed('Invalid token payload', code='invalid_payload')

        # Late imports to avoid circular dependencies
        from accounts.models import User, Seller, Admin

        try:
            if user_type == 'user':
                entity = User.objects.get(id=user_id)
            elif user_type == 'seller':
                entity = Seller.objects.get(id=user_id)
            elif user_type == 'admin':
                entity = Admin.objects.get(id=user_id)
            else:
                raise AuthenticationFailed('Invalid user type', code='invalid_user_type')
        except (User.DoesNotExist, Seller.DoesNotExist, Admin.DoesNotExist):
            raise AuthenticationFailed('User not found', code='user_not_found')

        # We return the entity as the Django "user" for request.user
        # We also attach the actual type for permission classes to use
        class RequestEntityWrapper:
            """Wrapper that looks enough like a Django User for DRF to not break."""
            is_authenticated = True
            is_active = True
            def __init__(self, e):
                self.entity = e
                self.id = e.id

        return RequestEntityWrapper(entity)

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        
        user_wrapper, token = result
        request.auth_entity = user_wrapper.entity
        request.auth_user_type = token.get('userType')
        return user_wrapper, token
