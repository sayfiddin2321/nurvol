from django.db import migrations, models


def convert_drafts_to_in_progress(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Project.objects.filter(status="draft").update(status="in_progress")


def restore_drafts(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Project.objects.filter(status="in_progress").update(status="draft")


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0005_showcasevideo"),
    ]

    operations = [
        migrations.RunPython(convert_drafts_to_in_progress, restore_drafts),
        migrations.AlterField(
            model_name="project",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Qoralama"),
                    ("in_progress", "Jarayonda"),
                    ("completed", "Tugallangan"),
                    ("archived", "Arxivlangan"),
                ],
                db_index=True,
                default="in_progress",
                max_length=20,
            ),
        ),
    ]
