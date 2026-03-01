from django.shortcuts import render, get_object_or_404
from .models import *
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from .forms import MaterialForm, MatTypeForm, GradeForm
from myproject.access import accessview
from django.contrib.auth.decorators import login_required


@login_required(login_url='/login/')
@accessview
def materialadd(request):
    context = {}
    if request.method == 'POST':
        material_form = MaterialForm(request.POST)
        context['material_form'] = material_form
        if material_form.is_valid():
            material_form.save()
        else:
            messages.success(request, material_form.errors)
            return render(request, 'material/material.html', context)

        messages.success(request, 'Material added Successfully ')
        return HttpResponseRedirect(reverse('material:materiallist'))
    else:
        material_form = MaterialForm()
        context['material_form'] = material_form
        return render(request, 'material/material.html', context)


@login_required(login_url='/login/')
@accessview
def materialedit(request, id):
    mate = get_object_or_404(Material, id=id)
    if request.method == 'POST':
        material_form = MaterialForm(request.POST, instance=mate)
        if material_form.is_valid():
            material_form.save()
        else:
            messages.success(request, material_form.errors)
            return render(request, 'material/materialedit.html', {'material_form': material_form})
        messages.success(request, "material updated successfully ")
        return HttpResponseRedirect(reverse('material:materiallist'))
    else:
        material_form = MaterialForm(instance=mate)
        return render(request, 'material/materialedit.html', {'material_form': material_form})


@login_required(login_url='/login/')
@accessview
def materiallist(request):
    materiallist = Material.objects.all()
    return render(request, 'material/materiallist.html', {'materiallist': materiallist})


@login_required(login_url='/login/')
@accessview
def mattypeadd(request):
    context = {}
    if request.method == 'POST':
        mattype_form = MatTypeForm(request.POST)
        context['mattype_form'] = mattype_form
        if mattype_form.is_valid():
            mattype_form.save()
        else:
            messages.success(request, mattype_form.errors)
            return render(request, 'mattype/mattypeadd.html', context)

        messages.success(request, 'Your Material type was updated.')
        return HttpResponseRedirect(reverse('material:mattypelist'))
    else:
        mattype_form = MatTypeForm()
        context['mattype_form'] = mattype_form
        return render(request, 'mattype/mattypeadd.html', context)


@login_required(login_url='/login/')
@accessview
def mattypeedit(request, id):
    context = {}
    matt = get_object_or_404(MatType, id=id)
    if request.method == 'POST':
        mattype_form = MatTypeForm(request.POST, instance=matt)
        context['mattype_form'] = mattype_form
        if mattype_form.is_valid():
            mattype_form.save()
        else:
            messages.success(request, mattype_form.errors)
            return render(request, 'mattype/mattypeedit.html', context)

        messages.success(request, 'Your Material type was updated.')
        return HttpResponseRedirect(reverse('material:mattypelist'))
    else:
        mattype_form = MatTypeForm(instance=matt)
        context['mattype_form'] = mattype_form
        return render(request, 'mattype/mattypeedit.html', context)


@login_required(login_url='/login/')
@accessview
def mattypelist(request):
    mattypelist = MatType.objects.all()
    return render(request, 'mattype/mattypelist.html', {'mattypelist': mattypelist})


@login_required(login_url='/login/')
@accessview
def gradeadd(request):
    context = {}
    if request.method == 'POST':
        gradeform = GradeForm(request.POST)
        context['gradeform'] = gradeform
        if gradeform.is_valid():
            gradeform.save()
        else:
            messages.success(request, gradeform.errors)
            return render(request, 'grade/gradeadd.html', context)
        return HttpResponseRedirect(reverse('material:gradelist'))
    else:
        gradeform = GradeForm()
        context['gradeform'] = gradeform
        return render(request, 'grade/gradeadd.html', context)


@login_required(login_url='/login/')
@accessview
def gradeedit(request, id):
    context = {}
    grad = get_object_or_404(Grade, id=id)
    if request.method == 'POST':
        gradeform = GradeForm(request.POST, instance=grad)
        context['gradeform'] = gradeform
        if gradeform.is_valid():
            gradeform.save()
        else:
            messages.success(request, gradeform.errors)
            return render(request, 'grade/gradeedit.html', context)
        return HttpResponseRedirect(reverse('material:gradelist'))
    else:
        gradeform = GradeForm(instance=grad)
        context['gradeform'] = gradeform
        return render(request, 'grade/gradeedit.html', context)


@login_required(login_url='/login/')
@accessview
def gradelist(request):
    gradelist = Grade.objects.all()
    return render(request, 'grade/gradelist.html', {'gradelist': gradelist})
