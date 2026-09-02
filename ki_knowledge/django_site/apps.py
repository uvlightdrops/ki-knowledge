from django.apps import AppConfig


class DjangoSiteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ki_knowledge.django_site"
    verbose_name = "KICLI Knowledge Site"
