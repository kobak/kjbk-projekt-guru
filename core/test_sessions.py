import time
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings
from django.utils import timezone


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], AXES_ENABLED=False)
class ActiveSessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("member@example.com", email="member@example.com", password="Test-login-2026!")
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")

    def test_active_session_renews_cookie_and_database_without_rotating_key(self):
        key = self.client.session.session_key
        Session.objects.filter(session_key=key).update(expire_date=timezone.now()+timedelta(hours=1))
        response = self.client.get("/api/bootstrap/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.session_key, key)
        self.assertEqual(int(response.cookies[settings.SESSION_COOKIE_NAME]["max-age"]), settings.SESSION_COOKIE_AGE)
        self.assertGreater(Session.objects.get(session_key=key).expire_date, timezone.now()+timedelta(days=13))
        self.assertNotIn(settings.SESSION_COOKIE_NAME, self.client.get("/api/bootstrap/").cookies)
        future = int(time.time()) + 3601
        with patch("core.middleware.time.time", return_value=future):
            self.assertIn(settings.SESSION_COOKIE_NAME, self.client.get("/api/session/").cookies)

    def test_native_background_poll_does_not_extend_session(self):
        key = self.client.session.session_key
        before = Session.objects.get(session_key=key).expire_date
        self.assertEqual(self.client.get("/api/desktop/notifications/").status_code, 200)
        self.assertEqual(Session.objects.get(session_key=key).expire_date, before)
        self.assertNotIn("_guru_active_at", self.client.session)

    def test_anonymous_expired_logged_out_and_password_changed_sessions_stay_invalid(self):
        anonymous = Client()
        self.assertIsNone(anonymous.get("/api/session/").json()["user"])
        self.assertNotIn(settings.SESSION_COOKIE_NAME, anonymous.cookies)
        key = self.client.session.session_key
        Session.objects.filter(session_key=key).update(expire_date=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get("/api/bootstrap/").status_code, 401)
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        self.client.post("/api/logout/", "{}", content_type="application/json")
        self.assertEqual(self.client.get("/api/bootstrap/").status_code, 401)
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        self.user.set_password("Changed-test-login-2026!")
        self.user.save(update_fields=["password"])
        self.assertEqual(self.client.get("/api/bootstrap/").status_code, 401)

    def test_failed_requests_and_disabled_accounts_do_not_renew(self):
        self.assertEqual(self.client.post("/api/bootstrap/", "{}", content_type="application/json").status_code, 405)
        self.assertNotIn("_guru_active_at", self.client.session)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.client.get("/api/bootstrap/").status_code, 401)
