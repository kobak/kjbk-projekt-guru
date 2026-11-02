import json

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings

from .models import Announcement, AnnouncementDismissal, Notification, Task, Workspace


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], AXES_ENABLED=False)
class AnnouncementTests(TestCase):
    def setUp(self):
        Workspace.objects.create(id=1)
        self.admin = User.objects.create_user(username="admin@example.com", is_staff=True)
        self.member = User.objects.create_user(username="member@example.com")
        self.other = User.objects.create_user(username="other@example.com")
        self.client.force_login(self.admin)
        self.member_client = Client()
        self.member_client.force_login(self.member)
        self.other_client = Client()
        self.other_client.force_login(self.other)
        self.payload = {"title": "Megérkezett a Mac-app", "body": "Már letölthető.",
            "link_label": "Letöltés", "link_url": "https://example.com/guru.zip"}

    def send(self, path, data, *, client=None, method="post"):
        return getattr(client or self.client, method)(path, json.dumps(data), content_type="application/json")

    def create(self, **fields):
        result = self.send("/api/announcements/", self.payload | fields)
        self.assertEqual(result.status_code, 200)
        return result.json()["announcement"]

    def publish(self, item, *, published=True, client=None):
        action = "publish" if published else "unpublish"
        return self.send(f"/api/announcements/{item['id']}/{action}/", {"version": item["version"]}, client=client)

    def visible(self, client=None):
        return (client or self.member_client).get("/api/bootstrap/").json()["announcement"]

    def dismiss(self, item, client=None):
        return self.send(f"/api/announcements/{item['id']}/dismiss/", {"version": item["version"]}, client=client or self.member_client)

    def test_only_admin_can_list_create_edit_or_publish(self):
        item = self.create()
        for client, status in [(Client(), 401), (self.member_client, 403)]:
            self.assertEqual(client.get("/api/announcements/").status_code, status)
            self.assertEqual(self.send("/api/announcements/", self.payload, client=client).status_code, status)
            self.assertEqual(self.send(f"/api/announcements/{item['id']}/", self.payload | {"version": 1}, client=client, method="patch").status_code, status)
            self.assertEqual(self.publish(item, client=client).status_code, status)
        self.assertIsNone(self.visible())

    def test_csrf_and_supported_methods(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        item = self.create()
        self.assertEqual(self.send("/api/announcements/", self.payload, client=protected).status_code, 403)
        self.assertEqual(self.publish(item, client=protected).status_code, 403)
        self.assertEqual(self.dismiss(item, client=protected).status_code, 403)
        self.assertEqual(self.client.get(f"/api/announcements/{item['id']}/publish/").status_code, 405)
        self.assertEqual(self.client.delete(f"/api/announcements/{item['id']}/").status_code, 405)

    def test_drafts_are_private_and_no_task_or_notifications_are_created(self):
        item = self.create()
        self.assertFalse(item["published"])
        self.assertIsNone(self.visible())
        self.assertIsNone(self.visible(self.client))
        self.assertEqual(len(self.client.get("/api/announcements/").json()["announcements"]), 1)
        self.assertFalse(Task.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_publication_replaces_previous_and_preserves_editable_history(self):
        first = self.publish(self.create()).json()["announcement"]
        second = self.publish(self.create(title="Új hír")).json()["announcement"]
        self.assertEqual(self.visible()["id"], second["id"])
        self.assertEqual(Announcement.objects.filter(active_slot=1).count(), 1)
        self.assertEqual(Announcement.objects.count(), 2)
        self.assertIsNone(Announcement.objects.get(id=first["id"]).active_slot)
        self.assertEqual(self.publish(first).status_code, 409)

    def test_dismissal_is_personal_and_saved_across_devices(self):
        item = self.publish(self.create()).json()["announcement"]
        self.assertEqual(self.dismiss(item).status_code, 200)
        self.assertIsNone(self.visible())
        another_device = Client()
        another_device.force_login(self.member)
        self.assertIsNone(self.visible(another_device))
        self.assertEqual(self.visible(self.other_client)["id"], item["id"])
        self.assertEqual(self.visible(self.client)["id"], item["id"])
        self.assertNotIn("published", self.visible(self.other_client))

    def test_changed_content_returns_but_unchanged_save_keeps_dismissal(self):
        item = self.publish(self.create()).json()["announcement"]
        self.dismiss(item)
        path = f"/api/announcements/{item['id']}/"
        unchanged = self.send(path, self.payload | {"version": item["version"]}, method="patch").json()["announcement"]
        self.assertEqual(unchanged["version"], item["version"])
        self.assertIsNone(self.visible())
        changed = self.send(path, self.payload | {"version": item["version"], "body": "Frissített információ"}, method="patch").json()["announcement"]
        self.assertGreater(changed["version"], item["version"])
        self.assertEqual(self.visible()["body"], "Frissített információ")
        self.dismiss(changed)
        self.assertEqual(AnnouncementDismissal.objects.filter(user=self.member).count(), 1)

    def test_stale_edit_unpublish_and_dismiss_cannot_override_new_content(self):
        item = self.publish(self.create()).json()["announcement"]
        path = f"/api/announcements/{item['id']}/"
        changed = self.send(path, self.payload | {"version": item["version"], "title": "Új változat"}, method="patch").json()["announcement"]
        self.assertEqual(self.send(path, self.payload | {"version": item["version"]}, method="patch").status_code, 409)
        self.assertEqual(self.publish(item, published=False).status_code, 409)
        self.assertEqual(self.dismiss(item).status_code, 409)
        self.assertEqual(self.visible()["version"], changed["version"])
        self.assertFalse(AnnouncementDismissal.objects.exists())

    def test_partial_edit_preserves_omitted_content_and_link_fields(self):
        item = self.create()
        result = self.send(f"/api/announcements/{item['id']}/", {"version": item["version"], "title": "Javított cím"}, method="patch")
        self.assertEqual(result.status_code, 200)
        changed = result.json()["announcement"]
        self.assertEqual(changed["body"], self.payload["body"])
        self.assertEqual(changed["link_label"], self.payload["link_label"])
        self.assertEqual(changed["link_url"], self.payload["link_url"])

    def test_unpublish_and_republish_are_reversible_and_reshow_news(self):
        item = self.publish(self.create()).json()["announcement"]
        self.dismiss(item)
        removed = self.publish(item, published=False).json()["announcement"]
        self.assertIsNone(self.visible(self.other_client))
        restored = self.publish(removed).json()["announcement"]
        self.assertEqual(self.visible()["version"], restored["version"])

    def test_missing_announcements_and_drafts_cannot_be_dismissed(self):
        self.assertEqual(self.dismiss({"id": 999, "version": 1}).status_code, 404)
        self.assertEqual(self.dismiss(self.create()).status_code, 409)
        self.assertEqual(self.dismiss(self.create(), client=Client()).status_code, 401)

    def test_bad_links_and_invalid_payloads_do_not_write(self):
        for extra in [{"title": " "}, {"title": "x" * 121}, {"body": "x" * 501}, {"body": 1},
            {"active_slot": 1}, {"published": True}, {"link_url": "", "link_label": "Letöltés"},
            {"link_url": "https://example.com", "link_label": ""}, {"link_url": "javascript:alert(1)"},
            {"link_url": "data:text/html,test"}, {"link_url": "//evil.example"}, {"link_url": "/\\evil.example"},
            {"link_url": "http://example.com"}, {"link_url": "https://user:secret@example.com"},
            {"link_url": "https://example.com/\nx"}, {"link_url": "https://example.com:bad"}]:
            with self.subTest(extra=extra):
                self.assertEqual(self.send("/api/announcements/", self.payload | extra).status_code, 400)
        self.assertFalse(Announcement.objects.exists())

    def test_internal_task_links_and_plain_text_are_preserved(self):
        item = self.create(title='<script>alert("x")</script>', body="Sima szöveg, nem HTML", link_url="/?task=123")
        self.publish(item)
        self.assertEqual(self.visible()["title"], '<script>alert("x")</script>')
        self.assertEqual(self.visible()["link_url"], "/?task=123")

    def test_versions_are_strict_and_dismissals_cannot_target_other_users(self):
        item = self.publish(self.create()).json()["announcement"]
        for version in (None, True, "2", 0):
            self.assertEqual(self.publish(item | {"version": version}).status_code, 400)
        path = f"/api/announcements/{item['id']}/dismiss/"
        self.assertEqual(self.send(path, {"version": item["version"], "user_id": self.other.id}, client=self.member_client).status_code, 400)
        self.assertFalse(AnnouncementDismissal.objects.exists())

    def test_database_enforces_single_active_news_and_one_personal_dismissal(self):
        item = Announcement.objects.create(title="Egy", active_slot=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Announcement.objects.create(title="Kettő", active_slot=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Announcement.objects.create(title="Hibás hely", active_slot=2)
        AnnouncementDismissal.objects.create(user=self.member, announcement=item, version=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AnnouncementDismissal.objects.create(user=self.member, announcement=item, version=1)
