from django import template
from django.utils.safestring import mark_safe

from meetings.richtext import plain_text, rich_html

register = template.Library()


@register.filter
def rich_description(value):
    """A task description as safe HTML (cleaned again here, so even a row saved by other means cannot inject
    anything); text from before the editor existed keeps its line breaks."""
    return mark_safe(rich_html(value))


@register.filter
def description_text(value):
    """The description as one line of plain text, for lists."""
    return ' '.join(plain_text(rich_html(value)).split())
