from django.db import models
import os
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import Document
from .forms import DocumentUploadForm, ManageViewersForm


@login_required
def document_list(request):
    docs = Document.objects.filter(
        models.Q(uploaded_by=request.user) | models.Q(viewers=request.user)
    ).distinct().select_related('uploaded_by')

    query = request.GET.get('q', '').strip()
    if query:
        docs = docs.filter(title__icontains=query)

    return render(request, 'documents/list.html', {
        'documents': docs,
        'query': query,
    })

@login_required
def document_upload(request):
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            doc.save()
            form.save_m2m()
            messages.success(request, 'Document uploaded.')
            return redirect('documents:list')
    else:
        form = DocumentUploadForm(user=request.user)
    return render(request, 'documents/upload.html', {'form': form})


@login_required
def document_detail(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if not doc.has_access(request.user):
        raise PermissionDenied  # 403, don't leak existence via 404 vs 403 if you prefer
    return render(request, 'documents/detail.html', {'document': doc})


@login_required
def document_download(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if not doc.has_access(request.user):
        raise PermissionDenied

    if not doc.file or not os.path.exists(doc.file.path):
        raise Http404("File not found")

    filename = os.path.basename(doc.file.name)
    return FileResponse(
        doc.file.open('rb'),
        as_attachment=True,
        filename=filename,
    )


@login_required
def manage_viewers(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    # only the creator (or superuser) can change who has access
    if doc.uploaded_by_id != request.user.id and not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'POST':
        form = ManageViewersForm(request.POST, instance=doc)
        if form.is_valid():
            form.save()
            messages.success(request, 'Viewers updated.')
            return redirect('documents:detail', pk=doc.pk)
    else:
        form = ManageViewersForm(instance=doc)
    return render(request, 'documents/manage_viewers.html', {'form': form, 'document': doc})

from django.views.decorators.http import require_POST

@login_required
@require_POST
def document_delete(request, pk):
    doc = get_object_or_404(Document, pk=pk)

    if doc.uploaded_by_id != request.user.id and not request.user.is_superuser:
        raise PermissionDenied

    # remove the physical file from disk before deleting the DB row
    if doc.file:
        doc.file.delete(save=False)

    title = doc.title
    doc.delete()
    messages.success(request, f'"{title}" was deleted.')
    return redirect('documents:list')