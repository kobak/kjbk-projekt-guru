import re
from datetime import date, time
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from .models import Project, Task, ChecklistItem, Notification, Activity
from .notifications import preference_channels, email_configured

class Problem(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

def person(u):
    return {"id": u.id, "name": u.first_name or u.username, "email": u.email,
        "admin": u.is_staff, "active": u.is_active}

def project_json(p):
    return {"id": str(p.id), "name": p.name, "description": p.description, "color": p.color, "archived": p.archived}

def task_json(t, user, detail=False):
    links = [l for l in t.calendar_links.all() if l.user_id == user.id]
    link = links[0] if links else None
    data = {"id": str(t.id), "project_id": str(t.project_id), "title": t.title, "description": t.description,
        "status": t.status, "priority": t.priority, "assignee_id": t.assignee_id, "created_by_id": t.created_by_id,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "due_time": t.due_time.strftime("%H:%M") if t.due_time else None, "labels": t.labels,
        "position": t.position, "version": t.version, "updated_at": t.updated_at.isoformat(),
        "checklist": [{"id": x.id, "text": x.text, "done": x.done} for x in t.checklist.all()],
        "comment_count": t.comments.count(), "attachment_count": t.attachments.count(),
        "calendar": {"enabled": link.enabled, "url": link.event_url, "error": link.error,
            "pending": link.synced_version != t.version} if link else None}
    if detail:
        if t.due_date:
            from .calendar import template_url
            data["calendar_manual_url"] = template_url(t)
            data["calendar_ics_url"] = f"/api/tasks/{t.id}/calendar.ics"
        data["comments"] = [{"id": c.id, "user": person(c.user), "body": c.body, "created_at": c.created_at.isoformat()} for c in t.comments.select_related("user")]
        data["attachments"] = [{"id": a.id, "name": a.name, "size": a.size, "url": f"/api/attachments/{a.id}/download/"} for a in t.attachments.all()]
    return data

def task_queryset():
    return Task.objects.filter(deleted=False).select_related("project", "assignee").prefetch_related("checklist", "comments", "attachments", "calendar_links")

def text(data, key, maximum, required=False):
    value = data.get(key, "")
    if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
        raise Problem(f"Hibás vagy hiányzó mező: {key} (legfeljebb {maximum} karakter).")
    return value.strip()

def password_text(data, key="password"):
    value = data.get(key)
    if not isinstance(value, str) or not 1 <= len(value) <= 1024:
        raise Problem("Adj meg egy érvényes jelszót.")
    return value

def notify(user_id, task, title, body="", key=None, *, kind=Notification.Kind.LEGACY):
    if not user_id:
        return
    email_events, push_events = preference_channels(user_id)
    values = {"user_id": user_id, "task": task, "title": title[:250], "body": body[:500], "kind": kind,
        "push_pending": kind in push_events, "email_pending": email_configured() and kind in email_events}
    if key:
        Notification.objects.get_or_create(dedupe_key=key, defaults=values)
    else:
        Notification.objects.create(**values)

def activity(user, task, message):
    Activity.objects.create(user=user, task=task, text=message[:300])

@transaction.atomic
def save_project(data, user, project=None):
    p = project or Project()
    if "name" in data or not project:
        p.name = text(data, "name", 120, True)
    if "description" in data:
        p.description = text(data, "description", 5000)
    if "color" in data:
        if not isinstance(data["color"], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", data["color"]):
            raise Problem("Érvénytelen projektszín.")
        p.color = data["color"]
    if "archived" in data:
        if not isinstance(data["archived"], bool):
            raise Problem("Érvénytelen archiválás.")
        p.archived = data["archived"]
    p.save()
    return p

@transaction.atomic
def save_task(data, user, task_id=None):
    if not isinstance(data, dict):
        raise Problem("A kérésnek objektumnak kell lennie.")
    if task_id:
        try:
            t = Task.objects.select_for_update().get(id=task_id, deleted=False)
        except Task.DoesNotExist:
            raise Problem("A feladat nem található.", 404)
        if data.get("version") != t.version:
            raise Problem("Ezt a feladatot közben valaki módosította. Frissítsd, majd próbáld újra.", 409)
    else:
        t = Task(created_by=user)
    old_assignee = t.assignee_id
    if "title" in data or not task_id:
        t.title = text(data, "title", 250, True)
    if "description" in data:
        t.description = text(data, "description", 20000)
    if "project_id" in data or not task_id:
        try:
            t.project = Project.objects.get(id=data.get("project_id"), archived=False)
        except (Project.DoesNotExist, ValueError, TypeError):
            raise Problem("Válassz egy aktív projektet.")
    elif t.project.archived:
        raise Problem("Az archivált projekt feladatai csak olvashatók.")
    for field, choices in [("status", Task.Status.values), ("priority", Task.Priority.values)]:
        if field in data:
            if data[field] not in choices:
                raise Problem(f"Érvénytelen {field}.")
            setattr(t, field, data[field])
    if "assignee_id" in data:
        value = data["assignee_id"]
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not User.objects.filter(id=value, is_active=True).exists()):
            raise Problem("A felelős nem található.")
        t.assignee_id = value
    for field, parser in [("due_date", date.fromisoformat), ("due_time", time.fromisoformat)]:
        if field in data:
            try:
                value = parser(data[field]) if data[field] else None
                if field == "due_time" and value and (value.tzinfo or value.second or value.microsecond):
                    raise ValueError()
                setattr(t, field, value)
            except (ValueError, TypeError):
                raise Problem("Hibás határidő. Dátum: ÉÉÉÉ-HH-NN, idő: ÓÓ:PP.")
    if t.due_time and not t.due_date:
        raise Problem("Az időpont mellé dátumot is adj meg.")
    if "labels" in data:
        labels = data["labels"]
        if not isinstance(labels, list) or len(labels) > 8 or any(not isinstance(x, str) or not 1 <= len(x.strip()) <= 30 for x in labels):
            raise Problem("Legfeljebb 8, egyenként 30 karakteres címke adható meg.")
        t.labels = list(dict.fromkeys(x.strip() for x in labels))
    if "position" in data:
        if type(data["position"]) is not int or not 0 <= data["position"] <= 1000000:
            raise Problem("Hibás sorrend.")
        t.position = data["position"]
    if task_id:
        t.version += 1
    t.save()
    if t.assignee_id and t.assignee_id != user.id and t.assignee_id != old_assignee:
        notify(t.assignee_id, t, "Új feladatot kaptál", t.title, kind=Notification.Kind.TASK_ASSIGNED)
    if task_id and old_assignee and old_assignee != user.id and old_assignee == t.assignee_id:
        notify(old_assignee, t, "Változott a feladatod", t.title, kind=Notification.Kind.TASK_UPDATED)
    activity(user, t, "módosította a feladatot" if task_id else "létrehozta a feladatot")
    return t

@transaction.atomic
def delete_task(task_id, version, user):
    t = Task.objects.select_for_update().get(id=task_id, deleted=False)
    if t.project.archived:
        raise Problem("Az archivált projekt feladatai csak olvashatók.")
    if version != t.version:
        raise Problem("A feladat közben módosult. Frissítsd a nézetet.", 409)
    t.deleted = True
    t.version += 1
    t.save()
    t.calendar_links.update(enabled=False, attempted_at=None)
    activity(user, t, "törölte a feladatot")
