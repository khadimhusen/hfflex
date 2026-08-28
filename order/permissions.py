from rest_framework.permissions import BasePermission

from .querysets import order_department_users


class IsOrderUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser or order_department_users().filter(id=user.id).exists()
