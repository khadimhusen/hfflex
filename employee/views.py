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

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import CompanyAsset, AssetAssignment
from .forms import CompanyAssetForm, AssetDisposeForm, AssetIssueForm, AssetReturnForm


from django.core.paginator import Paginator
from django.db.models import Q

@login_required(login_url='/login/')
def asset_list(request):
    assets = CompanyAsset.objects.all().order_by('name')

    # Filters
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')  # 'active' / 'disposed' / ''

    if search:
        assets = assets.filter(Q(name__icontains=search) | Q(description__icontains=search))

    if status == 'active':
        assets = assets.filter(is_active=True)
    elif status == 'disposed':
        assets = assets.filter(is_active=False)

    # Pagination
    paginator = Paginator(assets, 20)  # 20 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'employee/asset_list.html', {
        'page_obj': page_obj,
        'search': search,
        'status': status,
    })


from django.core.paginator import Paginator
from django.db.models import Q

@login_required(login_url='/login/')
def assignment_list(request):
    assignments = AssetAssignment.objects.select_related('asset', 'employee').all()

    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')  # 'issued' / 'returned' / ''
    employee_name = request.GET.get('employee_name', '').strip()

    if search:
        assignments = assignments.filter(asset__name__icontains=search)

    if status == 'issued':
        assignments = assignments.filter(return_date__isnull=True)
    elif status == 'returned':
        assignments = assignments.filter(return_date__isnull=False)

    if employee_name:
        assignments = assignments.filter(
            Q(employee__first_name__icontains=employee_name) |
            Q(employee__last_name__icontains=employee_name) |
            Q(employee__username__icontains=employee_name)
        )

    paginator = Paginator(assignments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'employee/assignment_list.html', {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'employee_name': employee_name,
    })

@login_required(login_url='/login/')
@accessview
def asset_detail(request, pk):
    asset = get_object_or_404(CompanyAsset, pk=pk)
    assignments = asset.assignments.select_related('employee').all()
    return render(request, 'employee/asset_detail.html', {
        'asset': asset,
        'assignments': assignments,
    })


@login_required(login_url='/login/')
@accessview
def asset_create(request):
    if request.method == 'POST':
        form = CompanyAssetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Asset created successfully.')
            return redirect('employee:asset_list')
    else:
        form = CompanyAssetForm()
    return render(request, 'employee/asset_form.html', {'form': form})


@login_required(login_url='/login/')
@accessview
def asset_update(request, pk):
    asset = get_object_or_404(CompanyAsset, pk=pk)
    if request.method == 'POST':
        form = CompanyAssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, 'Asset updated successfully.')
            return redirect('employee:asset_detail', pk=asset.pk)
    else:
        form = CompanyAssetForm(instance=asset)
    return render(request, 'employee/asset_form.html', {'form': form, 'asset': asset})


@login_required(login_url='/login/')
@accessview
def asset_dispose(request, pk):
    asset = get_object_or_404(CompanyAsset, pk=pk)
    if request.method == 'POST':
        form = AssetDisposeForm(request.POST, instance=asset)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f'{asset.name} marked as disposed.')
                return redirect('employee:asset_detail', pk=asset.pk)
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
    else:
        form = AssetDisposeForm(instance=asset)
    return render(request, 'employee/asset_dispose.html', {'form': form, 'asset': asset})




@login_required(login_url='/login/')
@accessview
def asset_issue(request):
    if request.method == 'POST':
        form = AssetIssueForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            try:
                assignment.full_clean()
                assignment.save()
                messages.success(request, f'{assignment.asset} issued to {assignment.employee}.')
                return redirect('employee:assignment_list')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
    else:
        form = AssetIssueForm(initial={'issuing_date': timezone.now().date()})
    return render(request, 'employee/asset_issue.html', {'form': form})


@login_required(login_url='/login/')
@accessview
def asset_return(request, pk):
    assignment = get_object_or_404(AssetAssignment, pk=pk, return_date__isnull=True)
    if request.method == 'POST':
        form = AssetReturnForm(request.POST, instance=assignment)
        if form.is_valid():
            assignment_obj = form.save(commit=False)
            try:
                assignment_obj.full_clean()
                assignment_obj.save()
                messages.success(request, f'{assignment.asset} returned.')
                return redirect('employee:assignment_list')
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages) if hasattr(e, 'messages') else str(e))
    else:
        form = AssetReturnForm(instance=assignment, initial={'return_date': timezone.now().date()})
    return render(request, 'employee/asset_return.html', {'form': form, 'assignment': assignment})



@login_required(login_url='/login/')
def employee_asset_detail(request, employee_id):
    employee = get_object_or_404(User, pk=employee_id)
    assignments = AssetAssignment.objects.filter(employee=employee).select_related('asset').order_by('-issuing_date')
    current_assignments = assignments.filter(return_date__isnull=True)
    past_assignments = assignments.filter(return_date__isnull=False)

    return render(request, 'employee/employee_asset_detail.html', {
        'employee': employee,
        'current_assignments': current_assignments,
        'past_assignments': past_assignments,
    })