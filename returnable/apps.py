from django.apps import AppConfig


class ReturnableConfig(AppConfig):
    name = 'returnable'
    def ready(self):
        import returnable.signals
