from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
from django.core.mail import send_mail
from order.models import Job
from order.templatetags.extra_tag import prejob


def user_login(request):
    context = {}

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if (username in ["PRINT-1","LAMI-1","SLIT-1","POUCH-1","POUCH-2"]):
                messages.success(request, f'Welcome {username} ', )
                return HttpResponseRedirect(reverse('manpower:newshift'))
            if username in ["khadimhusen"]:
                messages.success(request, f'{prejob()} Nos job Pending ')
            else:
                messages.success(request, f'Welcome {username} To H F FLEX PVT. LTD. ', )
            if request.GET.get('next', None):
                return HttpResponseRedirect(request.GET['next'])
            messages.success(request, f'Welcome {username} To H F FLEX PVT. LTD. ', )
            return HttpResponseRedirect(reverse('order:joblist'))

        else:
            context["error"] = "Provide valid credentials !!"
            return render(request, "login.html", context)
    else:
        return render(request, "login.html", context)


# @login_required(login_url="/login/")
# def success(request):
#     context = {}
#     context['user'] = request.user
#     return render(request, "auth/success.html", context)
#

def user_logout(request):
    logout(request)
    return render(request, 'logout.html')


def test(request,start,end):
    jobs = Job.objects.filter(id__range=(start,end))
    for job in jobs:
        job.save()
    return render(request, 'jobmaterial/test.html',{})


def noaccess(request):
    return render(request, 'noaccess.html')
