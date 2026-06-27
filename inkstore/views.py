import math
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import MixedInk
from .utils import delta_e_cie76


def get_hue(L, a, b):
    if a is None or b is None:
        return 999
    # treat 0,0,0 (unmeasured dummy rows) as no data
    if float(L) == 0 and float(a) == 0 and float(b) == 0:
        return 999
    h = math.degrees(math.atan2(float(b), float(a)))
    return h + 360 if h < 0 else h

@login_required(login_url='/login/')
def ink_list(request):
    qs = MixedInk.objects.all()

    # ── Filters ──
    can_id = request.GET.get('id', '').strip()
    data   = request.GET.get('data', '').strip()
    notes  = request.GET.get('notes', '').strip()
    sort   = request.GET.get('sort', 'id')   # 'id' | 'hue_nw' | 'hue_ww'

    if can_id:
        qs = qs.filter(pk=can_id)
    if data == 'has_data':
        qs = qs.exclude(l_nw__isnull=True, l_ww__isnull=True)
    elif data == 'empty':
        qs = qs.filter(l_nw__isnull=True, l_ww__isnull=True)
    if notes:
        qs = qs.filter(notes__icontains=notes)

    # ── Sorting ──
    ink_list_qs = list(qs)

    if sort == 'hue_nw':
        ink_list_qs.sort(key=lambda ink: get_hue(ink.l_nw, ink.a_nw, ink.b_nw))
    elif sort == 'hue_ww':
        ink_list_qs.sort(key=lambda ink: get_hue(ink.l_ww, ink.a_ww, ink.b_ww))
    elif sort == 'hue_nw_desc':
        ink_list_qs.sort(key=lambda ink: get_hue(ink.l_nw, ink.a_nw, ink.b_nw), reverse=True)
    elif sort == 'hue_ww_desc':
        ink_list_qs.sort(key=lambda ink: get_hue(ink.l_ww, ink.a_ww, ink.b_ww), reverse=True)
    else:
        ink_list_qs.sort(key=lambda ink: ink.id)

    # ── Pagination ──
    paginator  = Paginator(ink_list_qs, 100)
    page_num   = request.GET.get('page', 1)
    page_obj   = paginator.get_page(page_num)

    get_copy = request.GET.copy()
    get_copy.pop('page', None)
    query_string = get_copy.urlencode()

    return render(request, 'inkstore/list.html', {
        'page_obj':     page_obj,
        'query_string': query_string,
        'sort':         sort,
    })


@login_required(login_url='/login/')
def search_ink(request):
    results = []
    target  = None
    mode    = 'nw'
    top_n   = 10
    error   = None

    if request.method == 'POST':
        mode = request.POST.get('mode', 'nw')
        try:
            top_n = int(request.POST.get('top_n', 10))
        except ValueError:
            top_n = 10

        try:
            tL = float(request.POST['L'])
            tA = float(request.POST['A'])
            tB = float(request.POST['B'])
        except (KeyError, ValueError):
            error = 'Please enter valid numeric L, A, B values.'
            return render(request, 'inkstore/search.html', {
                'error': error, 'mode': mode, 'top_n': top_n,
            })

        target = {'L': tL, 'A': tA, 'B': tB}

        if mode == 'nw':
            inks = MixedInk.objects.exclude(l_nw__isnull=True)
        else:
            inks = MixedInk.objects.exclude(l_ww__isnull=True)

        scored = []
        for ink in inks:
            if mode == 'nw':
                de = delta_e_cie76(tL, tA, tB, ink.l_nw, ink.a_nw, ink.b_nw)
                ink_L, ink_A, ink_B = ink.l_nw, ink.a_nw, ink.b_nw
            else:
                de = delta_e_cie76(tL, tA, tB, ink.l_ww, ink.a_ww, ink.b_ww)
                ink_L, ink_A, ink_B = ink.l_ww, ink.a_ww, ink.b_ww

            scored.append({
                'rank': 0, 'de': round(de, 2),
                'ink': ink, 'L': ink_L, 'A': ink_A, 'B': ink_B,
            })

        scored.sort(key=lambda x: x['de'])
        for i, item in enumerate(scored[:top_n], start=1):
            item['rank'] = i
        results = scored[:top_n]

    return render(request, 'inkstore/search.html', {
        'results': results, 'target': target,
        'mode': mode, 'top_n': top_n, 'error': error,
    })


@login_required(login_url='/login/')
def edit_ink(request, pk):
    ink = get_object_or_404(MixedInk, pk=pk)

    if request.method == 'POST':
        try:
            def to_dec(val):
                return val if val.strip() != '' else None

            ink.l_nw  = to_dec(request.POST.get('l_nw', ''))
            ink.a_nw  = to_dec(request.POST.get('a_nw', ''))
            ink.b_nw  = to_dec(request.POST.get('b_nw', ''))
            ink.l_ww  = to_dec(request.POST.get('l_ww', ''))
            ink.a_ww  = to_dec(request.POST.get('a_ww', ''))
            ink.b_ww  = to_dec(request.POST.get('b_ww', ''))
            ink.qty   = to_dec(request.POST.get('qty', ''))
            ink.notes = request.POST.get('notes', '')
            ink.save()
            messages.success(request, f'Can #{ink.id} updated successfully.')
            return redirect('inkstore:edit', pk=ink.pk)
        except Exception as e:
            messages.warning(request, f'Error saving: {e}')

    return render(request, 'inkstore/edit.html', {'ink': ink})