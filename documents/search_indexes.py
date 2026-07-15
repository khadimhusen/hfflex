from django_elasticsearch_dsl import Document as ESDocument, fields
from django_elasticsearch_dsl.registries import registry
from .models import Document


@registry.register_document
class DocumentIndex(ESDocument):
    uploaded_by_username = fields.TextField(attr='uploaded_by.username')

    class Index:
        name = 'documents'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = Document
        fields = [
            'title',
            'description',
        ]