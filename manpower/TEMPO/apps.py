from django.apps import AppConfig


class ManpowerConfig(AppConfig):
    name = 'manpower'

    def ready(self):
        import manpower.signals
