from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Получает значение из словаря по ключу"""
    return dictionary.get(key, key) 