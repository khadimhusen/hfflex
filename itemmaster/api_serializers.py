from rest_framework import serializers

from customer.models import Customer
from material.models import Material, MatType, Grade, Unit, Commodity
from .querysets import can_edit_itemmaster
from .models import (
    Machine, MachineTask, PouchType, LamiRubber, ItemMaster, ItemImage,
    RawMaterial, Process, ItemProcess, Color, ItemColor, Problem,
    AttributeMaster, ItemAttribute, CylinderMovement, StdParameter,
    ItemStandardParameter,
)


class CustomerLookupSerializer(serializers.ModelSerializer):
    """Minimal customer lookup for itemmaster's own dropdowns (itemcustomer,
    cylinder_manufacture, cylinder-movement location) — scoped to
    IsItemmasterUser rather than the customer module's own IsCustomerUser,
    since an itemmaster user has no reason to also need customer-module
    access just to pick a customer here (same pattern as
    customer.MarketingUserViewSet reaching into a different app's users)."""

    class Meta:
        model = Customer
        fields = ['id', 'name']


# Same reasoning as CustomerLookupSerializer above — RawMaterial/ItemProcess
# need Material/MatType/Grade/Unit dropdowns, but the material module is
# staff-only (IsAdminUser), which almost no itemmaster user would satisfy.
class MaterialLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ['id', 'name']


class MatTypeLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatType
        fields = ['id', 'mat_type']


class GradeLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ['id', 'grade']


class UnitLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'unit']


class CommodityLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Commodity
        fields = ['id', 'commodity']


class TimestampedSerializerMixin(serializers.Serializer):
    created_by_name = serializers.CharField(
        source='createdby.get_full_name', read_only=True, default=None,
    )
    edited_by_name = serializers.CharField(
        source='editedby.get_full_name', read_only=True, default=None,
    )


# ---- small lookup tables -------------------------------------------------

class PouchTypeSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = PouchType
        fields = ['id', 'pouchtype', 'created', 'createdby', 'created_by_name',
                  'edited', 'editedby', 'edited_by_name']
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class LamiRubberSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = LamiRubber
        fields = ['id', 'rubber', 'status', 'created', 'createdby', 'created_by_name',
                  'edited', 'editedby', 'edited_by_name']
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class ProcessSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Process
        fields = ['id', 'process', 'created', 'createdby', 'created_by_name',
                  'edited', 'editedby', 'edited_by_name']
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ['id', 'colorname', 'pantonecolor', 'hexcode']


class ProblemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Problem
        fields = ['id', 'problem', 'is_active']


class AttributeMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttributeMaster
        fields = ['id', 'attribute']


class StdParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = StdParameter
        fields = ['id', 'parameter', 'unit_of_measure']


class MachineSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True, default=None)

    class Meta:
        model = Machine
        fields = ['id', 'machinename', 'max_speed', 'mode_speed', 'default_persons',
                  'est_date', 'end_date', 'active', 'user', 'user_name']


class MachineTaskSerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source='machine.machinename', read_only=True)

    class Meta:
        model = MachineTask
        fields = ['id', 'machine', 'machine_name', 'category', 'persons_required',
                  'task', 'qty_from_colors', 'default_qty', 'duration']


# ---- itemmaster sub-resources --------------------------------------------

class ItemImageSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ItemImage
        fields = ['id', 'imagename', 'itemname', 'created', 'createdby', 'created_by_name',
                  'edited', 'editedby', 'edited_by_name']
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class RawMaterialSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    materialname_display = serializers.CharField(source='materialname.name', read_only=True)
    item_mat_type_display = serializers.CharField(source='item_mat_type.mat_type', read_only=True)
    item_grade_display = serializers.CharField(source='item_grade.grade', read_only=True)

    class Meta:
        model = RawMaterial
        fields = ['id', 'itemmaster', 'materialname', 'materialname_display',
                  'item_mat_type', 'item_mat_type_display', 'item_grade', 'item_grade_display',
                  'size', 'micron', 'gsm', 'created', 'createdby', 'created_by_name',
                  'edited', 'editedby', 'edited_by_name']
        read_only_fields = ['gsm', 'created', 'createdby', 'edited', 'editedby']


class ItemProcessSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    process_display = serializers.CharField(source='process.process', read_only=True)
    unit_display = serializers.CharField(source='unit.unit', read_only=True)
    machine_display = serializers.CharField(source='machine.machinename', read_only=True, default=None)

    class Meta:
        model = ItemProcess
        fields = ['id', 'itemmaster', 'process', 'process_display', 'unit', 'unit_display',
                  'machine', 'machine_display', 'process_count', 'speed',
                  'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name']
        # process_count is auto-assigned by the model's save() (next count for
        # this item+process pair) — never client-settable, matching the old
        # inline formset which never exposed it either.
        read_only_fields = ['process_count', 'created', 'createdby', 'edited', 'editedby']


class ItemColorSerializer(serializers.ModelSerializer):
    color_display = serializers.CharField(source='color.colorname', read_only=True, default=None)

    class Meta:
        model = ItemColor
        fields = ['id', 'itemmaster', 'color', 'color_display', 'remark']


class ItemAttributeSerializer(serializers.ModelSerializer):
    attribute_display = serializers.CharField(source='item_attirbuate.attribute', read_only=True)

    class Meta:
        model = ItemAttribute
        fields = ['id', 'itemmaster', 'item_attirbuate', 'attribute_display', 'attri_value']


class ItemStandardParameterSerializer(serializers.ModelSerializer):
    parameter_display = serializers.CharField(source='standard_parameter.parameter', read_only=True)
    unit_of_measure = serializers.CharField(source='standard_parameter.unit_of_measure', read_only=True)

    class Meta:
        model = ItemStandardParameter
        fields = ['id', 'itemmaster', 'standard_parameter', 'parameter_display',
                  'unit_of_measure', 'value']


class CylinderMovementSerializer(serializers.ModelSerializer):
    # Matches CylinderMovementForm's old restriction — only these named
    # locations, or the item's own customer, are valid drop points.
    location = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    location_name = serializers.CharField(source='location.name', read_only=True)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = CylinderMovement
        fields = ['id', 'movementdate', 'item', 'location', 'location_name', 'remark',
                  'row', 'column', 'deleted', 'created', 'createdby', 'created_by_name']
        read_only_fields = ['created', 'createdby']

    def validate(self, attrs):
        item = attrs.get('item') or getattr(self.instance, 'item', None)
        location = attrs.get('location') or getattr(self.instance, 'location', None)
        if item and location:
            allowed_names = ['GODOWN-1', 'GODOWN-2', 'PRODUCTION', item.itemcustomer.name]
            if location.name not in allowed_names:
                raise serializers.ValidationError({
                    'location': f'Must be one of GODOWN-1, GODOWN-2, PRODUCTION, or the '
                                 f'item\'s own customer ({item.itemcustomer.name}).'
                })
        return attrs


# ---- ItemMaster itself ----------------------------------------------------

class ItemMasterSerializer(serializers.ModelSerializer):
    itemcustomer_name = serializers.CharField(source='itemcustomer.name', read_only=True)
    pouch_type_display = serializers.CharField(source='pouch_type.pouchtype', read_only=True, default=None)
    lami_rubber_display = serializers.SerializerMethodField()
    commodity_display = serializers.CharField(source='commodity.commodity', read_only=True, default=None)
    cylinder_manufacture_name = serializers.CharField(
        source='cylinder_manufacture.name', read_only=True, default=None,
    )
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)

    micron = serializers.SerializerMethodField()
    ply = serializers.SerializerMethodField()
    isnew = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    # Declared explicitly — the model's limit_choices_to (is_supplier=True,
    # active=True, supplier_item__itemname='Cylinder') isn't picked up
    # automatically by DRF's auto-generated field for a ForeignKey with a
    # dict-valued limit_choices_to referencing a M2M lookup.
    cylinder_manufacture = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.filter(
            is_supplier=True, active=True, supplier_item__itemname='Cylinder',
        ).distinct(),
        required=False, allow_null=True,
    )

    class Meta:
        model = ItemMaster
        fields = [
            'id', 'itemname', 'itemcode', 'itemcustomer', 'itemcustomer_name', 'barcode',
            'packsize', 'replength', 'openwidth', 'slit_size', 'no_of_repeat', 'no_of_ups',
            'cyl_length', 'cyl_circum', 'cylinder_status', 'cylinder_manufacture',
            'cylinder_manufacture_name', 'printing', 'total_gsm', 'pouch_weight', 'pouch_per_kg',
            'pouch_type', 'pouch_type_display', 'supply_form', 'film_size', 'remark',
            'unwind_direction', 'lami_rubber', 'lami_rubber_display', 'active', 'shade_accuracy',
            'commodity', 'commodity_display', 'micron', 'ply', 'isnew', 'can_edit',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = [
            'total_gsm', 'pouch_weight', 'pouch_per_kg',
            'created', 'createdby', 'edited', 'editedby',
        ]

    def validate_itemname(self, value):
        return value.strip().upper()

    def get_lami_rubber_display(self, obj):
        return str(obj.lami_rubber) if obj.lami_rubber_id else None

    def get_micron(self, obj):
        return obj.micron

    def get_ply(self, obj):
        return obj.ply

    def get_isnew(self, obj):
        return obj.isnew

    def get_can_edit(self, obj):
        if obj.pk is None:
            return True  # not yet created — the "New Item" form itself
        request = self.context.get('request')
        if not request:
            return False
        return can_edit_itemmaster(request.user, obj)
