from rest_framework import serializers
from employee.models import Department
from .models import Quotation, QuotationItem, MaterialStructure, MaterialRate, Term, AdditionTerm


class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = ['id', 'term', 'bydefault']


class QuotationItemSerializer(serializers.ModelSerializer):
    item_cylinder_cost = serializers.ReadOnlyField()
    itemtotalcost = serializers.ReadOnlyField()

    class Meta:
        model = QuotationItem
        fields = [
            'id', 'jobname', 'dimension', 'supply', 'structure', 'cyl_rate', 'no_of_cyl',
            'material_rate', 'pouch_per_kg', 'per_pouch_cost', 'moq', 'unit',
            'item_cylinder_cost', 'itemtotalcost',
        ]

    def validate(self, attrs):
        """Without a material rate there is nothing to price a Kg by:
        QuotationItem.save() can't derive per_pouch_cost (material_rate /
        pouch_per_kg), and itemtotalcost for a Kg item is material_rate x moq,
        i.e. 0. So such an item has to be sold per pouch, with the pouch cost
        typed in by hand."""
        if not attrs.get('material_rate'):
            errors = {}
            if not attrs.get('per_pouch_cost'):
                errors['per_pouch_cost'] = 'Required when there is no material rate.'
            if attrs.get('unit') == 'Kg':
                errors['unit'] = 'Cannot be Kg without a material rate -- use Nos.'
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class AdditionTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdditionTerm
        fields = ['id', 'term']


class QuotationListSerializer(serializers.ModelSerializer):
    """Read-only, list-sized twin of QuotationSerializer.

    The full serializer nests every item and term, spells the total out in
    words (num2words) and runs a Department query per approved row for
    can_edit -- none of which the list page shows. Detail, form and write
    responses keep the full serializer.
    """
    createdby_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    approvedby_name = serializers.CharField(source='approvedby.get_full_name', read_only=True, default=None)
    totalquotationcost = serializers.ReadOnlyField()

    class Meta:
        model = Quotation
        fields = [
            'id', 'partyname', 'add', 'contact', 'quotedate', 'remark', 'status',
            'created', 'createdby', 'createdby_name',
            'approvedby', 'approvedby_name', 'approved', 'is_deleted',
            'totalquotationcost',
        ]
        read_only_fields = fields


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(source='quotationitems', many=True, required=False)
    additional_terms = AdditionTermSerializer(source='additionalterms', many=True, required=False)

    createdby_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    editedby_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)
    approvedby_name = serializers.CharField(source='approvedby.get_full_name', read_only=True, default=None)

    designcost = serializers.ReadOnlyField()
    totalcylindercost = serializers.ReadOnlyField()
    grosscylindercost = serializers.ReadOnlyField()
    grossmaterialcost = serializers.ReadOnlyField()
    cylindergst = serializers.ReadOnlyField()
    materialgst = serializers.ReadOnlyField()
    totalmaterialcost = serializers.ReadOnlyField()
    totalquotationcost = serializers.ReadOnlyField()
    amountinword = serializers.ReadOnlyField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = [
            'id', 'partyname', 'add', 'contact', 'quotedate', 'remark', 'status',
            'design_rate', 'no_of_design', 'cylinder_gst', 'material_gst', 'quote_term',
            'items', 'additional_terms',
            'created', 'createdby', 'createdby_name',
            'edited', 'editedby', 'editedby_name',
            'approvedby', 'approvedby_name', 'approved', 'is_deleted', 'can_edit',
            'designcost', 'totalcylindercost', 'grosscylindercost', 'grossmaterialcost',
            'cylindergst', 'materialgst', 'totalmaterialcost', 'totalquotationcost', 'amountinword',
        ]
        read_only_fields = [
            'status', 'created', 'createdby', 'edited', 'editedby',
            'approvedby', 'approved', 'is_deleted',
        ]

    def get_can_edit(self, obj):
        # Matches the old editquote view: anyone can edit an unapproved quote,
        # but once approved only a can_approve_quote user may still edit it.
        if not obj.approvedby:
            return True
        request = self.context.get('request')
        if not request:
            return False
        return Department.objects.filter(
            department_name='can_approve_quote', user=request.user
        ).exists()

    def to_representation(self, instance):
        # QuotationItem.Meta.ordering is -id (newest first), and update() below
        # deletes+recreates every item on each save, giving them fresh ids —
        # so without this, the item order would visibly reverse on every save.
        # Sorting by id here (ascending = entry order) keeps display order
        # matching what was actually typed in, without touching the model's
        # ordering (other code, e.g. the PDF views, still relies on it as-is).
        data = super().to_representation(instance)
        data['items'] = sorted(data['items'], key=lambda item: item['id'])
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('quotationitems', [])
        terms_data = validated_data.pop('additionalterms', [])
        quote_terms = validated_data.pop('quote_term', [])
        request = self.context.get('request')

        quote = Quotation.objects.create(
            **validated_data,
            createdby=request.user if request else None,
        )
        if quote_terms:
            quote.quote_term.set(quote_terms)
        for item in items_data:
            QuotationItem.objects.create(quote=quote, **item)
        for term in terms_data:
            AdditionTerm.objects.create(quote=quote, **term)
        return quote

    def update(self, instance, validated_data):
        items_data = validated_data.pop('quotationitems', None)
        terms_data = validated_data.pop('additionalterms', None)
        quote_terms = validated_data.pop('quote_term', None)
        request = self.context.get('request')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if request:
            instance.editedby = request.user
        instance.save()

        if quote_terms is not None:
            instance.quote_term.set(quote_terms)

        # Line items and addition terms are edited as a whole set from the
        # frontend (like the old formset) — replace rather than diff/merge.
        if items_data is not None:
            instance.quotationitems.all().delete()
            for item in items_data:
                QuotationItem.objects.create(quote=instance, **item)

        if terms_data is not None:
            instance.additionalterms.all().delete()
            for term in terms_data:
                AdditionTerm.objects.create(quote=instance, **term)

        return instance
