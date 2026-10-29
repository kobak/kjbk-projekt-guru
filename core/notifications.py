from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.db import transaction
from urllib.parse import urlparse

from .models import NotificationPreference, NOTIFICATION_EVENTS, default_email_events, default_push_events


EVENTS = [
    {"key": "task_assigned", "label": "Új feladatot kaptam", "description": "Valaki rám osztott egy feladatot."},
    {"key": "task_updated", "label": "Változott a feladatom", "description": "Más módosította a hozzám rendelt feladatot."},
    {"key": "comment", "label": "Új hozzászólás", "description": "Hozzászóltak egy engem érintő feladathoz."},
    {"key": "due", "label": "Közeleg a határidő", "description": "A feladatom határideje 24 órán belül van."},
    {"key": "overdue", "label": "Lejárt a határidő", "description": "A feladatom határideje lejárt."},
]


def email_configured():
    return bool(settings.NOTIFICATION_EMAIL_ENABLED and settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL)


def preference_channels(user_id):
    preference = NotificationPreference.objects.filter(user_id=user_id).first()
    if preference:
        return preference.email_events, preference.push_events
    return default_email_events(), default_push_events()


def preference_json(user):
    email_events, push_events = preference_channels(user.id)
    return {
        "events": EVENTS,
        "preferences": {key: {"email": key in email_events, "push": key in push_events} for key in NOTIFICATION_EVENTS},
        "email": user.email,
        "email_configured": email_configured(),
    }


@transaction.atomic
def save_preferences(user, data):
    if set(data) != {"preferences"} or not isinstance(data["preferences"], dict) or not data["preferences"]:
        raise ValidationError("Adj meg érvényes értesítési beállításokat.")
    changes = data["preferences"]
    for key, channels in changes.items():
        if key not in NOTIFICATION_EVENTS or not isinstance(channels, dict) or not channels:
            raise ValidationError("Ismeretlen értesítéstípus.")
        if any(channel not in ("email", "push") or type(value) is not bool for channel, value in channels.items()):
            raise ValidationError("Az értesítési csatornák értéke csak igaz vagy hamis lehet.")
    preference, _ = NotificationPreference.objects.select_for_update().get_or_create(user=user)
    email_events, push_events = set(preference.email_events), set(preference.push_events)
    for key, channels in changes.items():
        for channel, enabled in channels.items():
            selected = email_events if channel == "email" else push_events
            selected.add(key) if enabled else selected.discard(key)
    preference.email_events = [key for key in NOTIFICATION_EVENTS if key in email_events]
    preference.push_events = [key for key in NOTIFICATION_EVENTS if key in push_events]
    preference.save(update_fields=["email_events", "push_events", "updated_at"])


def notification_is_relevant(notification):
    task = notification.task
    if not task:
        return False
    if task.deleted or task.project.archived:
        return False
    if notification.kind in ("task_assigned", "task_updated", "due", "overdue") and task.assignee_id != notification.user_id:
        return False
    if notification.kind in ("due", "overdue") and task.status == "done":
        return False
    if notification.kind in ("due", "overdue") and notification.dedupe_key:
        expected = f"{notification.kind}:{task.id}:{notification.user_id}:{task.due_date}:{task.due_time}"
        if notification.dedupe_key != expected:
            return False
    return True


def notification_email(notification):
    task = notification.task
    context = {
        "name": notification.user.first_name or notification.user.email,
        "title": notification.title,
        "task_title": notification.body,
        "project_name": task.project.name,
        "due_date": task.due_date,
        "due_time": task.due_time,
        "task_url": f"{settings.APP_URL}/?task={task.id}",
        "settings_url": f"{settings.APP_URL}/?settings=notifications",
        "logo_url": f"{settings.APP_URL}/static/brand/kjbk-infinity.png",
    }
    message = EmailMultiAlternatives(
        subject="[GURU] " + " ".join(notification.title.splitlines()),
        body=render_to_string("notifications/email.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[notification.user.email],
        headers={"Message-ID": f"<guru.notification.{notification.id}@{urlparse(settings.APP_URL).hostname}>"},
    )
    message.attach_alternative(render_to_string("notifications/email.html", context), "text/html")
    return message
