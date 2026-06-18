# myproject/admin_mixins.py

class AutocompleteMixin:
    def has_view_permission(self, request, obj=None):
        return True