from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_superuser_admin_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentsettings",
            name="public_phone",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="paymentsettings",
            name="public_telegram_username",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="paymentsettings",
            name="pro_monthly_price",
            field=models.CharField(default="79 000", max_length=32),
        ),
        migrations.AddField(
            model_name="paymentsettings",
            name="team_monthly_price",
            field=models.CharField(default="199 000", max_length=32),
        ),
    ]
