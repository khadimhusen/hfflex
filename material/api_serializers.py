from rest_framework import serializers

from .models import Commodity, Material, MatType, Grade, Unit, PurchaseMaterial


class TimestampedSerializerMixin(serializers.Serializer):
    """Every material master-data model with the same
    created/createdby/edited/editedby stamp fields uses this."""
    created_by_name = serializers.CharField(
        source='createdby.get_full_name', read_only=True, default=None,
    )
    edited_by_name = serializers.CharField(
        source='editedby.get_full_name', read_only=True, default=None,
    )


# Each unique CharField below (name/mat_type/grade/unit) is declared
# explicitly with its own validate_<field> — the model's save() uppercases
# the value, so DRF's auto-generated UniqueValidator (which would otherwise
# run on the raw, still-mixed-case input) is skipped in favor of checking
# uniqueness AFTER normalizing, avoiding a same-name-different-case
# duplicate slipping past validation into a raw IntegrityError.


class CommoditySerializer(serializers.ModelSerializer):
    class Meta:
        model = Commodity
        fields = ['id', 'commodity']


class MaterialSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    name = serializers.CharField(max_length=32)

    class Meta:
        model = Material
        fields = [
            'id', 'name', 'density', 'solid', 'weightgain', 'state',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def validate_name(self, value):
        value = value.strip().upper()
        qs = Material.objects.filter(name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f'Material "{value}" already exists.')
        return value


class MatTypeSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    mat_type = serializers.CharField(max_length=32)

    class Meta:
        model = MatType
        fields = [
            'id', 'mat_type',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def validate_mat_type(self, value):
        value = value.strip().upper()
        qs = MatType.objects.filter(mat_type=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f'Material type "{value}" already exists.')
        return value


class GradeSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    grade = serializers.CharField(max_length=32)

    class Meta:
        model = Grade
        fields = [
            'id', 'grade',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def validate_grade(self, value):
        value = value.strip().upper()
        qs = Grade.objects.filter(grade=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f'Grade "{value}" already exists.')
        return value


class UnitSerializer(TimestampedSerializerMixin, serializers.ModelSerializer):
    unit = serializers.CharField(max_length=8)

    class Meta:
        model = Unit
        fields = [
            'id', 'unit',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def validate_unit(self, value):
        value = value.strip().upper()
        qs = Unit.objects.filter(unit=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f'Unit "{value}" already exists.')
        return value


class PurchaseMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseMaterial
        fields = ['id', 'itemname']
