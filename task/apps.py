from django.apps import AppConfig


# The CKEditor 5 toolbar for task descriptions: only what the cleaner (meetings/richtext.py) keeps.
TASK_EDITOR_CONFIG = {
    'toolbar': {
        'items': ['bold', 'italic', 'underline', 'strikethrough', '|',
                  'bulletedList', 'numberedList', '|', 'link', 'blockQuote', '|', 'undo', 'redo'],
        'shouldNotGroupWhenFull': True,
    },
    'language': 'en',
}


class TaskConfig(AppConfig):
    name = 'task'

    def ready(self):
        import task.signals
        from django.conf import settings
        configs = getattr(settings, 'CKEDITOR_5_CONFIGS', None)
        if configs is not None:
            configs.setdefault('task_description', TASK_EDITOR_CONFIG)