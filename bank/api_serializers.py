from rest_framework import serializers

from .models import Bank, Cheque


class BankLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = ['id', 'account_name', 'bankname', 'account_number']


class BankSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)

    class Meta:
        model = Bank
        fields = [
            'id', 'account_name', 'bankname', 'account_number', 'ifsc', 'branch',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class ChequeSerializer(serializers.ModelSerializer):
    """Mirrors ChequeEditForm exactly (party/cheque_date/amount/status/
    expected_date/bill_number/bill_date/remark) -- bank/number are set
    once at creation (via the bulk-create action mirroring chequeadd)
    and never re-edited afterwards, same as the old app."""
    bank_display = serializers.CharField(source='bank.__str__', read_only=True)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)
    amountinword = serializers.ReadOnlyField()
    amountint = serializers.ReadOnlyField()

    class Meta:
        model = Cheque
        fields = [
            'id', 'bank', 'bank_display', 'number', 'party', 'cheque_date', 'amount', 'status',
            'expected_date', 'bill_number', 'bill_date', 'remark', 'lock_record', 'amountinword', 'amountint',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['bank', 'number', 'created', 'createdby', 'edited', 'editedby']
