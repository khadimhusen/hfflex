from employee.models import Access, ViewName
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User


def accesslists(request):
    if request.user:
        print(request.user)
        if str(request.user) == 'AnonymousUser':
            return {'accessname': ""}
        else:
            accessname = Access.objects.filter(username=request.user)
            return {'accessname': accessname}
    else:
        return {'accessname': ""}

