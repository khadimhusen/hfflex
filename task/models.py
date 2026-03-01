from django.db import models
from .choices import PRIORITY
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from PIL import Image
import os


class Task(models.Model):
    taskname = models.CharField(max_length=256)
    description = models.TextField()
    target_date = models.DateTimeField()
    priority = models.CharField(max_length=16, choices=PRIORITY, default="LOW")
    task_alloted_to = models.ForeignKey(User, on_delete=models.PROTECT, related_name="tasks")
    is_closed = models.BooleanField(default=False)
    close_date = models.DateTimeField(null=True, blank=True)
    request_to_close = models.BooleanField(default=False)
    request_date = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='taskcreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='taskedited')

    def __str__(self):
        return self.taskname


class TaskMsg(models.Model):
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name='taskmsg')
    msg_text = models.TextField(null=True, blank=True)
    msg_image = models.ImageField(upload_to='taskmsg/', null=True, blank=True)
    thumbnail = models.ImageField(upload_to='taskmsg_thumbnail/',editable=False ,null=True, blank=True)
    msg_file = models.FileField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='taskmsgcreated')

    def clean(self):

        if self.msg_text is None and self.msg_image is None and self.msg_file is None:
            raise ValidationError('all field should not be null')

    def save(self, *args, **kwargs):
        # Save the original image first
        super().save(*args, **kwargs)

        # Then create the thumbnail
        if self.msg_image:
            self.create_thumbnail()

    def create_thumbnail(self):
        img = Image.open(self.msg_image)

        # Define thumbnail size
        thumbnail_size = (200, 200)

        # Create a thumbnail
        img.thumbnail(thumbnail_size)

        base_filename = os.path.basename(self.msg_image.name)

        # Define the thumbnail path
        thumbnail_name, thumbnail_extension = os.path.splitext(base_filename)
        thumbnail_extension = thumbnail_extension.lower()

        thumbnail_filename = f'{thumbnail_name}_thumbnail{thumbnail_extension}'
        print("thumbnail file name",thumbnail_filename)
        thumbnail_path = os.path.join('taskmsg_thumbnail', thumbnail_filename)

        # Save the thumbnail
        img.save(os.path.join('media', thumbnail_path))

        # Update the thumbnail field
        self.thumbnail.name = thumbnail_path
        super().save()
