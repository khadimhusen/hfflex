from django.db import IntegrityError
from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import Customer
from .filters import ChequeFilter
from .models import Bank, Cheque
from .api_serializers import BankLookupSerializer, BankSerializer, ChequeSerializer
from .permissions import IsBankUser


class BankLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Bank.objects.order_by('account_name')
    serializer_class = BankLookupSerializer
    permission_classes = [IsBankUser]


class BankViewSet(viewsets.ModelViewSet):
    queryset = Bank.objects.select_related('createdby', 'editedby').order_by('account_name')
    serializer_class = BankSerializer
    permission_classes = [IsBankUser]

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class ChequeViewSet(viewsets.ModelViewSet):
    """Mirrors chequelist/chequeadd/chequeedit. bank/number are only ever
    set by bulk_create (mirrors chequeadd's range loop) -- never through a
    plain create/update, same as the old app never offered either."""
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = Cheque.objects.select_related('bank', 'createdby', 'editedby')
    serializer_class = ChequeSerializer
    permission_classes = [IsBankUser]
    filterset_class = ChequeFilter

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    def list(self, request, *args, **kwargs):
        """Mirrors chequelist()'s header count/total -- summed over the
        whole filtered queryset, not just the current page."""
        response = super().list(request, *args, **kwargs)
        qs = self.filter_queryset(self.get_queryset())
        response.data['total_amount'] = qs.aggregate(total=Sum('amount'))['total'] or 0
        return response

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """Mirrors chequeadd(): creates one Cheque per number in
        [startnum, endnum] for the given bank, silently skipping any
        number that already exists for that bank (unique_together)."""
        bank_id = request.data.get('bank')
        startnum = request.data.get('startnum')
        endnum = request.data.get('endnum')
        if not bank_id or startnum is None or endnum is None:
            raise ValidationError('bank, startnum and endnum are required.')
        bank = Bank.objects.filter(pk=bank_id).first()
        if not bank:
            raise ValidationError('Invalid bank.')
        startnum, endnum = int(startnum), int(endnum)
        if endnum < startnum:
            raise ValidationError('endnum must be greater than or equal to startnum.')

        created_count = 0
        for num in range(startnum, endnum + 1):
            try:
                Cheque.objects.create(bank=bank, number=num, createdby=request.user)
                created_count += 1
            except IntegrityError:
                pass
        return Response({'status': 'ok', 'created': created_count, 'requested': endnum - startnum + 1})


class PartyLookupView(APIView):
    """Mirrors chequeedit()'s partylist: supplier customer names plus
    every distinct party name already used on a Cheque, deduped and
    sorted -- feeds the party field's autocomplete."""
    permission_classes = [IsBankUser]

    def get(self, request):
        customer_names = Customer.objects.filter(is_supplier=True).exclude(
            name__isnull=True,
        ).exclude(name='').values_list('name', flat=True)
        cheque_names = Cheque.objects.exclude(party__isnull=True).exclude(party='').values_list(
            'party', flat=True,
        ).distinct()
        parties = sorted(set(customer_names) | set(cheque_names))
        return Response(parties)
