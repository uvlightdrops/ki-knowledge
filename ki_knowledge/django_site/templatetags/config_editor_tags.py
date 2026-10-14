from django import template

from ki_knowledge.django_site.config_editor import display_value

register = template.Library()


@register.filter
def config_value(value, path):
    """Display a config editor row value; unsafe URL values are never rendered."""
    return display_value(value, path)
