from django.shortcuts import render, get_object_or_404, HttpResponseRedirect, reverse
from .models import Profile, Access, ViewName, Worker
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from .forms import AccessFrom
from myproject.access import accessview
from django.contrib.auth.decorators import login_required


@login_required(login_url='/login/')
@accessview
def employeelist(request):
    emps = Profile.objects.all()

    return render(request, 'employee/list.html', {'emps': emps})


@login_required(login_url='/login/')
@accessview
def accesslistedit(request, id=None):
    context = {}
    useraccess = get_object_or_404(User, id=id)
    accessformset = inlineformset_factory(User, Access, fk_name='username' , form=AccessFrom, extra=6, can_delete=False)
    if request.method == 'POST':
        formset1 = accessformset(request.POST, prefix='access', instance=useraccess, )
        context['access'] = formset1
        if formset1.is_valid():
            formset1.save()
            return HttpResponseRedirect(reverse('employee:employeelist'))
        else:
            print(formset1.errors)
            return render(request, 'employee/access.html', context)

    else:
        formset1 = accessformset(prefix='access', instance=useraccess)
        context['access'] = formset1
        context['user']=useraccess
        return render(request, 'employee/access.html', context)



def viewaccess(request, id):
    pass


def workerdetail(request, id):
    worker= get_object_or_404(Worker, id=id)
    return render(request, 'worker/workerdetail.html', {'worker': worker})