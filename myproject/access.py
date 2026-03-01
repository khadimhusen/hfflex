from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from employee.models import ViewName, Access
from manpower.models import Shift


def accessview(view_func):
    def wrap(request, *args, **kwargs):
        """ uncomment below line to enable accessview decorator """

        # userviewlist = Access.objects.filter(username=request.user)
        # viewlist = [a.viewname.viewname for a in userviewlist]
        # param = str(view_func.__name__)
        # if param in viewlist:

        if True:
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseRedirect(reverse('noaccess'))

    return wrap


def forceview(view_func):
    def wrap(request, *args, **kwargs):
        """ This decorator force to check manpower report and approve """

        if not request.user.username == "cmshaikh":
            return view_func(request, *args, **kwargs)
        elif Shift.objects.filter(is_approved=False).count() >-1:

            return view_func(request, *args, **kwargs)
        else:
            messages.success(request, 'More than 12  shift report pending for approval, Plaese Check report and approve.')
            return redirect("manpower:shiftlist")

    return wrap
