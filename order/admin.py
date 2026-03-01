from django.contrib import admin
from .models import Order, Job, JobMaterial
from .models import JobProcess, JobColor, JobImage


class JobTabular(admin.TabularInline):
    model = Job


class JobMaterilTabular(admin.TabularInline):
    model = JobMaterial


class OrderAdmin(admin.ModelAdmin):
    inlines = [JobTabular]

    class Meta:
        model = Job


class JobprocessAdmin(admin.ModelAdmin):
    list_display = ['process']
    ordering = ['process']


class JobDetail(admin.ModelAdmin):
    list_display = ('id', 'itemmaster', 'jobstatus', 'kgqty', 'created')
    list_editable = ('jobstatus',)
    ordering = ['itemmaster', 'created']
    list_filter = ('jobstatus', 'created')


class JobImageAdmin(admin.TabularInline):
    model = JobImage


class JobProcessinline(admin.TabularInline):
    model = JobProcess

class JobMaterialinline(admin.TabularInline):
    model = JobMaterial

class JobColorinline(admin.TabularInline):
    model = JobColor

class JobDetailAdmin(admin.ModelAdmin):
    inlines = [JobImageAdmin, JobMaterialinline, JobProcessinline, JobColorinline]

    class Meta:
        model = Job


admin.site.register(Order, OrderAdmin)
admin.site.register(Job, JobDetailAdmin)
admin.site.register(JobProcess, JobprocessAdmin)
admin.site.register(JobMaterial)
admin.site.register(JobImage)
admin.site.register(JobColor)

