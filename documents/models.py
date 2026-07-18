from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class Document(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='documents/%Y/%m/')
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='uploaded_documents'
    )
    viewers = models.ManyToManyField(
        User, blank=True, related_name='viewable_documents'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def has_access(self, user):
        """Creator and assigned viewers can access. Superusers too, if you want that."""
        if user.is_superuser:
            return True
        return self.uploaded_by_id == user.id or self.viewers.filter(pk=user.pk).exists()

    def get_absolute_url(self):
        return reverse('documents:detail', args=[self.pk])


class DocumentDownloadLog(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='download_logs'
    )
    downloaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    downloaded_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-downloaded_at']

    def __str__(self):
        return f"{self.downloaded_by} downloaded {self.document} at {self.downloaded_at}"
