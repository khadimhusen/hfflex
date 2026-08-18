from django.contrib import admin
from .models import Pipeline, DealStageName, DealStage, DealStageHistory, Account, Contact, Deal, Note, DealAttachment


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(DealStageName)
class DealStageNameAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(DealStage)
class DealStageAdmin(admin.ModelAdmin):
    list_display = ('pipeline', 'dealstagename', 'order','max_stall_time' ,'probability', 'is_won', 'is_lost', 'color')
    list_editable= ( 'order', 'probability', 'max_stall_time' ,'color')

    list_filter = ('pipeline', 'is_won', 'is_lost')
    ordering = ('pipeline', 'order')


class DealStageHistoryInline(admin.TabularInline):
    model = DealStageHistory
    fk_name = 'deal'
    extra = 0
    readonly_fields = ('from_stage', 'to_stage', 'changed_by', 'changed_at')
    can_delete = False
    ordering = ('-changed_at',)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'billing_city', 'billing_state', 'industry', 'owner')
    list_filter = ('billing_state', 'industry', 'owner')
    search_fields = ('name', 'phone', 'account_number', 'billing_city')
    autocomplete_fields = ('owner',)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'account', 'title', 'phone', 'email', 'owner')
    list_filter = ('mailing_state', 'lead_source', 'owner')
    search_fields = ('first_name', 'last_name', 'phone', 'email', 'account__name')
    autocomplete_fields = ('account', 'owner')


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'pipeline', 'stage', 'account', 'contact',
        'amount', 'expected_revenue_display', 'closing_date', 'owner',
    )

    list_filter = ('pipeline', 'stage', 'deal_type', 'owner')
    search_fields = ('name', 'account__name', 'contact__first_name', 'contact__last_name')
    autocomplete_fields = ('account', 'contact', 'owner')
    inlines = [DealStageHistoryInline]

    def expected_revenue_display(self, obj):
        return obj.expected_revenue

    expected_revenue_display.short_description = 'Expected Revenue'


@admin.register(DealStageHistory)
class DealStageHistoryAdmin(admin.ModelAdmin):
    list_display = ('deal', 'from_stage', 'to_stage', 'changed_by', 'changed_at')
    list_filter = ('to_stage', 'changed_by')
    readonly_fields = ('deal', 'from_stage', 'to_stage', 'changed_by', 'changed_at')
    ordering = ('-changed_at',)


from .models import Lead  # add Lead to your existing import line


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'company', 'phone', 'email', 'lead_source',
        'lead_status', 'is_converted', 'owner',
    )
    list_filter = ('lead_source', 'lead_status', 'is_converted', 'owner')
    search_fields = ('first_name', 'last_name', 'company', 'phone', 'email')
    autocomplete_fields = ('owner', 'converted_account', 'converted_contact', 'converted_deal')
    readonly_fields = ('zoho_record_id', 'is_converted', 'converted_account',
                       'converted_contact', 'converted_deal', 'converted_at',
                       'created_at', 'updated_at')


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('content', 'deal', 'lead', 'contact', 'account', 'created_by', 'created_at')
    list_filter = ('created_by',)

@admin.register(DealAttachment)
class DealAttachmentAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'deal', 'uploaded_by', 'uploaded_at')