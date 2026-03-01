from django.apps import AppConfig


class ItemmasterConfig(AppConfig):
    name = 'itemmaster'

    def ready(self):
        import itemmaster.signals
