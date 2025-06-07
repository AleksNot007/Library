from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Умножает value на arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return '' 