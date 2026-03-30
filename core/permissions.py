from rest_framework import permissions

class IsUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request, 'auth_user_type', None) == 'user'
        )

class IsSeller(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request, 'auth_user_type', None) == 'seller'
        )

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request, 'auth_user_type', None) == 'admin'
        )

class IsUserOrSeller(permissions.BasePermission):
    def has_permission(self, request, view):
        auth_type = getattr(request, 'auth_user_type', None)
        return bool(
            request.user and
            request.user.is_authenticated and
            auth_type in ['user', 'seller']
        )
