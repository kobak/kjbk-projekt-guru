from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0010_google_connection_subject")]

    operations = [
        migrations.AddField(
            model_name="pushsubscription",
            name="session_hash",
            field=models.CharField(blank=True, db_default="", db_index=True, max_length=64),
        ),
    ]
