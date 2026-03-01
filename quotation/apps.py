from django.apps import AppConfig


class QuotationConfig(AppConfig):
    name = 'quotation'
    def ready(self):
        import quotation.signals
