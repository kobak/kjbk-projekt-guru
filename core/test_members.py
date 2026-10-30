import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.core import mail
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import AppearancePreference, Invite, Notification, NotificationPreference, Project, Workspace
from .services import save_task
from .worker import send_notification_email
from . import views


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost"], AXES_ENABLED=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", NOTIFICATION_EMAIL_ENABLED=True,
    EMAIL_HOST="smtp.example.com", DEFAULT_FROM_EMAIL="guru@example.com")
class MemberEmailTests(TestCase):
    def setUp(self):
        Workspace.objects.create(id=1)
        self.admin = User.objects.create_user(username="admin@example.com", email="admin@example.com", is_staff=True)
        self.member = User.objects.create_user(username="typo@example.com", email="typo@example.com", first_name="Csapattag", password="Test-member-password-2026!")
        self.client.force_login(self.admin)
        self.url = f"/api/members/{self.member.id}/"

    def change(self, data=None, client=None, url=None):
        return (client or self.client).patch(url or self.url, json.dumps(data if data is not None else {
            "email": "correct@example.com", "current_email": "typo@example.com"}), content_type="application/json")

    def invite(self, email, token, accepted=False):
        return Invite.objects.create(email=email, token_hash=hashlib.sha256(token.encode()).hexdigest(), created_by=self.admin,
            expires_at=timezone.now() + timedelta(days=1), accepted_at=timezone.now() if accepted else None)

    def test_admin_changes_address_and_login_without_changing_identity_or_password(self):
        original_password = self.member.password
        preference = NotificationPreference.objects.create(user=self.member, email_events=["comment"], push_events=[])
        appearance = AppearancePreference.objects.create(user=self.member, theme="dark")
        response = self.change({"email": "  Correct@EXAMPLE.com  ", "current_email": self.member.email})
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(response.json()["user"]["id"], self.member.id)
        self.assertEqual(self.member.email, "correct@example.com")
        self.assertEqual(self.member.username, "correct@example.com")
        self.assertEqual(self.member.password, original_password)
        self.assertTrue(self.member.is_active)
        self.assertFalse(self.member.is_staff)
        self.assertEqual(self.member.first_name, "Csapattag")
        self.assertEqual(NotificationPreference.objects.get(user=self.member).id, preference.id)
        self.assertEqual(AppearancePreference.objects.get(user=self.member).id, appearance.id)
        self.assertEqual(LogEntry.objects.get().user_id, self.admin.id)
        self.assertEqual(LogEntry.objects.get().object_id, str(self.member.id))
        anonymous = Client()
        payload = {"email": "typo@example.com", "password": "Test-member-password-2026!"}
        self.assertEqual(anonymous.post("/api/login/", json.dumps(payload), content_type="application/json").status_code, 401)
        payload["email"] = "correct@example.com"
        self.assertEqual(anonymous.post("/api/login/", json.dumps(payload), content_type="application/json").status_code, 200)

    def test_only_authenticated_admin_can_change_addresses(self):
        self.assertEqual(self.change(client=Client()).status_code, 401)
        member_client = Client()
        member_client.force_login(self.member)
        self.assertEqual(self.change(client=member_client).status_code, 403)
        self.assertEqual(self.change(client=member_client, url=f"/api/members/{self.admin.id}/").status_code, 403)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "typo@example.com")

    def test_csrf_is_required_and_other_methods_are_rejected(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        self.assertEqual(self.change(client=protected).status_code, 403)
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_invalid_fields_addresses_and_types_do_not_write(self):
        for data in ({}, {"email": "new@example.com"}, {"email": "invalid", "current_email": self.member.email},
            {"email": True, "current_email": self.member.email}, {"email": "new@example.com", "current_email": None},
            {"email": "new@example.com", "current_email": self.member.email, "is_staff": True},
            {"email": "new@example.com", "current_email": self.member.email, "password": "a-new-password"},
            {"email": "a" * 64 + "@" + "b" * 60 + "." + "c" * 27, "current_email": self.member.email}):
            with self.subTest(data=data):
                self.assertEqual(self.change(data).status_code, 400)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "typo@example.com")
        self.assertFalse(LogEntry.objects.exists())

    def test_duplicate_email_or_login_is_rejected_even_for_inactive_accounts(self):
        User.objects.create_user(username="other-login@example.com", email="email-used@example.com")
        User.objects.create_user(username="login-used@example.com", email="another@example.com", is_active=False)
        for email in ("EMAIL-USED@example.com", "LOGIN-USED@EXAMPLE.COM"):
            with self.subTest(email=email):
                self.assertEqual(self.change({"email": email, "current_email": self.member.email}).status_code, 409)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "typo@example.com")
        self.assertFalse(LogEntry.objects.exists())

    def test_stale_edit_cannot_overwrite_a_more_recent_correction(self):
        self.assertEqual(self.change().status_code, 200)
        stale = self.change({"email": "stale@example.com", "current_email": "typo@example.com"})
        self.assertEqual(stale.status_code, 409)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "correct@example.com")
        self.assertEqual(LogEntry.objects.count(), 1)

    def test_admin_can_change_own_address_without_losing_session_or_role(self):
        response = self.change({"email": "new-admin@example.com", "current_email": self.admin.email}, url=f"/api/members/{self.admin.id}/")
        self.assertEqual(response.status_code, 200)
        session = self.client.get("/api/session/").json()["user"]
        self.assertEqual(session["id"], self.admin.id)
        self.assertEqual(session["email"], "new-admin@example.com")
        self.assertTrue(session["admin"])

    def test_inactive_and_missing_members_are_not_editable(self):
        self.assertEqual(self.change(url="/api/members/999999/").status_code, 404)
        self.member.is_active = False
        self.member.save(update_fields=["is_active"])
        self.assertEqual(self.change().status_code, 404)
        self.assertFalse(LogEntry.objects.exists())

    def test_unused_invites_for_old_and_new_addresses_are_revoked(self):
        old = self.invite("typo@example.com", "old-token")
        new = self.invite("correct@example.com", "new-token")
        historical = self.invite("typo@example.com", "used-token", accepted=True)
        unrelated = self.invite("unrelated@example.com", "other-token")
        self.assertEqual(self.change().status_code, 200)
        self.assertFalse(Invite.objects.filter(id__in=[old.id, new.id]).exists())
        self.assertEqual(set(Invite.objects.values_list("id", flat=True)), {historical.id, unrelated.id})
        self.assertEqual(Client().get("/api/invites/old-token/").status_code, 404)
        self.assertEqual(Client().get("/api/invites/new-token/").status_code, 404)

    def test_existing_task_and_pending_notification_use_the_corrected_address(self):
        project = Project.objects.create(name="Közös projekt")
        task = save_task({"project_id": str(project.id), "title": "Kiosztott feladat", "assignee_id": self.member.id}, self.admin)
        notification = Notification.objects.get(user=self.member)
        self.assertTrue(notification.email_pending)
        self.assertEqual(self.change().status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        task.refresh_from_db()
        self.assertEqual(task.assignee_id, self.member.id)
        send_notification_email(notification.id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["correct@example.com"])
        self.assertEqual(task.comments.count(), 0)

    def test_same_address_is_a_noop_and_150_character_address_is_supported(self):
        self.assertEqual(self.change({"email": self.member.email, "current_email": self.member.email}).status_code, 200)
        self.assertFalse(LogEntry.objects.exists())
        email = "a" * 64 + "@" + "b" * 60 + "." + "c" * 24
        self.assertEqual(len(email), 150)
        self.assertEqual(self.change({"email": email, "current_email": self.member.email}).status_code, 200)

    def test_database_uniqueness_race_is_a_conflict_with_no_partial_changes(self):
        invite = self.invite(self.member.email, "race-token")
        with patch.object(User, "save", side_effect=IntegrityError("simulated unique conflict")):
            self.assertEqual(self.change().status_code, 409)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "typo@example.com")
        self.assertEqual(self.member.username, "typo@example.com")
        self.assertTrue(Invite.objects.filter(id=invite.id).exists())
        self.assertFalse(LogEntry.objects.exists())

    def test_concurrent_profile_save_does_not_restore_an_old_email(self):
        member_client = Client()
        member_client.force_login(self.member)
        original_text = views.text
        def concurrent_change(data, key, *args):
            User.objects.filter(id=self.member.id).update(email="correct@example.com", username="correct@example.com")
            return original_text(data, key, *args)
        with patch("core.views.text", side_effect=concurrent_change):
            response = member_client.patch("/api/profile/", json.dumps({"name": "Új név"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "correct@example.com")
        self.assertEqual(self.member.username, "correct@example.com")
        self.assertEqual(self.member.first_name, "Új név")

    def test_concurrent_deactivation_does_not_restore_an_old_email(self):
        stale_member = User.objects.get(id=self.member.id)
        User.objects.filter(id=self.member.id).update(email="correct@example.com", username="correct@example.com")
        with patch("core.views.get_object_or_404", return_value=stale_member):
            response = self.client.post(f"/api/members/{self.member.id}/deactivate/")
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.assertEqual(self.member.email, "correct@example.com")
        self.assertEqual(self.member.username, "correct@example.com")
