from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MixedInk
from .api_serializers import MixedInkSerializer
from .permissions import IsInkStoreUser
from .utils import delta_e_cie76, sort_by_nearest_neighbour_grouped


class MixedInkViewSet(viewsets.ModelViewSet):
    """Mirrors ink_list (filters + sorting) and edit_ink (update).

    No create/delete: the old app has neither -- the can list is fixed
    stock that only ever gets its readings filled in.
    """
    http_method_names = ['get', 'patch', 'put', 'head', 'options']
    serializer_class = MixedInkSerializer
    permission_classes = [IsInkStoreUser]
    queryset = MixedInk.objects.all()

    def get_queryset(self):
        qs = MixedInk.objects.all()
        params = self.request.query_params

        can_id = params.get('id', '').strip()
        if can_id:
            qs = qs.filter(pk=can_id)

        # Same three-state 'data' filter as ink_list: anything measured,
        # or a can still sitting at all-zeros waiting to be read.
        data = params.get('data', '').strip()
        if data == 'has_data':
            qs = qs.filter(l_nw__gt=0.00, l_ww__gt=0.00)
        elif data == 'empty':
            qs = qs.filter(l_nw=0, a_nw=0, b_nw=0, l_ww=0, a_ww=0, b_ww=0)

        notes = params.get('notes', '').strip()
        if notes:
            qs = qs.filter(notes__icontains=notes)

        return qs

    def list(self, request, *args, **kwargs):
        # nn_nw/nn_ww order cans so visually similar colours sit together
        # (nearest-neighbour chained within 30-degree hue groups). That is
        # a Python pass over the whole filtered set, not something the DB
        # can order by -- hence the manual list + paginate here rather than
        # an ordering= on the queryset. ~1000 cans total, so the cost is
        # bounded; this is exactly what ink_list already did.
        qs = self.filter_queryset(self.get_queryset())
        sort = request.query_params.get('sort', 'id')

        inks = list(qs)
        if sort == 'nn_nw':
            inks = sort_by_nearest_neighbour_grouped(inks, mode='nw')
        elif sort == 'nn_ww':
            inks = sort_by_nearest_neighbour_grouped(inks, mode='ww')
        else:
            inks.sort(key=lambda ink: ink.id)

        page = self.paginate_queryset(inks)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(inks, many=True).data)


class InkSearchView(APIView):
    """Mirrors search_ink: given a target LAB reading, rank the stored cans
    by CIE76 Delta E and return the closest ones.

    GET rather than the old view's POST -- nothing is created or changed,
    and it keeps a search shareable/bookmarkable as a URL.
    """
    permission_classes = [IsInkStoreUser]

    def get(self, request):
        params = request.query_params

        try:
            target_l = float(params['L'])
            target_a = float(params['A'])
            target_b = float(params['B'])
        except (KeyError, TypeError, ValueError):
            return Response(
                {'detail': 'Enter valid numeric L, A and B values.'}, status=400,
            )

        mode = params.get('mode', 'nw')
        if mode not in ('nw', 'ww'):
            return Response({'mode': ["Must be 'nw' or 'ww'."]}, status=400)

        try:
            top_n = int(params.get('top_n', 10))
        except (TypeError, ValueError):
            top_n = 10
        top_n = max(1, min(top_n, 100))

        if mode == 'nw':
            inks = MixedInk.objects.exclude(l_nw__isnull=True)
        else:
            inks = MixedInk.objects.exclude(l_ww__isnull=True)

        scored = []
        for ink in inks:
            if mode == 'nw':
                ink_l, ink_a, ink_b = ink.l_nw, ink.a_nw, ink.b_nw
            else:
                ink_l, ink_a, ink_b = ink.l_ww, ink.a_ww, ink.b_ww
            if ink_l is None or ink_a is None or ink_b is None:
                continue
            scored.append({
                'de': round(delta_e_cie76(target_l, target_a, target_b, ink_l, ink_a, ink_b), 2),
                'ink': ink,
                'L': ink_l,
                'A': ink_a,
                'B': ink_b,
            })

        scored.sort(key=lambda item: item['de'])
        results = [
            {
                'rank': rank,
                'de': item['de'],
                'L': item['L'],
                'A': item['A'],
                'B': item['B'],
                'ink': MixedInkSerializer(item['ink']).data,
            }
            for rank, item in enumerate(scored[:top_n], start=1)
        ]

        return Response({
            'target': {'L': target_l, 'A': target_a, 'B': target_b},
            'mode': mode,
            'top_n': top_n,
            'count': len(results),
            'results': results,
        })
