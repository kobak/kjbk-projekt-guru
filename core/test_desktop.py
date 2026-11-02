from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import Notification, NotificationPreference, Project, Task


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], AXES_ENABLED=False)
class DesktopNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="desktop@example.com")
        self.other = User.objects.create_user(username="other@example.com")
        self.project = Project.objects.create(name="Desktop")
        self.task = Task.objects.create(project=self.project, title="Feladat", created_by=self.other, assignee=self.user)
        self.client.force_login(self.user)
        self.url = "/api/desktop/notifications/"

    def notice(self, **kwargs):
        return Notification.objects.create(user=self.user, task=self.task, title="Új feladat",
            kind="task_assigned", **kwargs)

    def test_login_required_and_feed_is_read_only(self):
        self.assertEqual(Client().get(self.url).status_code, 401)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_first_connection_baselines_without_flooding_old_notifications(self):
        n = self.notice()
        response = self.client.get(self.url)
        self.assertEqual(response.json(), {"user_id": self.user.id, "cursor": n.id,
            "has_more": False, "unread": 1, "notifications": []})
        self.assertIn("no-store", response["Cache-Control"])

    def test_cursor_returns_only_own_new_notifications_without_mutation(self):
        old = self.notice()
        other = Notification.objects.create(user=self.other, task=self.task, title="Más fiók", kind="comment")
        new = self.notice()
        response = self.client.get(self.url, {"after": old.id}).json()
        self.assertEqual([n["id"] for n in response["notifications"]], [new.id])
        self.assertNotIn(other.id, [n["id"] for n in response["notifications"]])
        self.assertEqual(response["cursor"], new.id)
        new.refresh_from_db()
        self.assertFalse(new.read)
        self.assertTrue(new.push_pending)

    def test_delivery_respects_push_preferences_without_requiring_vapid(self):
        n = self.notice()
        NotificationPreference.objects.create(user=self.user, email_events=["task_assigned"], push_events=[])
        result = self.client.get(self.url, {"after": 0}).json()
        self.assertEqual(result["notifications"], [])
        self.assertEqual(result["cursor"], n.id)

    def test_read_archived_deleted_reassigned_and_stale_notifications_are_filtered(self):
        n = self.notice()
        for state in ("read", "archived", "deleted", "reassigned", "old"):
            with self.subTest(state=state):
                n.read = state == "read"
                n.created_at = timezone.now() - timedelta(days=8 if state == "old" else 0)
                n.save()
                Notification.objects.filter(id=n.id).update(created_at=n.created_at)
                self.project.archived = state == "archived"
                self.project.save()
                self.task.deleted = state == "deleted"
                self.task.assignee = self.other if state == "reassigned" else self.user
                self.task.save()
                self.assertEqual(self.client.get(self.url, {"after": 0}).json()["notifications"], [])

    def test_filtered_batches_advance_cursor_and_report_more(self):
        rows = [self.notice(read=True) for _ in range(101)]
        first = self.client.get(self.url, {"after": 0}).json()
        self.assertEqual(first["notifications"], [])
        self.assertTrue(first["has_more"])
        self.assertEqual(first["cursor"], rows[99].id)
        last = self.client.get(self.url, {"after": first["cursor"]}).json()
        self.assertFalse(last["has_more"])
        self.assertEqual(last["cursor"], rows[100].id)

    def test_invalid_cursors_and_old_due_reminders(self):
        for value in ("", "-1", "1.0", "n/a", "1e3", "９", "9" * 20):
            self.assertEqual(self.client.get(self.url, {"after": value}).status_code, 400)
        self.task.status = "done"
        self.task.save()
        Notification.objects.create(user=self.user, task=self.task, title="Határidő", kind="due")
        self.assertEqual(self.client.get(self.url, {"after": 0}).json()["notifications"], [])
