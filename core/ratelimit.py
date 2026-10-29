from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import RateLimit

@transaction.atomic
def allow(key, limit, seconds):
    item, _ = RateLimit.objects.select_for_update().get_or_create(key=key[:250], defaults={"started_at": timezone.now()})
    if item.started_at + timedelta(seconds=seconds) < timezone.now():
        item.count, item.started_at = 0, timezone.now()
    item.count += 1
    item.save()
    return item.count <= limit
