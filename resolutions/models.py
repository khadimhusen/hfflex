from django.db import models
from django.contrib.auth.models import User
from django_ckeditor_5.fields import CKEditor5Field

def resolution_upload_path(instance, filename):
    return f'resolutions/{instance.resolution.resolution_number}/{filename}'


class Resolution(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    # Core fields
    resolution_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=300)
    content = CKEditor5Field('Resolution Content', config_name='default')

    # Meeting details
    meeting_date = models.DateField()
    meeting_location = models.CharField(max_length=300)
    meeting_type = models.CharField(max_length=100, choices=[
        ('board_meeting', 'Board Meeting'),
        ('agm', 'Annual General Meeting'),
        ('egm', 'Extraordinary General Meeting'),
        ('committee', 'Committee Meeting'),
    ])

    # Meta
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='resolutions_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-meeting_date', '-resolution_number']
        permissions = [
            ('can_publish_resolution', 'Can publish resolution'),
        ]

    def __str__(self):
        return f"{self.resolution_number} - {self.title}"


class ResolutionDocument(models.Model):
    resolution = models.ForeignKey(Resolution, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to=resolution_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.name

    def file_extension(self):
        import os
        return os.path.splitext(self.file.name)[1].lower()


class ResolutionEditor(models.Model):
    """Users who are allowed to create/edit resolutions (besides admins)"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    can_edit = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"