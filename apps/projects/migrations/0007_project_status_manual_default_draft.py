from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0006_project_status_in_progress"),
    ]

    operations = [
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
                default="draft",
                max_length=20,
            ),
        ),
    ]
