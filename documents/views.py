from django.db import models
import logging
import os
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import Document, DocumentDownloadLog
from .forms import DocumentUploadForm, ManageViewersForm

from django.db.models import Q
from elastic_transport import TransportError

from documents.search_indexes import DocumentIndex

logger = logging.getLogger(__name__)


@login_required(login_url='/login/')
def document_list(request):
    query = request.GET.get('q', '').strip()

    if query:
        # Plain substring matches -- "pan" finds "PANCARD". Elasticsearch's
        # fuzzy multi_match matches whole words only (and allows no typo at
        # all in a 3-letter word), so on its own it never found them. Same
        # union the CRM's documents API does (api_viewsets._search).
        substring = Document.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
            | Q(uploaded_by__username__icontains=query))

        try:
            es_results = DocumentIndex.search().query(
                'multi_match', query=query,
                fields=['title^2', 'description', 'uploaded_by_username'],
                fuzziness='AUTO')[:500]  # without a size, ES returns its top 10 only
            pks = [str(hit.meta.id) for hit in es_results]
        except TransportError:
            logger.warning('Elasticsearch search failed (is it running?) -- falling back to a DB search.')
            pks = []

        # ES's relevance-ranked (typo-tolerant) hits first, then any
        # substring match ES didn't return.
        docs = list(Document.objects.filter(pk__in=pks))
        docs.sort(key=lambda d: pks.index(str(d.pk)))
        docs += [d for d in substring if str(d.pk) not in pks]
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


def get_client_ip(request):
    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@login_required
def document_download(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if not doc.has_access(request.user):
        raise PermissionDenied

    if not doc.file:
        raise Http404("File not found")

    # log the download before serving the file
    DocumentDownloadLog.objects.create(
        document=doc,
        downloaded_by=request.user,
        ip_address=get_client_ip(request),
    )

    response = HttpResponse()
    response['Content-Type'] = ''
    response['X-Accel-Redirect'] = f'/media/{doc.file.name}'
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(doc.file.name)}"'
    return response
