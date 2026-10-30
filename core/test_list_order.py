import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import Activity, CalendarLink, Notification, PersonalListOrder, Project, Task


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost"], AXES_ENABLED=False)
class PersonalListOrderTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice@example.com")
        self.bob = User.objects.create_user(username="bob@example.com")
        self.project = Project.objects.create(name="Projekt")
        self.tasks = [Task.objects.create(project=self.project, title=str(index), created_by=self.alice, assignee=self.bob, position=index) for index in range(4)]
        self.ids = [str(task.id) for task in self.tasks]
        self.client.force_login(self.alice)

    def move(self, moving=0, target=2, placement="after", version=0, client=None, extra=None):
        payload = {"task_id": self.ids[moving], "target_id": self.ids[target], "placement": placement, "version": version}
        payload.update(extra or {})
        return (client or self.client).patch("/api/list-order/", json.dumps(payload), content_type="application/json")

    def test_default_order_does_not_write_and_bootstrap_contains_only_own_order(self):
        self.assertEqual(self.client.get("/api/list-order/").json(), {"task_ids": self.ids, "version": 0})
        self.assertFalse(PersonalListOrder.objects.exists())
        self.move()
        bob = Client()
        bob.force_login(self.bob)
        self.assertEqual(bob.get("/api/bootstrap/").json()["list_order"], {"task_ids": self.ids, "version": 0})
        self.assertEqual(self.client.get("/api/bootstrap/").json()["list_order"]["task_ids"], [self.ids[1], self.ids[2], self.ids[0], self.ids[3]])
        self.assertFalse(PersonalListOrder.objects.filter(user=self.bob).exists())

    def test_moves_are_persistent_and_do_not_change_shared_task_versions_or_notifications(self):
        link = CalendarLink.objects.create(task=self.tasks[0], user=self.alice, enabled=True, synced_version=self.tasks[0].version)
        before = list(Task.objects.order_by("position").values_list("id", "position", "version", "updated_at"))
        response = self.move()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], 1)
        self.assertEqual(before, list(Task.objects.order_by("position").values_list("id", "position", "version", "updated_at")))
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(Activity.objects.exists())
        link.refresh_from_db()
        self.assertEqual(link.synced_version, self.tasks[0].version)
        device = Client()
        device.force_login(self.alice)
        self.assertEqual(device.get("/api/list-order/").json(), response.json())
        self.assertEqual(self.move(0, 1, "before", 1).json()["task_ids"], self.ids)

    def test_reordering_a_filtered_subset_preserves_every_other_tasks_relative_order(self):
        second_project = Project.objects.create(name="Másik projekt")
        self.tasks[1].project = second_project
        self.tasks[1].save(update_fields=["project"])
        result = self.move(0, 3).json()["task_ids"]
        self.assertEqual(result, [self.ids[1], self.ids[2], self.ids[3], self.ids[0]])
        self.assertEqual([value for value in result if value != self.ids[0]], self.ids[1:])

    def test_stale_versions_are_rejected_without_overwriting_saved_order(self):
        saved = self.move().json()
        self.assertEqual(self.move(1, 3).status_code, 409)
        self.assertEqual(self.client.get("/api/list-order/").json(), saved)

    def test_new_and_deleted_tasks_are_merged_without_losing_saved_order(self):
        self.move()
        self.tasks[2].deleted = True
        self.tasks[2].save(update_fields=["deleted"])
        new_task = Task.objects.create(project=self.project, title="Új", created_by=self.alice, position=0)
        ids = self.client.get("/api/list-order/").json()["task_ids"]
        self.assertEqual(ids, [self.ids[1], self.ids[0], self.ids[3], str(new_task.id)])

    def test_archived_and_deleted_tasks_cannot_be_dragged(self):
        self.tasks[0].deleted = True
        self.tasks[0].save(update_fields=["deleted"])
        self.assertEqual(self.move().status_code, 404)
        self.tasks[0].deleted = False
        self.tasks[0].save(update_fields=["deleted"])
        self.project.archived = True
        self.project.save(update_fields=["archived"])
        self.assertEqual(self.move().status_code, 400)
        self.assertFalse(PersonalListOrder.objects.exists())

    def test_login_csrf_and_patch_method_are_required(self):
        self.assertEqual(Client().get("/api/list-order/").status_code, 401)
        self.assertEqual(self.move(client=Client()).status_code, 401)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.alice)
        self.assertEqual(self.move(client=protected).status_code, 403)
        self.assertEqual(self.client.post("/api/list-order/").status_code, 405)

    def test_invalid_payloads_and_cross_account_fields_do_not_write(self):
        for extra in ({"user_id": self.bob.id}, {"task_id": "not-a-uuid"}, {"target_id": None},
            {"version": True}, {"version": -1}, {"placement": "first"}):
            with self.subTest(extra=extra): self.assertEqual(self.move(extra=extra).status_code, 400)
        self.assertFalse(PersonalListOrder.objects.exists())

    def test_noop_does_not_create_an_order(self):
        self.assertEqual(self.move(0, 0).json(), {"task_ids": self.ids, "version": 0})
        self.assertFalse(PersonalListOrder.objects.exists())

    def test_task_creation_time_is_returned_and_cannot_be_changed_by_edit(self):
        created = timezone.now() - timedelta(days=3)
        Task.objects.filter(id=self.tasks[0].id).update(created_at=created)
        url = f"/api/tasks/{self.ids[0]}/"
        self.assertEqual(self.client.get(url).json()["task"]["created_at"], created.isoformat())
        response = self.client.patch(url, json.dumps({"version": self.tasks[0].version, "created_at": "2000-01-01T00:00:00Z", "title": "Új cím"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task"]["created_at"], created.isoformat())
