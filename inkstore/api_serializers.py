from rest_framework import serializers

from .models import MixedInk


class MixedInkSerializer(serializers.ModelSerializer):
    """Mirrors edit_ink's editable set (the six LAB readings + qty + notes).

    delta_nw_ww is the model's own property -- how far the with-white
    reading sits from the no-white one -- exposed so the list can show it
    without the client re-deriving it and risking a different answer.
    """

    delta_nw_ww = serializers.SerializerMethodField()

    class Meta:
        model = MixedInk
        fields = [
            'id', 'qty', 'notes',
            'l_nw', 'a_nw', 'b_nw',
            'l_ww', 'a_ww', 'b_ww',
            'delta_nw_ww',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_delta_nw_ww(self, obj):
        # The property does float maths on all six values; any of them
        # being null (a can that has only ever been half-measured) would
        # raise rather than return a number.
        fields = (obj.l_nw, obj.a_nw, obj.b_nw, obj.l_ww, obj.a_ww, obj.b_ww)
        if any(value is None for value in fields):
            return None
        return obj.delta_nw_ww
