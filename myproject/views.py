from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
from employee.models import Department


def user_login(request):
    context = {}

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            print("user: ", user)
            if (user in Department.objects.filter(department_name="machine")):
                messages.success(request, f'Welcome {username} ')
                print("from machine")
                return HttpResponseRedirect(reverse('manpower:newshift'))

            if (user in Department.objects.filter(department_name="Marketing_only")):
                messages.success(request, f'Welcome {username} ')
                print("from marketing")
                return HttpResponseRedirect(reverse('quotation:quotationlist'))

            if request.GET.get('next', None):
                print("from page")
                return HttpResponseRedirect(request.GET['next'])

            messages.success(request, f'Welcome {username} To H F FLEX PVT. LTD. ', )
            print("from general")
            return HttpResponseRedirect(reverse('order:joblist'))

        else:
            context["error"] = "Provide valid credentials !!"
            return render(request, "login.html", context)
    else:
        return render(request, "login.html", context)



def user_logout(request):
    logout(request)
    return render(request, 'logout.html')


def test(request):
    import json
    from django.contrib.contenttypes.models import ContentType

    # Open and load the JSON file
    with open('content.json', 'r') as f:
        data = json.load(f)

    # Create a list of MyModel instances

    instances = []
    for item in data:
        print(item.get("id"))
        instance = ContentType(id=item.get('id', 0), app_label=item.get('fields').get("app_label"),
                               model=item.get('fields', 0).get("model"))
        instances.append(instance)
    print(instances)
    # Bulk update the instances in the database
    ContentType.objects.bulk_update(instances, ['app_label', 'model'])
    return render(request, 'jobmaterial/test.html', {})


def noaccess(request):
    return render(request, 'noaccess.html')


def test1(request):
    return render(request, 'test1.html', {'my_range': range(16)})


def test2(request):
    return render(request, 'test2.html', {'my_range': range(16)})
