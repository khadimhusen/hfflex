import os

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse

CRM_STATIC_DIR = os.path.join(settings.BASE_DIR, 'crm_static')


def serve_crm_spa(request, path=''):
    """Serves the built CRM SPA (crm_static/, produced by `npm run build` in
    hfflex_frontend) directly from Django — for trying the production build
    locally. In real deployment this is normally the web server's job
    (nginx etc. pointed at crm_static), not Django's — nothing else in this
    project served /crm/ before this.
    """
    if path:
        candidate = os.path.normpath(os.path.join(CRM_STATIC_DIR, path))
        # Guard against path traversal (e.g. /crm/../../settings.py) — only
        # ever serve a file that resolves to somewhere inside crm_static.
        if candidate.startswith(CRM_STATIC_DIR) and os.path.isfile(candidate):
            return FileResponse(open(candidate, 'rb'))

    # Vue Router here uses hash routing (#/deals/...), so the server only
    # ever needs to hand back index.html for any non-asset /crm/* path.
    index_path = os.path.join(CRM_STATIC_DIR, 'index.html')
    if not os.path.isfile(index_path):
        raise Http404('CRM build not found — run "npm run build" in hfflex_frontend first.')
    return FileResponse(open(index_path, 'rb'))


def user_login(request):
    context = {}

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            request.session['show_pending_tasks'] = True

            if user.department.filter(department_name='machine').exists():
                messages.success(request, f'Welcome {username} ')
                return HttpResponseRedirect(reverse('planning:machine_schedule',kwargs={'machine_id':1}))

            if user.department.filter(department_name="Marketing_only").exists():
                messages.success(request, f'Welcome {username} ')
                return HttpResponseRedirect(reverse('quotation:quotationlist'))

            if request.GET.get('next', None):
                return HttpResponseRedirect(request.GET['next'])

            messages.success(request, f'Welcome {username} To H F FLEX PVT. LTD. ', )
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
