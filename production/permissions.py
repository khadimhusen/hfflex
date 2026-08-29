from rest_framework.permissions import BasePermission

from .querysets import (
    report_department_users, dispatch_department_users, stock_department_users,
)


class IsProductionReportUser(BasePermission):
    """Mirrors the old nav's 'sidereport' gate (Production Report section) —
    previously nav-visibility only, now actually enforced."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff or user.is_superuser:
            return True
        return report_department_users().filter(id=user.id).exists()


class IsDispatchUser(BasePermission):
    """Mirrors the old nav's 'sidedispatch' gate."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff or user.is_superuser:
            return True
        return dispatch_department_users().filter(id=user.id).exists()


class IsStockUser(BasePermission):
    """Mirrors the old nav's 'sidestock' gate (Inward + Stock section)."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff or user.is_superuser:
            return True
        return stock_department_users().filter(id=user.id).exists()


class IsProductionUser(BasePermission):
    """Any of the three production sub-departments — used only for shared,
    read-only lookups (material/unit/worker/etc.) that more than one
    sub-module needs; the actual CRUD viewsets use the specific
    department permission above."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff or user.is_superuser:
            return True
        return (
            report_department_users().filter(id=user.id).exists()
            or dispatch_department_users().filter(id=user.id).exists()
            or stock_department_users().filter(id=user.id).exists()
        )
