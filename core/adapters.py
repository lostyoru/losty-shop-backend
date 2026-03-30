from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.hashers import make_password
from allauth.account.adapter import DefaultAccountAdapter
from rest_framework_simplejwt.tokens import RefreshToken


class FrontendJWTAccountAdapter(DefaultAccountAdapter):
    """Redirect allauth logins back to frontend with an API access token."""

    def get_login_redirect_url(self, request):
        user = request.user
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')

        if not getattr(user, 'is_authenticated', False):
            return f"{frontend_url}/login"

        user_type = getattr(user, 'role', 'user') or 'user'
        if user_type not in {'user', 'seller', 'admin'}:
            user_type = 'user'

        refresh = RefreshToken()
        refresh['userType'] = user_type
        refresh['sub'] = str(user.id)

        access = refresh.access_token
        access['userType'] = user_type

        if hasattr(user, 'hashed_refresh_token'):
            user.hashed_refresh_token = make_password(str(refresh))
            user.save(update_fields=['hashed_refresh_token'])

        query = urlencode({'accessToken': str(access)})
        return f"{frontend_url}/login?{query}"
