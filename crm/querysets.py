from django.contrib.auth.models import User

def crm_users():
    return User.objects.filter(department__department_name__iexact='crm_user', is_active=True)