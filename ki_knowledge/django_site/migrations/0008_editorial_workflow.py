"""Enable Wagtail moderation workflow for SourceDocument and GeneratedDocument.

Creates one shared "Redaktionelle Freigabe" workflow with a single
GroupApprovalTask (approved by an "Editors" group), and assigns it to both
snippet content types via WorkflowContentType. This is additive to the
existing review_status field (see infosite_models.py) - editors can either
just set review_status directly, or use "Submit for moderation" in the
Wagtail snippet editor to run a real Wagtail workflow (draft -> in review ->
approved/rejected) with audit trail, alongside the plain status field.
"""

from django.db import migrations


def create_workflow(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Workflow = apps.get_model("wagtailcore", "Workflow")
    WorkflowTask = apps.get_model("wagtailcore", "WorkflowTask")
    WorkflowContentType = apps.get_model("wagtailcore", "WorkflowContentType")
    GroupApprovalTask = apps.get_model("wagtailcore", "GroupApprovalTask")

    editors_group, _ = Group.objects.get_or_create(name="Editors")

    task_content_type, _ = ContentType.objects.get_or_create(
        app_label="wagtailcore", model="groupapprovaltask"
    )
    task, created = GroupApprovalTask.objects.get_or_create(
        name="Redaktionelle Freigabe",
        defaults={"content_type": task_content_type},
    )
    task.groups.add(editors_group)

    workflow, _ = Workflow.objects.get_or_create(name="Redaktionelle Freigabe")
    WorkflowTask.objects.get_or_create(workflow=workflow, task_id=task.id, defaults={"sort_order": 0})

    for app_label, model in (
        ("django_site", "sourcedocument"),
        ("django_site", "generateddocument"),
    ):
        content_type, _ = ContentType.objects.get_or_create(app_label=app_label, model=model)
        WorkflowContentType.objects.get_or_create(
            content_type=content_type, defaults={"workflow": workflow}
        )


def remove_workflow(apps, schema_editor):
    Workflow = apps.get_model("wagtailcore", "Workflow")
    Workflow.objects.filter(name="Redaktionelle Freigabe").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("django_site", "0007_backfill_domain_registry"),
        ("wagtailcore", "0098_apitoken"),
    ]

    operations = [
        migrations.RunPython(create_workflow, remove_workflow),
    ]
