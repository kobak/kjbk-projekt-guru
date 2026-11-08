from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from oauth2_provider.models import AccessToken

from .models import Notification, Project, Task
from .worker import tick


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], AXES_ENABLED=False)
class PrivateTaskTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", first_name="Tulajdonos")
        self.member = User.objects.create_superuser(username="admin", first_name="Admin")
        self.client.force_login(self.owner)
        self.other = Client()
        self.other.force_login(self.member)
        response = self.request(self.client, "post", "/api/tasks/", {
            "title": "Személyes teendő", "project_id": None, "due_date": "2026-11-09",
        })
        self.assertEqual(response.status_code, 200)
        self.task = response.json()["task"]
        self.url = f"/api/tasks/{self.task['id']}/"

    def request(self, client, method, url, data):
        return getattr(client, method)(url, data, content_type="application/json")

    def test_personal_task_and_activity_are_only_in_the_owners_lists(self):
        self.assertIsNone(self.task["project_id"])
        self.assertEqual(self.task["assignee_id"], self.owner.id)
        project = Project.objects.create(name="Közös projekt")
        shared = Task.objects.create(project=project, title="Közös feladat", created_by=self.owner)
        own = self.client.get("/api/bootstrap/").json()
        self.assertIn(self.task["id"], [task["id"] for task in own["tasks"]])
        self.assertIn(self.task["id"], own["list_order"]["task_ids"])
        self.assertIn(self.task["id"], [activity["task_id"] for activity in own["activity"]])
        other = self.other.get("/api/bootstrap/").json()
        self.assertEqual([task["id"] for task in other["tasks"]], [str(shared.id)])
        self.assertEqual(other["list_order"]["task_ids"], [str(shared.id)])
        self.assertNotIn(self.task["title"], str(other["activity"]))
        self.assertNotContains(self.other.get("/admin/core/task/"), self.task["id"])
        self.assertEqual(self.other.get(f"/admin/core/task/{self.task['id']}/change/").status_code, 302)
        self.assertEqual(self.request(self.other, "patch", "/api/list-order/", {
            "task_id": self.task["id"], "target_id": str(shared.id), "placement": "before", "version": 0,
        }).status_code, 404)

    @override_settings(GOOGLE_PICKER_CLIENT_ID="test", GOOGLE_PICKER_API_KEY="test", GOOGLE_PICKER_APP_ID="1")
    def test_admin_cannot_use_direct_task_or_related_endpoints(self):
        response = self.other.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "A kért adat nem található.")
        for method, suffix, data in [
            ("patch", "", {"version": 1, "title": "Módosítva"}),
            ("delete", "", {"version": 1}),
            ("post", "comments/", {"body": "Hozzászólás"}),
            ("post", "checklist/", {"text": "Részfeladat"}),
            ("post", "attachments/", {}),
            ("post", "calendar/", {}),
            ("delete", "calendar/", {}),
        ]:
            with self.subTest(method=method, suffix=suffix):
                self.assertEqual(self.request(self.other, method, self.url + suffix, data).status_code, 404)
        with patch("core.drive.requests.get") as google:
            response = self.request(self.other, "post", self.url + "drive-attachments/", {
                "file_id": "file_123", "access_token": "dummy-token",
            })
            self.assertEqual(response.status_code, 404)
            google.assert_not_called()
        self.assertEqual(self.other.get(self.url.rstrip("/") + "/calendar.ics").status_code, 404)

    def test_owner_can_edit_export_and_access_private_attachments(self):
        response = self.request(self.client, "patch", self.url, {"version": 1, "status": "done"})
        self.assertEqual(response.json()["task"]["status"], "done")
        self.assertEqual(self.request(self.client, "post", self.url + "checklist/", {"text": "Részfeladat"}).status_code, 200)
        self.assertContains(self.client.get(self.url + "calendar.ics"), "CLASS:PRIVATE")
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.assertEqual(self.client.post(self.url + "attachments/", {
                "file": SimpleUploadedFile("note.txt", b"private note"),
            }).status_code, 200)
            attachment = self.client.get(self.url).json()["task"]["attachments"][0]
            download = self.client.get(attachment["url"])
            self.assertEqual(b"".join(download.streaming_content), b"private note")
            self.assertEqual(self.other.get(attachment["url"]).status_code, 404)
            path = f"/api/attachments/{attachment['id']}/"
            self.assertEqual(self.other.delete(path).status_code, 404)
            self.assertEqual(self.client.delete(path).status_code, 200)
        self.assertEqual(self.request(self.client, "delete", self.url, {"version": 2}).status_code, 200)

    def test_no_visibility_conversion_assignment_or_mention_can_share_a_private_task(self):
        project = Project.objects.create(name="Közös projekt")
        shared = Task.objects.create(project=project, title="Közös feladat", created_by=self.owner)
        for path, change in [
            (self.url, {"project_id": str(project.id)}),
            (self.url, {"assignee_id": self.member.id}),
            (f"/api/tasks/{shared.id}/", {"project_id": None}),
        ]:
            self.assertEqual(self.request(self.client, "patch", path, {"version": 1, **change}).status_code, 400)
        self.assertEqual(self.request(self.client, "post", self.url + "comments/", {
            "body": "@Admin", "mentions": [{"user_id": self.member.id, "start": 0, "end": 6}],
        }).status_code, 400)
        self.assertFalse(Notification.objects.filter(task_id=self.task["id"], user=self.member).exists())
        due = timezone.localtime() + timedelta(hours=2)
        Task.objects.filter(id=self.task["id"]).update(due_date=due.date(), due_time=due.time())
        with override_settings(NOTIFICATION_EMAIL_ENABLED=False, VAPID_PRIVATE_KEY=""):
            tick()
        self.assertEqual(list(Notification.objects.filter(task_id=self.task["id"]).values_list("user_id", flat=True)), [self.owner.id])

    def test_mcp_scopes_private_tasks_to_the_authenticated_account(self):
        for user in (self.owner, self.member):
            token = f"private-task-token-{user.id}"
            AccessToken.objects.create(user=user, token=token, expires=timezone.now() + timedelta(hours=1),
                scope="tasks:read tasks:write", resource=[settings.APP_URL + "/mcp"])
            for name, arguments in [
                ("list_tasks", {"project_id": None}),
                ("get_task", {"task_id": self.task["id"]}),
                ("update_task", {"task_id": self.task["id"], "version": 1, "title": self.task["title"]}),
            ]:
                with self.subTest(user=user.username, tool=name):
                    response = self.client.post("/mcp", {
                        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    }, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
                    result = response.json()["result"]
                    self.assertEqual(result["isError"], user == self.member and name != "list_tasks")
                    self.assertEqual(self.task["title"] in result["content"][0]["text"], user == self.owner)
