from rest_framework import serializers
from .models import Quotation, QuotationItem, MaterialStructure, MaterialRate, Term, AdditionTerm


class QuotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        fields = ["partyname",
                  "add",
                  "contact",
                  "quotedate",
                  "remark",
                  "design_rate",
                  "no_of_design",
                  "cylinder_gst",
                  "material_gst",
                  "quote_term"]
