import json
import smtplib
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import Notification, NotificationPreference, Project, Task, PushSubscription, NOTIFICATION_EVENTS
from .notifications import save_preferences
from .services import notify, save_task
from .worker import tick


@override_settings(
    SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost"], AXES_ENABLED=False,
    NOTIFICATION_EMAIL_ENABLED=True, EMAIL_HOST="smtp.example.com",
    DEFAULT_FROM_EMAIL="kjbk projekt guru <guru@example.com>",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    VAPID_PRIVATE_KEY="fake-test-vapid-key", VAPID_SUBJECT="mailto:admin@example.com",
)
class NotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner@example.com", email="owner@example.com", first_name="Gazda")
        self.member = User.objects.create_user(username="member@example.com", email="member@example.com", first_name="Tag")
        self.project = Project.objects.create(name="Közös projekt")
        self.task = Task.objects.create(project=self.project, title="Értesítési próba", created_by=self.owner, assignee=self.member)
        self.client.force_login(self.member, backend="django.contrib.auth.backends.ModelBackend")
        push_patcher = patch("core.worker.webpush")
        self.push = push_patcher.start()
        self.addCleanup(push_patcher.stop)

    def emit(self, kind=Notification.Kind.TASK_ASSIGNED, task=None, key=None):
        task = task or self.task
        notify(task.assignee_id, task, "Új feladatot kaptál", task.title, key, kind=kind)
        return Notification.objects.latest("id")

    def preferences(self, value):
        return self.client.patch("/api/notification-preferences/", json.dumps(value), content_type="application/json")

    def subscription(self):
        return PushSubscription.objects.create(user=self.member, endpoint="https://fcm.googleapis.com/test-only",
            keys={"p256dh": "test-public-key", "auth": "test-auth-key"})

    def test_default_preferences_are_personal_and_match_agreed_channels(self):
        response = self.client.get("/api/notification-preferences/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], self.member.email)
        self.assertTrue(data["email_configured"])
        self.assertEqual(set(data["preferences"]), set(NOTIFICATION_EVENTS))
        for key, channels in data["preferences"].items():
            self.assertEqual(channels, {"email": key == "task_assigned", "push": True})

    def test_preferences_require_login_and_csrf(self):
        self.assertEqual(Client().get("/api/notification-preferences/").status_code, 401)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.member)
        response = client.patch("/api/notification-preferences/", json.dumps({"preferences": {"comment": {"email": True}}}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_only_own_preferences_change_and_partial_update_preserves_others(self):
        response = self.preferences({"preferences": {"comment": {"email": True}, "task_assigned": {"push": False}}})
        self.assertEqual(response.status_code, 200)
        prefs = response.json()["preferences"]
        self.assertTrue(prefs["comment"]["email"])
        self.assertTrue(prefs["task_assigned"]["email"])
        self.assertFalse(prefs["task_assigned"]["push"])
        self.client.force_login(self.owner)
        owner = self.client.get("/api/notification-preferences/").json()["preferences"]
        self.assertFalse(owner["comment"]["email"])
        self.assertTrue(owner["task_assigned"]["push"])

    def test_invalid_and_cross_user_payloads_cannot_partially_change_preferences(self):
        for payload in [
            {"user_id": self.owner.id, "preferences": {"comment": {"email": True}}},
            {"preferences": {"unknown": {"email": True}}},
            {"preferences": {"comment": {"email": "true"}}},
            {"preferences": {"comment": {"email": 1}}},
            {"preferences": {"comment": {"sms": True}}},
            {"preferences": {"task_assigned": {"email": False}, "comment": None}},
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(self.preferences(payload).status_code, 400)
        self.assertFalse(NotificationPreference.objects.exists())

    def test_assignment_from_another_user_queues_and_sends_one_email(self):
        created = save_task({"project_id": str(self.project.id), "title": "Kiosztott feladat", "assignee_id": self.member.id}, self.owner)
        notification = Notification.objects.get(task=created)
        self.assertEqual(notification.kind, "task_assigned")
        self.assertTrue(notification.email_pending)
        tick(); tick()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.member.email])
        self.assertIn(f"{settings.APP_URL}/?task={created.id}", mail.outbox[0].body)
        self.assertIn("?settings=notifications", mail.outbox[0].body)
        notification.refresh_from_db()
        self.assertFalse(notification.email_pending)
        self.assertIsNotNone(notification.email_sent_at)

    def test_own_assignment_does_not_notify(self):
        save_task({"project_id": str(self.project.id), "title": "Saját", "assignee_id": self.owner.id}, self.owner)
        tick()
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_all_channels_off_keeps_in_app_notification(self):
        NotificationPreference.objects.create(user=self.member, email_events=[], push_events=[])
        self.subscription()
        self.emit()
        tick()
        self.assertEqual(Notification.objects.filter(user=self.member).count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        self.push.assert_not_called()

    def test_email_and_push_can_be_selected_independently(self):
        preference = NotificationPreference.objects.create(user=self.member, email_events=[], push_events=["task_assigned"])
        self.subscription()
        self.emit(); tick()
        self.assertEqual(len(mail.outbox), 0)
        self.push.assert_called_once()
        self.push.reset_mock()
        preference.email_events, preference.push_events = ["task_assigned"], []
        preference.save()
        self.emit(); tick()
        self.assertEqual(len(mail.outbox), 1)
        self.push.assert_not_called()

    def test_all_five_types_can_send_email_when_selected(self):
        NotificationPreference.objects.create(user=self.member, email_events=list(NOTIFICATION_EVENTS), push_events=[])
        for key in NOTIFICATION_EVENTS:
            self.emit(key)
        tick(); tick()
        self.assertEqual(len(mail.outbox), 5)

    def test_only_assignments_send_email_by_default(self):
        for key in NOTIFICATION_EVENTS:
            self.emit(key)
        tick()
        self.assertEqual(len(mail.outbox), 1)

    def test_disabling_a_queued_channel_prevents_delivery(self):
        self.subscription()
        notification = self.emit()
        save_preferences(self.member, {"preferences": {"task_assigned": {"email": False, "push": False}}})
        tick()
        self.assertEqual(len(mail.outbox), 0)
        self.push.assert_not_called()
        notification.refresh_from_db()
        self.assertFalse(notification.email_pending)
        self.assertFalse(notification.push_pending)

    def test_enabling_a_channel_does_not_replay_older_notifications(self):
        preference = NotificationPreference.objects.create(user=self.member, email_events=[], push_events=[])
        self.emit()
        preference.email_events = ["task_assigned"]
        preference.save()
        tick()
        self.assertEqual(len(mail.outbox), 0)

    def test_not_configured_email_does_not_build_a_future_backlog(self):
        with override_settings(NOTIFICATION_EMAIL_ENABLED=False):
            self.emit()
        tick()
        self.assertEqual(len(mail.outbox), 0)

    def test_legacy_notifications_are_not_emailed(self):
        Notification.objects.create(user=self.member, task=self.task, title="Korábbi értesítés", body=self.task.title)
        tick()
        self.assertEqual(len(mail.outbox), 0)

    def test_inactive_reassigned_deleted_archived_and_completed_reminders_are_skipped(self):
        notification = self.emit()
        self.task.assignee = self.owner
        self.task.save()
        tick()
        self.assertEqual(len(mail.outbox), 0)
        self.task.assignee = self.member
        self.task.deleted = True
        self.task.save()
        self.emit(); tick()
        self.task.deleted = False
        self.task.save()
        self.project.archived = True
        self.project.save()
        self.emit(); tick()
        self.project.archived = False
        self.project.save()
        self.member.is_active = False
        self.member.save()
        self.emit(); tick()
        self.assertEqual(len(mail.outbox), 0)
        self.member.is_active = True
        self.member.save()
        Notification.objects.update(email_pending=False)
        NotificationPreference.objects.create(user=self.member, email_events=["due"], push_events=[])
        self.task.status = "done"
        self.task.save()
        self.emit("due"); tick()
        self.assertEqual(len(mail.outbox), 0)

    def test_email_older_than_a_day_is_not_sent(self):
        notification = self.emit()
        Notification.objects.filter(id=notification.id).update(created_at=timezone.now()-timedelta(days=2))
        tick()
        self.assertEqual(len(mail.outbox), 0)

    def test_rescheduled_deadline_cancels_already_queued_reminder(self):
        NotificationPreference.objects.create(user=self.member, email_events=["due"], push_events=[])
        self.task.due_date = timezone.localdate()+timedelta(days=1)
        self.task.save()
        notification = self.emit("due", key=f"due:{self.task.id}:{self.member.id}:{self.task.due_date}:{self.task.due_time}")
        self.task.due_date += timedelta(days=7)
        self.task.save()
        tick()
        self.assertEqual(len(mail.outbox), 0)
        notification.refresh_from_db()
        self.assertFalse(notification.email_pending)

    def test_email_html_escapes_user_text_and_subject_cannot_inject_headers(self):
        self.task.title = '<script>alert("test")</script>'
        self.task.save()
        notify(self.member.id, self.task, "Új feladat\r\nX-Injected: false", self.task.title, kind=Notification.Kind.TASK_ASSIGNED)
        tick()
        message = mail.outbox[0]
        self.assertNotIn("\r", message.subject)
        self.assertNotIn("\n", message.subject)
        self.assertIn("&lt;script&gt;", message.alternatives[0].content)
        self.assertNotIn("<script>", message.alternatives[0].content)
        self.assertIn(self.task.title, message.body)

    def test_duplicate_reminder_key_does_not_duplicate_delivery(self):
        self.emit(key="one-event")
        self.emit(key="one-event")
        tick(); tick()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    @patch("core.worker.notification_email")
    def test_smtp_failure_retries_later_and_eventually_completes(self, make):
        notification = self.emit()
        make.return_value.send.side_effect = smtplib.SMTPException("fake transient failure")
        with self.assertLogs("core.worker", level="WARNING"):
            tick()
        tick()
        self.assertEqual(make.return_value.send.call_count, 1)
        notification.refresh_from_db()
        self.assertEqual(notification.email_attempts, 1)
        self.assertTrue(notification.email_pending)
        notification.email_next_attempt_at = timezone.now()-timedelta(seconds=1)
        notification.save()
        make.return_value.send.side_effect = None
        make.return_value.send.return_value = 1
        tick(); tick()
        notification.refresh_from_db()
        self.assertIsNotNone(notification.email_sent_at)
        self.assertEqual(notification.email_error, "")
        self.assertEqual(make.return_value.send.call_count, 2)

    @patch("core.worker.notification_email")
    def test_smtp_failures_stop_after_four_attempts(self, make):
        notification = self.emit()
        make.return_value.send.side_effect = smtplib.SMTPException("fake failure")
        for _ in range(4):
            Notification.objects.filter(id=notification.id).update(email_next_attempt_at=None)
            with self.assertLogs("core.worker", level="WARNING"):
                tick()
        tick()
        notification.refresh_from_db()
        self.assertEqual(make.return_value.send.call_count, 4)
        self.assertFalse(notification.email_pending)
        self.assertIsNone(notification.email_sent_at)

    def test_push_failure_does_not_prevent_email(self):
        self.subscription()
        self.push.side_effect = RuntimeError("fake push failure")
        self.emit()
        with self.assertLogs("core.worker", level="WARNING"):
            tick()
        self.assertEqual(len(mail.outbox), 1)

    def test_comments_use_comment_preferences(self):
        NotificationPreference.objects.create(user=self.member, email_events=["comment"], push_events=[])
        self.client.force_login(self.owner)
        response = self.client.post(f"/api/tasks/{self.task.id}/comments/", json.dumps({"body": "Megjegyzés"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Notification.objects.get().kind, "comment")
        tick()
        self.assertEqual(len(mail.outbox), 1)
