from django.apps import AppConfig


class WagtailCmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ki_knowledge.wagtail_cms"
    label = "wagtail_cms"
    verbose_name = "CMS Workflow (Wagtail)"
