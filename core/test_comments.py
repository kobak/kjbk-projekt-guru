import importlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.core import mail
from django.db import connection
from django.test import Client, TestCase, override_settings

from .models import Activity, Comment, Notification, NotificationPreference, Project, PushSubscription, Task
from .worker import tick


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], AXES_ENABLED=False,
    NOTIFICATION_EMAIL_ENABLED=True, EMAIL_HOST="smtp.example.com", DEFAULT_FROM_EMAIL="guru@example.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", VAPID_PRIVATE_KEY="test-key")
class CommentMentionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner@example.com", email="owner@example.com", first_name="Gazda")
        self.member = User.objects.create_user(username="member@example.com", email="member@example.com", first_name="Kornél")
        self.other = User.objects.create_user(username="other@example.com", email="other@example.com", first_name="Kornél")
        self.project = Project.objects.create(name="Teszt")
        self.task = Task.objects.create(project=self.project, created_by=self.owner, assignee=self.member, title="Közös feladat")
        self.url = f"/api/tasks/{self.task.id}/comments/"
        self.client.force_login(self.owner)
        self.push = patch("core.worker.webpush").start()
        self.addCleanup(patch.stopall)

    def post(self, body="@Kornél nézd meg!", mentions=None, client=None):
        if mentions is None:
            mentions = [{"user_id": self.member.id, "start": 0, "end": 7}]
        return (client or self.client).post(self.url, json.dumps({"body": body, "mentions": mentions}), content_type="application/json")

    def test_mention_of_assignee_has_one_notice_and_one_email(self):
        self.assertEqual(self.post().status_code, 200)
        notice = Notification.objects.get()
        self.assertEqual((notice.user_id, notice.kind), (self.member.id, "mention"))
        self.assertTrue(notice.email_pending)
        self.assertTrue(notice.push_pending)
        tick(); tick()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.member.email])
        self.assertIn("megemlített", mail.outbox[0].subject)
        self.assertIn(f"?task={self.task.id}", mail.outbox[0].body)
        self.task.refresh_from_db()
        self.assertEqual(self.task.version, 1)

    def test_same_name_selection_notifies_exact_user_without_prior_participation(self):
        self.post(mentions=[{"user_id": self.other.id, "start": 0, "end": 7}])
        self.assertEqual(Notification.objects.get(user=self.other).kind, "mention")
        self.assertEqual(Notification.objects.get(user=self.member).kind, "comment")
        detail = self.client.get(f"/api/tasks/{self.task.id}/").json()["task"]
        self.assertEqual(detail["comments"][0]["mentions"][0]["user_id"], self.other.id)

    def test_multiple_mentions_of_same_user_do_not_duplicate_notice(self):
        self.post("@Kornél és @Kornél", [{"user_id": self.member.id, "start": 0, "end": 7},
            {"user_id": self.member.id, "start": 11, "end": 18}])
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(Comment.objects.get().mentions), 2)

    def test_self_mention_does_not_notify_self(self):
        self.post("@Gazda", [{"user_id": self.owner.id, "start": 0, "end": 6}])
        self.assertFalse(Notification.objects.filter(user=self.owner).exists())
        self.assertEqual(Notification.objects.get().kind, "comment")

    def test_text_without_selected_mention_remains_an_ordinary_comment(self):
        self.post(mentions=[])
        self.assertEqual(Notification.objects.get().kind, "comment")
        self.assertFalse(Notification.objects.get().email_pending)
        self.assertEqual(Comment.objects.get().mentions, [])

    def test_utf16_emoji_and_trimmed_whitespace_keep_correct_highlight(self):
        self.assertEqual(self.post("  👍 @Kornél!  ", [{"user_id": self.member.id, "start": 5, "end": 12}]).status_code, 200)
        comment = Comment.objects.get()
        self.assertEqual(comment.body, "👍 @Kornél!")
        self.assertEqual(comment.mentions, [{"user_id": self.member.id, "start": 3, "end": 10}])

    def test_invalid_mentions_are_atomic(self):
        valid = {"user_id": self.member.id, "start": 0, "end": 7}
        payloads = [None, {}, [1], [dict(valid, user_id=True)], [dict(valid, user_id=9999)],
            [dict(valid, start=-1)], [dict(valid, end=100)], [dict(valid, end=6)],
            [dict(valid, extra=1)], [valid, valid], [dict(valid, start="0")]]
        for spans in payloads:
            with self.subTest(spans=spans):
                self.assertEqual(self.post(mentions=spans if spans is not None else {}).status_code, 400)
                self.assertFalse(Comment.objects.exists())
                self.assertFalse(Notification.objects.exists())
                self.assertFalse(Activity.objects.exists())

    def test_disabled_or_renamed_member_must_be_reselected(self):
        self.member.is_active = False
        self.member.save()
        self.assertEqual(self.post().status_code, 400)
        self.member.is_active, self.member.first_name = True, "Más név"
        self.member.save()
        self.assertEqual(self.post().status_code, 400)
        self.assertFalse(Comment.objects.exists())

    def test_notification_failure_rolls_back_the_comment(self):
        with patch("core.comments.notify", side_effect=RuntimeError("test-only failure")):
            with self.assertRaises(RuntimeError):
                self.post()
        self.assertFalse(Comment.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(Activity.objects.exists())

    def test_mention_channels_are_independent_of_comment_channels(self):
        NotificationPreference.objects.create(user=self.member, email_events=[], push_events=["mention"])
        PushSubscription.objects.create(user=self.member, endpoint="https://fcm.googleapis.com/test", keys={})
        self.post(); tick()
        self.assertEqual(len(mail.outbox), 0)
        self.push.assert_called_once()
        pref = NotificationPreference.objects.get(user=self.member)
        pref.email_events, pref.push_events = ["mention"], []
        pref.save()
        self.push.reset_mock()
        self.post(); tick()
        self.assertEqual(len(mail.outbox), 1)
        self.push.assert_not_called()

    def test_disabling_queued_mentions_keeps_in_app_and_skips_external_delivery(self):
        self.post()
        NotificationPreference.objects.create(user=self.member, email_events=[], push_events=[])
        tick()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        self.push.assert_not_called()

    def test_unauthenticated_csrf_archived_and_deleted_requests_cannot_comment(self):
        self.assertEqual(self.post(client=Client()).status_code, 401)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(self.post(client=csrf).status_code, 403)
        self.project.archived = True
        self.project.save()
        self.assertEqual(self.post().status_code, 404)
        self.project.archived = False
        self.project.save()
        self.task.deleted = True
        self.task.save()
        self.assertEqual(self.post().status_code, 404)
        self.assertFalse(Comment.objects.exists())

    def test_migration_adds_only_new_default_and_reverse_preserves_old_choices(self):
        pref = NotificationPreference.objects.create(user=self.member, email_events=["due"], push_events=[])
        migration = importlib.import_module("core.migrations.0006_comment_mentions")
        editor = SimpleNamespace(connection=connection)
        migration.enable_mentions(apps, editor)
        migration.enable_mentions(apps, editor)
        pref.refresh_from_db()
        self.assertEqual(pref.email_events, ["due", "mention"])
        self.assertEqual(pref.push_events, ["mention"])
        migration.remove_mentions(apps, editor)
        pref.refresh_from_db()
        self.assertEqual(pref.email_events, ["due"])
        self.assertEqual(pref.push_events, [])
