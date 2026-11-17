import json
import re
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import PasswordResetDelivery, PushSubscription, RateLimit
from .password_reset import deliver_reset, deliver_pending_resets
from .worker import tick


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost"], AXES_ENABLED=False,
                   APP_URL="https://guru.example.com", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   DEFAULT_FROM_EMAIL="GURU <guru@example.com>", NOTIFICATION_EMAIL_ENABLED=False,
                   VAPID_PRIVATE_KEY="")
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="member@example.com", email="member@example.com",
                                             password="Original-test-secret-2026!")

    def post(self, path, data, client=None):
        return (client or self.client).post("/api/password-reset/" + path, json.dumps(data), content_type="application/json")

    def request_link(self, email=None):
        return self.post("", {"email": email or self.user.email})

    def link(self):
        self.assertEqual(self.request_link().status_code, 200)
        deliver_pending_resets()
        match = re.search(r"/#reset=([^/\s]+)/([^\s]+)", mail.outbox[-1].body)
        return {"uid": match[1], "token": match[2], "password": "Replacement-test-secret-2026!"}

    def test_request_is_generic_and_never_sends_mail_in_the_http_request(self):
        known = self.request_link("MEMBER@EXAMPLE.COM")
        unknown = self.request_link("missing@example.com")
        disabled = User.objects.create_user("disabled@example.com", email="disabled@example.com", password="secret", is_active=False)
        unusable = User.objects.create_user("unusable@example.com", email="unusable@example.com")
        self.assertEqual(known.json(), unknown.json())
        self.assertEqual(known.json(), self.request_link(disabled.email).json())
        self.assertEqual(known.json(), self.request_link(unusable.email).json())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(PasswordResetDelivery.objects.count(), 1)
        self.assertNotIn(self.user.email, " ".join(RateLimit.objects.values_list("key", flat=True)))

    def test_worker_sends_reset_even_when_task_email_notifications_are_disabled(self):
        values = self.link()
        item = PasswordResetDelivery.objects.get()
        self.assertTrue(item.finished)
        self.assertIsNotNone(item.sent_at)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn("https://guru.example.com/#reset=", mail.outbox[0].body)
        self.assertIn("60 percig", mail.outbox[0].body)
        self.assertIn(values["token"], mail.outbox[0].alternatives[0].content)
        self.assertNotIn("Original-test-secret", mail.outbox[0].body)
        tick()
        self.assertEqual(len(mail.outbox), 1)

    def test_valid_reset_is_one_use_and_old_password_stops_working(self):
        values = self.link()
        self.assertEqual(self.post("confirm/", values).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(values["password"]))
        self.assertFalse(self.user.check_password("Original-test-secret-2026!"))
        self.assertEqual(self.post("confirm/", values).status_code, 400)
        result = self.client.post("/api/login/", json.dumps({"email": self.user.email, "password": values["password"]}), content_type="application/json")
        self.assertEqual(result.status_code, 200)

    def test_old_sessions_and_push_are_invalidated_only_after_success(self):
        previous = Client()
        previous.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        PushSubscription.objects.create(user=self.user, endpoint="https://fcm.googleapis.com/reset-test", keys={})
        values = self.link()
        self.assertEqual(previous.get("/api/bootstrap/").status_code, 200)
        self.assertEqual(PushSubscription.objects.count(), 1)
        self.assertEqual(self.post("confirm/", values).status_code, 200)
        self.assertEqual(previous.get("/api/bootstrap/").status_code, 401)
        self.assertFalse(PushSubscription.objects.exists())

    def test_weak_password_does_not_consume_token(self):
        values = self.link()
        self.assertEqual(self.post("confirm/", {**values, "password": "123"}).status_code, 400)
        self.assertEqual(self.post("confirm/", values).status_code, 200)

    def test_expired_or_malformed_token_never_changes_password(self):
        values = self.link()
        future = default_token_generator._now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1)
        with patch.object(default_token_generator, "_now", return_value=future):
            self.assertEqual(self.post("confirm/", values).status_code, 400)
        for change in ({"uid": "!"}, {"uid": "OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5"}, {"token": "bogus"}):
            self.assertEqual(self.post("confirm/", {**values, **change}).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Original-test-secret-2026!"))

    def test_changed_login_password_email_or_active_state_cancels_queued_delivery(self):
        for field, value in (("last_login", timezone.now()), ("password", "changed"), ("email", "changed@example.com"), ("is_active", False)):
            with self.subTest(field=field):
                self.request_link()
                item = PasswordResetDelivery.objects.latest("id")
                original = getattr(self.user, field)
                User.objects.filter(pk=self.user.pk).update(**{field: value})
                deliver_reset(item.pk)
                item.refresh_from_db()
                self.assertTrue(item.finished)
                self.assertIsNone(item.sent_at)
                User.objects.filter(pk=self.user.pk).update(**{field: original})
                RateLimit.objects.all().delete()
        self.assertEqual(len(mail.outbox), 0)

    def test_password_email_login_and_deactivation_invalidate_issued_tokens(self):
        values = self.link()
        for field, value in (("last_login", timezone.now()), ("password", "changed"), ("email", "changed@example.com"), ("is_active", False)):
            with self.subTest(field=field):
                original = getattr(self.user, field)
                User.objects.filter(pk=self.user.pk).update(**{field: value})
                self.assertEqual(self.post("confirm/", values).status_code, 400)
                User.objects.filter(pk=self.user.pk).update(**{field: original})

    def test_retry_redacts_errors_and_expired_requests_are_not_sent(self):
        self.request_link()
        item = PasswordResetDelivery.objects.get()
        with patch("core.password_reset.EmailMultiAlternatives.send", side_effect=RuntimeError("private smtp details")):
            with self.assertLogs("core.password_reset", level="WARNING") as logs:
                deliver_reset(item.pk)
        self.assertNotIn("private smtp details", str(logs.output))
        item.refresh_from_db()
        self.assertEqual(item.error, "RuntimeError")
        self.assertFalse(item.finished)
        deliver_reset(item.pk)
        self.assertEqual(len(mail.outbox), 0)
        PasswordResetDelivery.objects.filter(pk=item.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        deliver_reset(item.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.request_link()
        expired = PasswordResetDelivery.objects.latest("id")
        PasswordResetDelivery.objects.filter(pk=expired.pk).update(created_at=timezone.now()-timedelta(hours=2))
        deliver_reset(expired.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_rate_limits_apply_to_known_and_unknown_addresses(self):
        for address in (self.user.email, "unknown@example.com"):
            RateLimit.objects.all().delete()
            self.assertEqual([self.request_link(address).status_code for _ in range(4)], [200, 200, 200, 429])

    def test_requires_csrf_post_and_valid_data(self):
        self.assertEqual(self.client.get("/api/password-reset/").status_code, 405)
        self.assertEqual(self.client.get("/api/password-reset/confirm/").status_code, 405)
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post("", {"email": self.user.email}, client).status_code, 403)
        self.assertEqual(self.post("confirm/", {}, client).status_code, 403)
        client.get("/api/session/")
        response = client.post("/api/password-reset/", json.dumps({"email": self.user.email}),
            content_type="application/json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post("", {"email": "invalid"}).status_code, 400)
