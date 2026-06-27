from django.contrib import admin
from .models import Task, TaskMsg, Notification

admin.site.register(Task)
admin.site.register(TaskMsg)
admin.site.register(Notification)



