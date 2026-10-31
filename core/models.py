import uuid
import hashlib
from django.conf import settings
from django.db import models

NOTIFICATION_EVENTS = ("task_assigned", "task_updated", "comment", "mention", "due", "overdue")

def default_email_events():
    return ["task_assigned", "mention"]

def default_push_events():
    return list(NOTIFICATION_EVENTS)

class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences")
    email_events = models.JSONField(default=default_email_events)
    push_events = models.JSONField(default=default_push_events)
    updated_at = models.DateTimeField(auto_now=True)

class AppearancePreference(models.Model):
    class Theme(models.TextChoices):
        SYSTEM = "system", "Rendszer szerint"
        LIGHT = "light", "Világos"
        DARK = "dark", "Sötét"
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appearance_preference")
    theme = models.CharField(max_length=10, choices=Theme.choices, default=Theme.SYSTEM)
    default_view = models.CharField(max_length=10, choices=[("list", "Lista"), ("board", "Kanban")], default="list")
    show_completed = models.BooleanField(default=False)
    list_sort = models.CharField(max_length=10, choices=[("due", "Határidő"), ("priority", "Prioritás"), ("created", "Létrehozás"), ("manual", "Kézi sorrend")], default="due")
    font_size = models.CharField(max_length=10, choices=[("normal", "Normál"), ("large", "Nagy")], default="normal")
    density = models.CharField(max_length=10, choices=[("compact", "Kompakt"), ("spacious", "Tágas")], default="compact")
    updated_at = models.DateTimeField(auto_now=True)

class PersonalListOrder(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="personal_list_order")
    task_ids = models.JSONField(default=list)
    version = models.PositiveIntegerField(default=0)

class Workspace(models.Model):
    name = models.CharField(max_length=100, default="Közös munkatér")

class RateLimit(models.Model):
    key = models.CharField(max_length=250, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField()

class Invite(models.Model):
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#557c69")
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "Teendő"
        DOING = "doing", "Folyamatban"
        REVIEW = "review", "Ellenőrzés"
        DONE = "done", "Kész"
    class Priority(models.TextChoices):
        LOW = "low", "Alacsony"
        NORMAL = "normal", "Normál"
        HIGH = "high", "Magas"
        URGENT = "urgent", "Sürgős"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="tasks")
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_tasks")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_tasks")
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True)
    labels = models.JSONField(default=list, blank=True)
    position = models.IntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=["deleted", "due_date"]), models.Index(fields=["project", "status"])]

class ChecklistItem(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="checklist")
    text = models.CharField(max_length=250)
    done = models.BooleanField(default=False)
    class Meta:
        ordering = ["id"]

class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    mentions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["created_at"]

def attachment_path(instance, filename):
    return f"attachments/{instance.task_id}/{uuid.uuid4().hex}"

class Attachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    file = models.FileField(upload_to=attachment_path)
    name = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    class Kind(models.TextChoices):
        LEGACY = "legacy", "Korábbi értesítés"
        TASK_ASSIGNED = "task_assigned", "Új feladat kiosztása"
        TASK_UPDATED = "task_updated", "Feladatom módosítása"
        COMMENT = "comment", "Hozzászólás"
        MENTION = "mention", "Megemlítés hozzászólásban"
        DUE = "due", "Közelgő határidő"
        OVERDUE = "overdue", "Lejárt határidő"
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, null=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=250)
    body = models.CharField(max_length=500, blank=True)
    read = models.BooleanField(default=False)
    dedupe_key = models.CharField(max_length=250, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.LEGACY)
    push_pending = models.BooleanField(default=True)
    push_attempts = models.PositiveSmallIntegerField(default=0)
    push_sent_at = models.DateTimeField(null=True, blank=True)
    email_pending = models.BooleanField(default=False)
    email_attempts = models.PositiveSmallIntegerField(default=0)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_next_attempt_at = models.DateTimeField(null=True, blank=True)
    email_error = models.CharField(max_length=120, blank=True)
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email_pending", "email_next_attempt_at"])]

class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    endpoint = models.URLField(max_length=2000)
    endpoint_hash = models.CharField(max_length=64, unique=True)
    keys = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        self.endpoint_hash = hashlib.sha256(self.endpoint.encode()).hexdigest()
        if kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"endpoint_hash"}
        super().save(*args, **kwargs)

class GoogleConnection(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    encrypted_refresh_token = models.TextField()
    connected_at = models.DateTimeField(auto_now_add=True)
    error = models.CharField(max_length=250, blank=True)

class CalendarLink(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="calendar_links")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event_id = models.CharField(max_length=100, default="")
    event_url = models.URLField(max_length=2000, blank=True)
    enabled = models.BooleanField(default=True)
    synced_version = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=250, blank=True)
    attempted_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "user"], name="one_calendar_event_per_user_task")]

class Activity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    task = models.ForeignKey(Task, null=True, on_delete=models.SET_NULL)
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]
