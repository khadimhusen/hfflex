from django.contrib import admin

from .models import Candidate, Interview, InterviewFeedback, JobOpening, OpeningCriterion


class CriterionInline(admin.TabularInline):
    model = OpeningCriterion
    extra = 0


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'department', 'positions', 'status', 'opened_date')
    list_filter = ('status',)
    search_fields = ('number', 'title')
    readonly_fields = ('number',)
    inlines = [CriterionInline]


class FeedbackInline(admin.TabularInline):
    model = InterviewFeedback
    extra = 0


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'opening', 'stage', 'mobile', 'current_company')
    list_filter = ('stage', 'source')
    search_fields = ('name', 'mobile', 'email')


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'round_no', 'round_type', 'scheduled_at', 'status')
    list_filter = ('status', 'round_type')
    inlines = [FeedbackInline]
