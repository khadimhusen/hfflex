from django import template

register = template.Library()

@register.filter
def format_variance(value):
    if value is None:
        return '—'
    total_seconds = int(value.total_seconds())
    sign = '+' if total_seconds >= 0 else '-'
    total_seconds = abs(total_seconds)
    hours   = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{sign}{hours:02d}:{minutes:02d}"

@register.filter
def format_duration(value):
    if value is None:
        return '—'
    total_seconds = int(value.total_seconds())
    if total_seconds == 0:
        return ''
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    parts = []
    if days:
        return f"{days}d, {hours:02d}:{minutes:02d}"

    return f"{hours:02d}:{minutes:02d}"