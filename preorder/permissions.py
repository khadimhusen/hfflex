from rest_framework.permissions import BasePermission

from .querysets import preorder_department_users


class IsPreorderUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser or preorder_department_users().filter(id=user.id).exists()
