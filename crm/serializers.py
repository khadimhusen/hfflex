from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Pipeline, DealStageName, DealStage, DealStageHistory,
    Account, Contact, Deal, Lead, DealAttachment, Note, DealTask,
)
from .querysets import crm_users
from django.utils import timezone

class OwnerSerializerMixin(serializers.Serializer):
    """Every model with an `owner` FK needs this same restriction —
    defined once, mixed into each serializer below."""
    owner = serializers.PrimaryKeyRelatedField(queryset=crm_users())
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)


class PipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pipeline
        fields = ['id', 'name']


class DealStageNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = DealStageName
        fields = ['id', 'name']


class DealStageSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source='dealstagename.name', read_only=True)
    pipeline_name = serializers.CharField(source='pipeline.name', read_only=True)

    class Meta:
        model = DealStage
        fields = [
            'id', 'pipeline', 'pipeline_name', 'dealstagename', 'stage_name',
            'order', 'probability', 'is_won', 'is_lost', 'max_stall_time', 'color',
        ]


class AccountSerializer(OwnerSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            'id', 'zoho_record_id', 'name', 'account_number', 'phone',
            'billing_street', 'billing_city', 'billing_state', 'billing_country', 'billing_code',
            'website', 'industry', 'annual_revenue', 'enquiry_notes',
            'owner', 'owner_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['zoho_record_id', 'created_at', 'updated_at']


class ContactSerializer(OwnerSerializerMixin, serializers.ModelSerializer):
    name = serializers.ReadOnlyField()  # exposes the @property from the model
    account_name = serializers.CharField(source='account.name', read_only=True, default=None)

    class Meta:
        model = Contact
        fields = [
            'id', 'zoho_record_id', 'salutation', 'first_name', 'last_name', 'name',
            'account', 'account_name', 'title', 'email', 'phone', 'mobile',
            'mailing_street', 'mailing_city', 'mailing_state', 'mailing_country', 'mailing_zip',
            'lead_source', 'description', 'owner', 'owner_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['zoho_record_id', 'created_at', 'updated_at']


class DealSerializer(OwnerSerializerMixin, serializers.ModelSerializer):
    expected_revenue = serializers.ReadOnlyField()
    account_name = serializers.CharField(source='account.name', read_only=True, default=None)
    contact_name = serializers.CharField(source='contact.name', read_only=True, default=None)
    stage_name = serializers.CharField(source='stage.dealstagename.name', read_only=True)
    pipeline_name = serializers.CharField(source='pipeline.name', read_only=True)
    is_won = serializers.BooleanField(source='stage.is_won', read_only=True)
    is_lost = serializers.BooleanField(source='stage.is_lost', read_only=True)
    stage_entered_at = serializers.DateTimeField(read_only=True)
    is_stalled = serializers.BooleanField(read_only=True)
    days_in_stage = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = [
            'id', 'zoho_record_id', 'name', 'pipeline', 'pipeline_name',
            'stage', 'stage_name', 'is_won', 'is_lost',
            'account', 'account_name', 'contact', 'contact_name',
            'amount', 'expected_revenue', 'deal_type', 'city', 'lost_reason', 'lead_source',
            'closing_date', 'owner', 'owner_name', 'description', 'created_at', 'updated_at',
            'stage_entered_at', 'is_stalled', 'days_in_stage',
        ]
        read_only_fields = ['zoho_record_id', 'created_at', 'updated_at']

    def get_days_in_stage(self, obj):
        entered = getattr(obj, 'stage_entered_at', None)
        if not entered:
            return None
        return (timezone.now() - entered).days

    def validate(self, attrs):
        pipeline = attrs.get('pipeline', getattr(self.instance, 'pipeline', None))
        stage = attrs.get('stage', getattr(self.instance, 'stage', None))
        if pipeline and stage and stage.pipeline_id != pipeline.id:
            raise serializers.ValidationError(
                {'stage': f'"{stage}" does not belong to pipeline "{pipeline}".'}
            )
        return attrs

class DealStageChangeSerializer(serializers.Serializer):
    """Used only by the custom stage-change action below — a Deal's normal
    update should not silently move its stage without writing history."""
    stage = serializers.PrimaryKeyRelatedField(queryset=DealStage.objects.all())


class DealStageHistorySerializer(serializers.ModelSerializer):
    from_stage_name = serializers.CharField(source='from_stage.dealstagename.name', read_only=True, default=None)
    to_stage_name = serializers.CharField(source='to_stage.dealstagename.name', read_only=True)
    to_stage_is_won = serializers.BooleanField(source='to_stage.is_won', read_only=True)
    to_stage_is_lost = serializers.BooleanField(source='to_stage.is_lost', read_only=True)
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = DealStageHistory
        fields = ['id', 'deal', 'from_stage', 'from_stage_name', 'to_stage', 'to_stage_name',
                  'to_stage_is_won', 'to_stage_is_lost',
                  'changed_by', 'changed_by_name', 'changed_at']
        read_only_fields = fields


class LeadSerializer(OwnerSerializerMixin, serializers.ModelSerializer):
    name = serializers.ReadOnlyField()

    class Meta:
        model = Lead
        fields = [
            'id', 'zoho_record_id', 'first_name', 'last_name', 'name', 'company', 'title',
            'email', 'phone', 'mobile', 'street', 'city', 'state', 'country', 'zip_code',
            'lead_source', 'lead_status', 'industry', 'annual_revenue', 'description',
            'im_query_type', 'im_query_id', 'im_enquiry_time', 'im_product',
            'is_converted', 'converted_account', 'converted_contact', 'converted_deal', 'converted_at',
            'owner', 'owner_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['zoho_record_id', 'is_converted', 'converted_account',
                            'converted_contact', 'converted_deal', 'converted_at',
                            'created_at', 'updated_at']


class CrmUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class NoteSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)
    can_modify = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = ['id', 'content', 'lead', 'contact', 'account', 'deal',
                  'created_by', 'created_by_name', 'can_modify', 'created_at']
        read_only_fields = ['created_by', 'created_at']

    def get_can_modify(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        return obj.created_by_id == request.user.id or request.user.is_staff


class DealAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True, default=None)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = DealAttachment
        fields = ['id', 'deal', 'file', 'file_url', 'original_filename',
                  'uploaded_by', 'uploaded_by_name', 'uploaded_at']
        read_only_fields = ['uploaded_by', 'uploaded_at']
        extra_kwargs = {'file': {'write_only': True}}

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

class DealTaskSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True, default=None)
    deal_name = serializers.CharField(source='deal.name', read_only=True, default=None)

    class Meta:
        model = DealTask
        fields = [
            'id', 'deal', 'deal_name', 'subject', 'due_date', 'priority',
            'owner', 'owner_name', 'is_closed',
            'reminder_enabled', 'reminder_at', 'reminder_dismissed',
            'created_by', 'created_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'reminder_dismissed']