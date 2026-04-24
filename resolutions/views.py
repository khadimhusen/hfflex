from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Resolution, ResolutionEditor
from .forms import ResolutionForm, DocumentFormSet


def can_edit(user):
    """Check if user is admin or an authorized editor."""
    if user.is_staff or user.is_superuser:
        return True
    return ResolutionEditor.objects.filter(user=user, can_edit=True).exists()


# ── List ──────────────────────────────────────────────────────────────────────
def resolution_list(request):
    qs = Resolution.objects.filter(status='published')

    # Search
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(resolution_number__icontains=q) |
            Q(meeting_location__icontains=q)
        )

    # Filter by year
    year = request.GET.get('year', '')
    if year:
        qs = qs.filter(meeting_date__year=year)

    # Filter by meeting type
    meeting_type = request.GET.get('meeting_type', '')
    if meeting_type:
        qs = qs.filter(meeting_type=meeting_type)

    paginator = Paginator(qs, 10)
    page = paginator.get_page(request.GET.get('page'))

    years = Resolution.objects.filter(status='published').dates('meeting_date', 'year')

    return render(request, 'resolutions/list.html', {
        'page_obj': page,
        'years': years,
        'q': q,
        'selected_year': year,
        'selected_type': meeting_type,
        'meeting_types': Resolution._meta.get_field('meeting_type').choices,
        'user_can_edit': can_edit(request.user) if request.user.is_authenticated else False,
    })


# ── Detail ────────────────────────────────────────────────────────────────────
def resolution_detail(request, pk):
    resolution = get_object_or_404(Resolution, pk=pk)

    # Non-editors can only see published resolutions
    if resolution.status != 'published' and not (
        request.user.is_authenticated and can_edit(request.user)
    ):
        from django.http import Http404
        raise Http404

    return render(request, 'resolutions/detail.html', {
        'resolution': resolution,
        'user_can_edit': request.user.is_authenticated and can_edit(request.user),
    })


# ── Create ────────────────────────────────────────────────────────────────────
@login_required
def resolution_create(request):
    if not can_edit(request.user):
        messages.error(request, "You don't have permission to create resolutions.")
        return redirect('resolution_list')

    if request.method == 'POST':
        form = ResolutionForm(request.POST)
        formset = DocumentFormSet(request.POST, request.FILES)
        if form.is_valid() and formset.is_valid():
            resolution = form.save(commit=False)
            resolution.created_by = request.user
            if resolution.status == 'published':
                resolution.published_at = timezone.now()
            resolution.save()
            formset.instance = resolution
            for doc_form in formset:
                if doc_form.cleaned_data.get('file'):
                    doc = doc_form.save(commit=False)
                    doc.uploaded_by = request.user
                    doc.save()
            messages.success(request, f'Resolution {resolution.resolution_number} created successfully.')
            return redirect('resolution_detail', pk=resolution.pk)
    else:
        form = ResolutionForm()
        formset = DocumentFormSet()

    return render(request, 'resolutions/form.html', {
        'form': form,
        'formset': formset,
        'action': 'Create',
    })


# ── Edit ──────────────────────────────────────────────────────────────────────
@login_required
def resolution_edit(request, pk):
    resolution = get_object_or_404(Resolution, pk=pk)
    if not can_edit(request.user):
        messages.error(request, "You don't have permission to edit resolutions.")
        return redirect('resolution_detail', pk=pk)

    if request.method == 'POST':
        form = ResolutionForm(request.POST, instance=resolution)
        formset = DocumentFormSet(request.POST, request.FILES, instance=resolution)
        if form.is_valid() and formset.is_valid():
            resolution = form.save(commit=False)
            if resolution.status == 'published' and not resolution.published_at:
                resolution.published_at = timezone.now()
            resolution.save()
            for doc_form in formset:
                if doc_form.cleaned_data.get('file'):
                    doc = doc_form.save(commit=False)
                    doc.uploaded_by = request.user
                    doc.save()
                elif doc_form.cleaned_data.get('DELETE') and doc_form.instance.pk:
                    doc_form.instance.delete()
            messages.success(request, 'Resolution updated successfully.')
            return redirect('resolution_detail', pk=resolution.pk)
    else:
        form = ResolutionForm(instance=resolution)
        formset = DocumentFormSet(instance=resolution)

    return render(request, 'resolutions/form.html', {
        'form': form,
        'formset': formset,
        'resolution': resolution,
        'action': 'Edit',
    })


# ── Delete ────────────────────────────────────────────────────────────────────
@login_required
def resolution_delete(request, pk):
    resolution = get_object_or_404(Resolution, pk=pk)
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Only admins can delete resolutions.")
        return redirect('resolution_detail', pk=pk)
    if request.method == 'POST':
        resolution.delete()
        messages.success(request, 'Resolution deleted.')
        return redirect('resolution_list')
    return render(request, 'resolutions/confirm_delete.html', {'resolution': resolution})