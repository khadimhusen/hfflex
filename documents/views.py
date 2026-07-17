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

from documents.search_indexes import DocumentIndex

@login_required(login_url='/login/')
def document_list(request):
    query = request.GET.get('q', '').strip()

    if query:
        es_results = DocumentIndex.search().query(
            'multi_match', query=query,
            fields=['title^2', 'description','uploaded_by_username'],
            fuzziness='AUTO')

        pks = [hit.meta.id for hit in es_results]
        docs = list(Document.objects.filter(pk__in=pks))
        docs.sort(key=lambda d: pks.index(str(d.pk)))
    else:
        docs = list(Document.objects.all())

    docs = [
        d for d in docs
        if d.uploaded_by_id == request.user.id
        or d.viewers.filter(pk=request.user.pk).exists()
        or request.user.is_superuser
    ]

    return render(request, 'documents/list.html', {'documents': docs, 'query': query})

@login_required(login_url='/login/')
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


@login_required(login_url='/login/')
def document_detail(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if not doc.has_access(request.user):
        raise PermissionDenied  # 403, don't leak existence via 404 vs 403 if you prefer
    return render(request, 'documents/detail.html', {'document': doc})


@login_required(login_url='/login/')
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


@login_required(login_url='/login/')
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

@login_required(login_url='/login/')
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