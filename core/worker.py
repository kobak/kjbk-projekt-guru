import json
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db.models import F, Q
from django.db import transaction
from django.utils import timezone
from pywebpush import webpush, WebPushException
from .models import Task, Notification, PushSubscription, CalendarLink, RateLimit
from .calendar import sync_link
from .services import notify
from .notifications import email_configured, notification_email, notification_is_relevant, preference_channels

logger = logging.getLogger(__name__)

@transaction.atomic
def send_notification_email(notification_id):
    if not email_configured():
        return
    n = Notification.objects.select_for_update().get(id=notification_id)
    now = timezone.now()
    if not n.email_pending or n.email_attempts >= 4 or n.email_sent_at or (n.email_next_attempt_at and n.email_next_attempt_at > now):
        return
    email_events, _ = preference_channels(n.user_id)
    if not n.user.is_active or not n.user.email or n.kind not in email_events or not notification_is_relevant(n):
        n.email_pending = False
        n.save(update_fields=["email_pending"])
        return
    n.email_attempts += 1
    try:
        if notification_email(n).send() != 1:
            raise RuntimeError("Email backend did not accept the notification")
    except Exception as exc:
        # Do not log SMTP credentials, message bodies or recipient addresses.
        n.email_error = type(exc).__name__[:120]
        n.email_pending = n.email_attempts < 4
        n.email_next_attempt_at = now + timedelta(minutes=(1, 5, 30, 60)[n.email_attempts - 1])
        logger.warning("Email delivery failed for notification %s (%s)", n.id, type(exc).__name__)
    else:
        n.email_sent_at = timezone.now()
        n.email_pending = False
        n.email_error = ""
        n.email_next_attempt_at = None
    n.save(update_fields=["email_attempts", "email_pending", "email_sent_at", "email_next_attempt_at", "email_error"])


@transaction.atomic
def send_notification_push(notification_id):
    if not settings.VAPID_PRIVATE_KEY:
        return
    n = Notification.objects.select_for_update().get(id=notification_id)
    if not n.push_pending or n.push_attempts >= 4 or n.push_sent_at:
        return
    _, push_events = preference_channels(n.user_id)
    enabled = n.kind in push_events if n.kind != Notification.Kind.LEGACY else bool(push_events)
    if not n.user.is_active or not enabled or (n.kind != Notification.Kind.LEGACY and not notification_is_relevant(n)):
        n.push_pending = False
        n.save(update_fields=["push_pending"])
        return
    subscriptions = list(PushSubscription.objects.filter(user_id=n.user_id))
    if not subscriptions:
        n.push_pending = False
        n.save(update_fields=["push_pending"])
        return
    n.push_attempts += 1
    failed, sent = False, False
    for sub in subscriptions:
        try:
            webpush(subscription_info={"endpoint": sub.endpoint, "keys": sub.keys},
                data=json.dumps({"title": n.title, "body": n.body, "tag": f"kozos-{n.id}", "url": f"/?task={n.task_id}" if n.task_id else "/"}),
                vapid_private_key=settings.VAPID_PRIVATE_KEY, vapid_claims={"sub": settings.VAPID_SUBJECT}, timeout=10, ttl=3600)
            sent = True
        except WebPushException as exc:
            if exc.response is not None and exc.response.status_code in (404, 410):
                sub.delete()
            else:
                failed = True
                logger.warning("Push delivery failed for notification %s", n.id)
        except Exception as exc:
            failed = True
            logger.warning("Push delivery failed for notification %s (%s)", n.id, type(exc).__name__)
    n.push_pending = failed and n.push_attempts < 4
    if not failed and sent:
        n.push_sent_at = timezone.now()
    n.save(update_fields=["push_pending", "push_attempts", "push_sent_at"])


def tick():
    now = timezone.now()
    local_today = timezone.localdate(now)
    for t in Task.objects.filter(deleted=False, project__archived=False, assignee__is_active=True,
            due_date__range=(local_today - timedelta(days=7), local_today + timedelta(days=1))).exclude(status="done"):
        due = datetime.combine(t.due_date, t.due_time or time(9), ZoneInfo(settings.TIME_ZONE))
        left = (due - now).total_seconds()
        if 0 <= left <= 86400:
            notify(t.assignee_id, t, "Közeleg a határidő", t.title,
                f"due:{t.id}:{t.assignee_id}:{t.due_date}:{t.due_time}", kind=Notification.Kind.DUE)
        elif -86400 <= left < 0:
            notify(t.assignee_id, t, "Lejárt egy feladatod határideje", t.title,
                f"overdue:{t.id}:{t.assignee_id}:{t.due_date}:{t.due_time}", kind=Notification.Kind.OVERDUE)
    retry_before = now - timedelta(minutes=5)
    links = CalendarLink.objects.filter(user__is_active=True).filter(Q(enabled=True) | ~Q(event_id="")).filter(Q(attempted_at=None) | Q(attempted_at__lt=retry_before)).filter(
        ~Q(synced_version=F("task__version")) | ~Q(error="") | Q(enabled=False) & ~Q(event_id=""))
    for link_id in links.values_list("id", flat=True)[:30]:
        sync_link(link_id)
    if email_configured():
        email_ids = list(Notification.objects.filter(email_pending=True, email_sent_at=None, email_attempts__lt=4,
            created_at__gte=now-timedelta(days=1), user__is_active=True).filter(
            Q(email_next_attempt_at=None) | Q(email_next_attempt_at__lte=now)).order_by("created_at").values_list("id", flat=True)[:50])
        for notification_id in email_ids:
            send_notification_email(notification_id)
    if settings.VAPID_PRIVATE_KEY:
        push_ids = list(Notification.objects.filter(push_pending=True, push_sent_at=None, push_attempts__lt=4,
            created_at__gte=now-timedelta(days=1), user__is_active=True).order_by("created_at").values_list("id", flat=True)[:50])
        for notification_id in push_ids:
            send_notification_push(notification_id)
    RateLimit.objects.filter(started_at__lt=now-timedelta(days=2)).delete()
