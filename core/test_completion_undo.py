import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Project, Task


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], AXES_ENABLED=False)
class CompletionUndoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="member@example.com")
        project = Project.objects.create(name="Teszt")
        self.task = Task.objects.create(project=project, created_by=self.user, title="Ellenőrzendő", status="review", priority="high")
        self.client.force_login(self.user)
        self.url = f"/api/tasks/{self.task.id}/"

    def change(self, **data):
        return self.client.patch(self.url, json.dumps(data), content_type="application/json")

    def test_completion_can_restore_exact_previous_status_and_preserve_fields(self):
        completed = self.change(status="done", version=1).json()["task"]
        response = self.change(status="review", version=completed["version"])
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual((self.task.status, self.task.title, self.task.priority), ("review", "Ellenőrzendő", "high"))

    def test_undo_cannot_overwrite_any_intervening_edit(self):
        completed = self.change(status="done", version=1).json()["task"]
        self.assertEqual(self.change(title="Közben javított cím", version=completed["version"]).status_code, 200)
        self.assertEqual(self.change(status="review", version=completed["version"]).status_code, 409)
        self.task.refresh_from_db()
        self.assertEqual((self.task.status, self.task.title), ("done", "Közben javított cím"))
