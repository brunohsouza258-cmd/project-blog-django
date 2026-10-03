from django import template
from django.utils import timezone
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def tempo_atras(value):
    """
    "agora", "há 3 minutos", "há 2 horas", "há 3 dias"...
    Só a maior unidade (depth=1): "há 2 horas", e não "há 2 horas, 5 minutos".
    """
    if not value:
        return ''
    if (timezone.now() - value).total_seconds() < 60:
        return 'agora'
    return f'há {timesince(value, depth=1)}'
