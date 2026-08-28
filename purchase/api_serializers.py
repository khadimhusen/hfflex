from rest_framework import serializers
from rest_framework.reverse import reverse

from customer.models import Customer, Address
from material.models import Unit
from myproject.thumbnails import get_or_create_thumbnail
from .models import Po, PoItem, PoImage, ExpectedDate, Term
from .querysets import can_add_price, can_approve_po


class SupplierLookupSerializer(serializers.ModelSerializer):
    """Minimal supplier lookup for the PO 'supplier' field's dropdown —
    scoped to IsPurchaseUser rather than the customer module's own
    IsCustomerUser, same reasoning as itemmaster's/preorder's lookups."""

    class Meta:
        model = Customer
        fields = ['id', 'name']


class ShipToLookupSerializer(serializers.ModelSerializer):
    """'Ship to' options — the old PoForm.ship_to had no queryset override
    at all (any Customer, not just suppliers), unlike 'supplier'. Kept as
    its own lookup rather than reusing SupplierLookupViewSet's is_supplier
    filter, which would otherwise silently exclude HF Flex's own internal
    customer record (the field's actual default)."""

    class Meta:
        model = Customer
        fields = ['id', 'name']


class DeliveryAddressLookupSerializer(serializers.ModelSerializer):
    """'Ship to' address options — mirrors PoForm's hardcoded
    Address.objects.filter(customer_id=31), HF Flex's own internal
    customer record used for receiving goods."""

    class Meta:
        model = Address
        fields = ['id', 'addname', 'add1', 'add2', 'pincode']


class UnitLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'unit']


class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = ['id', 'term', 'bydefault']


class PoItemSerializer(serializers.ModelSerializer):
    unit_display = serializers.CharField(source='unit.unit', read_only=True)
    total = serializers.ReadOnlyField()
    pendingqty = serializers.ReadOnlyField()

    class Meta:
        model = PoItem
        fields = [
            'id', 'purchaseorder', 'description', 'category', 'qty', 'unit', 'unit_display',
            'rate', 'rec_qty', 'remark', 'total', 'pendingqty',
            'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        # Marketing users never see price data — mirrors the old
        # PoItemFormMarketing form, which excluded 'rate' from the edit
        # form entirely. Tightened here to also hide the derived 'total',
        # which would otherwise leak rate = total / qty.
        if request and not can_add_price(request.user):
            self.fields.pop('rate', None)
            self.fields.pop('total', None)

    def create(self, validated_data):
        # Old app: marketing users' formset.save(commit=False) explicitly
        # backfilled `instance.rate = (instance.rate or 0)` since their form
        # never collected a rate at all.
        validated_data.setdefault('rate', 0)
        return super().create(validated_data)


class PoImageSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = PoImage
        fields = [
            'id', 'po', 'imagename', 'poimage', 'thumbnail_url',
            'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def get_thumbnail_url(self, obj):
        url = get_or_create_thumbnail(obj.poimage)
        if not url:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


class ExpectedDateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = ExpectedDate
        fields = ['id', 'po', 'expected_date', 'remark', 'created', 'createdby', 'created_by_name']
        read_only_fields = ['created', 'createdby']


class PoSerializer(serializers.ModelSerializer):
    # The model field itself allows null (blank=True, null=True), but the
    # old PoForm required it (forms.DateTimeField has no blank=True), and
    # Po.save() unconditionally creates an initial ExpectedDate row from it
    # on first save — ExpectedDate.expected_date is NOT NULL, so a null
    # delivery_date here would crash that insert. Require it, matching the
    # old form's actual behavior.
    delivery_date = serializers.DateTimeField(required=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    # The old printable detail.html showed the supplier's own address(es),
    # GST, primary contact person and email alongside the PO — useful
    # context when reviewing/sending a PO, not just the bare name.
    supplier_gst = serializers.CharField(source='supplier.gst', read_only=True, default=None)
    supplier_email = serializers.CharField(source='supplier.email', read_only=True, default=None)
    supplier_addresses = serializers.SerializerMethodField()
    supplier_contact = serializers.SerializerMethodField()
    ship_to_name = serializers.CharField(source='ship_to.name', read_only=True, default=None)
    delivery_at_display = serializers.CharField(source='delivery_at.addname', read_only=True, default=None)
    delivery_at_detail = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)
    approved_by_name = serializers.CharField(source='approvedby.get_full_name', read_only=True, default=None)
    poterm = serializers.PrimaryKeyRelatedField(many=True, queryset=Term.objects.all(), required=False)
    itemcount = serializers.IntegerField(source='poitem.count', read_only=True)
    totalqty = serializers.ReadOnlyField()
    totalrecqty = serializers.ReadOnlyField()
    totalpendingqty = serializers.ReadOnlyField()
    pototal = serializers.ReadOnlyField()
    cgst = serializers.ReadOnlyField()
    sgst = serializers.ReadOnlyField()
    grosstotal = serializers.ReadOnlyField()
    inword = serializers.ReadOnlyField()
    delayed = serializers.SerializerMethodField()
    can_add_price = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Po
        fields = [
            'id', 'supplier', 'supplier_name', 'supplier_gst', 'supplier_email', 'supplier_addresses',
            'supplier_contact', 'delivery_date', 'payment_terms', 'tax1', 'tax2',
            'transport', 'remark', 'ship_to', 'ship_to_name', 'delivery_at', 'delivery_at_display',
            'delivery_at_detail', 'poterm', 'status', 'itemcount', 'totalqty', 'totalrecqty', 'totalpendingqty',
            'pototal', 'cgst', 'sgst', 'grosstotal', 'inword', 'delayed', 'can_add_price', 'can_approve', 'pdf_url',
            'created', 'createdby', 'created_by_name', 'approvedby', 'approved_by_name', 'approve_date',
            'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = [
            # 'status' is deliberately NOT read-only here — the old edit.html
            # form let users change it post-creation (only purchasenew.html's
            # CREATE flow forces it to "Pending", which perform_create still
            # does unconditionally via its save(status='Pending') kwarg).
            'created', 'createdby', 'approvedby', 'approve_date', 'edited', 'editedby',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        # Same price gate as PoItemSerializer.rate — tightened from the old
        # app, whose printable detail.html showed these to anyone who could
        # view the PO at all, regardless of the 'can_add_price' department.
        if request and not can_add_price(request.user):
            for field in ('pototal', 'cgst', 'sgst', 'grosstotal', 'inword'):
                self.fields.pop(field, None)

    def get_delayed(self, obj):
        if not obj.delivery_date:
            return False
        return obj.delayed

    def get_can_add_price(self, obj):
        request = self.context.get('request')
        return bool(request) and can_add_price(request.user)

    def get_can_approve(self, obj):
        request = self.context.get('request')
        return bool(request) and can_approve_po(request.user)

    def get_pdf_url(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        # Absolute URL, same convention as poimage/preimg/thumbnail_url
        # elsewhere — lets the SPA link straight to it without needing to
        # know the API's base URL itself.
        return reverse('po-pdf', kwargs={'pk': obj.pk}, request=request)

    def get_supplier_addresses(self, obj):
        return [
            {'addname': a.addname, 'add1': a.add1, 'add2': a.add2, 'pincode': a.pincode}
            for a in obj.supplier.addresses.all()
        ]

    def get_supplier_contact(self, obj):
        # Mirrors detail.html's `po.supplier.persons.all|slice:"1"` — just
        # the first contact person on file, not the whole list. Uses
        # .all() + Python indexing rather than .first(), which would issue
        # its own query and bypass the queryset's supplier__persons
        # prefetch (needed to avoid an N+1 across a list of POs).
        persons = list(obj.supplier.persons.all())
        if not persons:
            return None
        return {'name': persons[0].name, 'mobile': persons[0].mobile}

    def get_delivery_at_detail(self, obj):
        if not obj.delivery_at:
            return None
        a = obj.delivery_at
        return {'addname': a.addname, 'add1': a.add1, 'add2': a.add2, 'pincode': a.pincode}
