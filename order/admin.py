from django.contrib import admin
from .models import Order, Job, JobMaterial, JobProcess, JobColor, JobImage


# ── Inlines ───────────────────────────────────────────────────────────────────

class JobTabularInline(admin.TabularInline):
    model = Job
    extra = 1


class JobImageInline(admin.TabularInline):
    model = JobImage
    extra = 1


class JobProcessInline(admin.TabularInline):
    model = JobProcess
    extra = 1


class JobMaterialInline(admin.TabularInline):
    model = JobMaterial
    extra = 1


class JobColorInline(admin.TabularInline):
    model = JobColor
    extra = 1


# ── ModelAdmins ───────────────────────────────────────────────────────────────

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [JobTabularInline]


@admin.register(JobProcess)
class JobProcessAdmin(admin.ModelAdmin):
    list_display = ['process']
    ordering = ['process']


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('id', 'itemmaster', 'jobstatus', 'kgqty', 'created')
    list_editable = ('jobstatus',)
    ordering = ['itemmaster', 'created']
    list_filter = ('jobstatus', 'created')
    search_fields = ('itemmaster__name',)  # adjust field to your model
    inlines = [JobImageInline, JobMaterialInline, JobProcessInline, JobColorInline]
    actions = ['remove_account_approval']

    def remove_account_approval(self, request, queryset):
        updated = queryset.update(account_clearance_date=None, approvedby=None, jobstatus='Account clearance')
        self.message_user(request, f'{updated} job(s) account approval removed.')
    remove_account_approval.short_description = 'Remove account approval'


@admin.register(JobMaterial)
class JobMaterialAdmin(admin.ModelAdmin):
    pass


@admin.register(JobImage)
class JobImageAdmin(admin.ModelAdmin):
    pass


@admin.register(JobColor)
class JobColorAdmin(admin.ModelAdmin):
    pass