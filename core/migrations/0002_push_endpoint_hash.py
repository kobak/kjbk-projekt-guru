import hashlib
from django.db import migrations, models

def populate_hashes(apps, schema_editor):
    Subscription = apps.get_model("core", "PushSubscription")
    for item in Subscription.objects.all().iterator():
        item.endpoint_hash = hashlib.sha256(item.endpoint.encode()).hexdigest()
        item.save(update_fields=["endpoint_hash"])

class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [
        migrations.AddField(model_name="pushsubscription", name="endpoint_hash", field=models.CharField(max_length=64, unique=True, null=True)),
        migrations.RunPython(populate_hashes, migrations.RunPython.noop),
        migrations.AlterField(model_name="pushsubscription", name="endpoint_hash", field=models.CharField(max_length=64, unique=True)),
        migrations.AlterField(model_name="pushsubscription", name="endpoint", field=models.URLField(max_length=2000)),
    ]
