from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0009_private_tasks")]

    operations = [
        migrations.AddField(
            model_name="googleconnection",
            name="google_subject",
            field=models.CharField(blank=True, db_default="", max_length=255),
        ),
    ]
