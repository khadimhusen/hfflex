import logging

from django_elasticsearch_dsl.signals import RealTimeSignalProcessor
from elastic_transport import TransportError

logger = logging.getLogger(__name__)


class ResilientSignalProcessor(RealTimeSignalProcessor):
    """Same as the default RealTimeSignalProcessor, except an Elasticsearch
    connectivity failure during the auto-sync-on-save/delete/m2m-change hook
    is logged and swallowed instead of propagating.

    Without this: Document.viewers.set()/.add()/.remove() (and plain
    .save()/.delete()) all run inside their own transaction.atomic() block
    internally. If the m2m_changed/post_save/post_delete signal this
    processor is subscribed to raises -- which it does the moment
    Elasticsearch isn't reachable -- Django rolls back everything in that
    atomic block the instant the exception propagates out of it, even if
    the caller goes on to catch that exception outside. The real database
    write silently never happens, while the request still looks like it
    succeeded. This project doesn't depend on ES for reads (Document
    search uses a plain DB filter -- see documents/api_viewsets.py), so a
    failed sync is safe to ignore rather than let it corrupt real writes.
    """

    def handle_save(self, sender, instance, **kwargs):
        try:
            super().handle_save(sender, instance, **kwargs)
        except TransportError:
            logger.warning('Elasticsearch sync (save) failed for %r -- ignoring.', instance)

    def handle_delete(self, sender, instance, **kwargs):
        try:
            super().handle_delete(sender, instance, **kwargs)
        except TransportError:
            logger.warning('Elasticsearch sync (delete) failed for %r -- ignoring.', instance)

    def handle_pre_delete(self, sender, instance, **kwargs):
        try:
            super().handle_pre_delete(sender, instance, **kwargs)
        except TransportError:
            logger.warning('Elasticsearch sync (pre_delete) failed for %r -- ignoring.', instance)

    def handle_m2m_changed(self, sender, instance, action, **kwargs):
        try:
            super().handle_m2m_changed(sender, instance, action, **kwargs)
        except TransportError:
            logger.warning('Elasticsearch sync (m2m %s) failed for %r -- ignoring.', action, instance)
