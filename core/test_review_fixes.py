import hashlib
import uuid
from datetime import date, time, timedelta
from urllib.parse import parse_qs, urlencode, urlparse
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application, RefreshToken
from oauth2_provider.oauth2_validators import OAuth2Validator

from .calendar import SCOPE, calendar_file, cipher, event_payload, sync_link
from .models import CalendarLink, GoogleConnection, Project, PushSubscription, Task, Workspace


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], AXES_ENABLED=False,
                   GOOGLE_CLIENT_ID="calendar-test-client", GOOGLE_CLIENT_SECRET="calendar-test-secret")
class ReviewRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("first@example.com", is_staff=True)
        self.other = User.objects.create_user("second@example.com")
        self.client.force_login(self.user)
        self.project = Project.objects.create(name="Projekt")
        self.task = Task.objects.create(project=self.project, title="Határidő", created_by=self.user,
                                        due_date=date(2026, 11, 16))

    def application(self, name):
        return Application.objects.create(
            name=name, client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://client.example.com/callback",
        )

    def token_pair(self, app, user, age=timedelta(minutes=1), revoked=None):
        access = AccessToken.objects.create(user=user, application=app, scope="tasks:read",
                                            resource=[settings.APP_URL + "/mcp"],
                                            token=f"access-{app.name}-{user.pk}", expires=timezone.now() - age)
        raw_refresh = f"refresh-{app.name}-{user.pk}"
        RefreshToken.objects.create(user=user, application=app, access_token=access, token=raw_refresh,
                                    revoked=revoked, token_family=uuid.uuid4())
        return raw_refresh

    def refresh(self, app, raw_refresh):
        return Client().post("/oauth/token/", urlencode({
            "grant_type": "refresh_token", "client_id": app.client_id, "refresh_token": raw_refresh,
            "resource": settings.APP_URL + "/mcp",
        }), content_type="application/x-www-form-urlencoded")

    def test_mcp_lists_still_refreshable_connections_and_revokes_only_current_user(self):
        url = "/api/mcp/connections/"
        app = self.application("Expired access")
        raw = self.token_pair(app, self.user)
        other_raw = self.token_pair(app, self.other)
        self.token_pair(self.application("Expired refresh"), self.user, age=timedelta(days=31))
        self.token_pair(self.application("Revoked"), self.user, revoked=timezone.now())
        active = self.application("Active access")
        self.token_pair(active, self.user, age=-timedelta(minutes=1))
        self.assertEqual(self.client.get(url).json()["connections"],
                         [{"id": active.id, "name": active.name}, {"id": app.id, "name": app.name}])
        self.assertEqual(self.client.delete(url, {"id": app.id}, content_type="application/json").status_code, 200)
        self.assertEqual(self.refresh(app, raw).json()["error"], "invalid_grant")
        self.assertEqual(self.refresh(app, other_raw).status_code, 200)
        self.assertEqual(self.client.get(url).json()["connections"], [{"id": active.id, "name": active.name}])

    def test_mcp_refresh_checks_revocation_again_before_issuing_tokens(self):
        app = self.application("Revoked during refresh")
        raw = self.token_pair(app, self.user)
        validate = OAuth2Validator.validate_refresh_token

        def revoked_after_validation(validator, raw_token, client, request, *args, **kwargs):
            allowed = validate(validator, raw_token, client, request, *args, **kwargs)
            if allowed:
                self.client.delete("/api/mcp/connections/", {"id": app.id}, content_type="application/json")
            return allowed

        with patch.object(OAuth2Validator, "validate_refresh_token", revoked_after_validation):
            result = self.refresh(app, raw)
        self.assertEqual(result.json()["error"], "invalid_grant")
        self.assertFalse(AccessToken.objects.filter(application=app).exists())

    def test_mcp_client_revocation_reaches_a_rotated_refresh_token(self):
        app = self.application("Refresh rotation")
        raw = self.token_pair(app, self.user)
        rotated = self.refresh(app, raw)
        self.assertEqual(rotated.status_code, 200)
        revoke = Client().post("/oauth/revoke_token/", urlencode({
            "client_id": app.client_id, "token": raw, "token_type_hint": "refresh_token",
        }), content_type="application/x-www-form-urlencoded")
        self.assertEqual(revoke.status_code, 200)
        self.assertEqual(self.refresh(app, rotated.json()["refresh_token"]).json()["error"], "invalid_grant")

    def connect_google(self, subject, legacy_event_status=404, organizer_is_self=True):
        start = self.client.get("/api/google/connect/")
        params = parse_qs(urlparse(start.url).query)
        self.assertEqual(set(params["scope"][0].split()), {"openid", SCOPE})
        self.assertIn("select_account", params["prompt"][0].split())
        code = Mock(status_code=200, json=lambda: {
            "access_token": "google-test-access", "refresh_token": "new-refresh", "scope": f"openid {SCOPE}",
        })
        profile = Mock(status_code=200, json=lambda: {"sub": subject})
        event = Mock(status_code=legacy_event_status, json=lambda: {
            "status": "confirmed", "organizer": {"self": organizer_is_self},
            "extendedProperties": {"private": {"kozos_task": str(self.task.id)}},
        })
        with patch("core.views.requests.post", return_value=code), patch(
            "core.views.requests.get", side_effect=[profile, event],
        ) as get:
            response = self.client.get("/api/google/callback/", {"state": params["state"][0], "code": "test"})
        return response.url, get.call_args_list

    def existing_calendar(self, subject, event_id="ktestevent"):
        conn = GoogleConnection.objects.create(user=self.user, google_subject=subject,
            encrypted_refresh_token=cipher().encrypt(b"old-refresh").decode())
        link = CalendarLink.objects.create(task=self.task, user=self.user, event_id=event_id,
                                          synced_version=1 if event_id else 0)
        return conn, link

    def test_google_same_account_keeps_events_but_different_account_is_refused(self):
        conn, link = self.existing_calendar("first-subject")
        url, reads = self.connect_google("other-subject")
        self.assertTrue(url.endswith("google=account_mismatch"))
        self.assertEqual(len(reads), 1)
        conn.refresh_from_db()
        self.assertEqual(cipher().decrypt(conn.encrypted_refresh_token.encode()), b"old-refresh")
        self.assertTrue(self.connect_google("first-subject")[0].endswith("google=connected"))
        conn.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(cipher().decrypt(conn.encrypted_refresh_token.encode()), b"new-refresh")
        self.assertEqual(link.event_id, "ktestevent")

    def test_google_legacy_connection_requires_matching_event_on_primary_calendar(self):
        conn, _ = self.existing_calendar("")
        for status, owner in [(404, True), (200, False)]:
            with self.subTest(status=status, owner=owner):
                self.assertTrue(self.connect_google("some-subject", status, owner)[0].endswith("google=account_unverified"))
                conn.refresh_from_db()
                self.assertEqual(cipher().decrypt(conn.encrypted_refresh_token.encode()), b"old-refresh")
        url, reads = self.connect_google("verified-subject", 200)
        self.assertTrue(url.endswith("google=connected"))
        self.assertTrue(reads[1].args[0].endswith("/calendars/primary/events/ktestevent"))
        conn.refresh_from_db()
        self.assertEqual(conn.google_subject, "verified-subject")

    def test_calendar_sync_discards_token_if_connection_changes_during_exchange(self):
        conn, link = self.existing_calendar("first-subject")

        def reconnect(_connection):
            GoogleConnection.objects.filter(pk=conn.pk).update(
                encrypted_refresh_token=cipher().encrypt(b"new-refresh").decode(),
            )
            return "old-access-token"

        with patch("core.calendar.access_token", side_effect=reconnect), patch(
            "core.calendar.requests.put",
        ) as put:
            self.assertFalse(sync_link(link.pk))
        put.assert_not_called()
        link.refresh_from_db()
        self.assertIsNone(link.attempted_at)

    def test_google_can_switch_without_events_but_does_not_move_pending_adds(self):
        conn, link = self.existing_calendar("first-subject", event_id="")
        self.assertTrue(self.connect_google("other-subject")[0].endswith("google=connected"))
        conn.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(conn.google_subject, "other-subject")
        self.assertFalse(link.enabled)

    def test_google_requires_verified_identity_even_when_first_connecting(self):
        self.assertTrue(self.connect_google(None)[0].endswith("google=error"))
        self.assertFalse(GoogleConnection.objects.filter(user=self.user).exists())
        self.assertTrue(self.connect_google("first-subject")[0].endswith("google=connected"))

    def test_deactivating_a_member_detaches_calendar_and_disables_old_links(self):
        conn = GoogleConnection.objects.create(user=self.other, google_subject="other-subject",
            encrypted_refresh_token=cipher().encrypt(b"old-refresh").decode())
        link = CalendarLink.objects.create(task=self.task, user=self.other, event_id="ktestevent",
            event_url="https://calendar.google.com/calendar/event", error="Elavult hiba")
        with patch("core.calendar.requests.delete") as delete:
            self.assertEqual(self.client.post(f"/api/members/{self.other.pk}/deactivate/").status_code, 200)
        delete.assert_not_called()
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_active)
        self.assertFalse(GoogleConnection.objects.filter(pk=conn.pk).exists())
        link.refresh_from_db()
        self.assertEqual((link.enabled, link.event_id, link.event_url, link.error), (False, "", "", ""))

    def test_disconnect_requires_explicit_choice_if_old_calendar_is_unreachable(self):
        conn, link = self.existing_calendar("first-subject")
        path = "/api/google/disconnect/"
        self.assertEqual(self.client.post(path, {}, content_type="application/json").status_code, 409)
        self.assertTrue(GoogleConnection.objects.filter(pk=conn.pk).exists())
        self.assertEqual(self.client.post(path, {"leave_events": "yes"}, content_type="application/json").status_code, 400)
        with patch("core.calendar.requests.delete") as delete:
            self.assertEqual(self.client.post(path, {"leave_events": True}, content_type="application/json").status_code, 200)
        delete.assert_not_called()
        self.assertFalse(GoogleConnection.objects.filter(pk=conn.pk).exists())
        link.refresh_from_db()
        self.assertEqual(link.event_id, "")
        self.assertFalse(link.enabled)
        self.assertTrue(self.connect_google("other-subject")[0].endswith("google=connected"))

    def test_archived_task_cannot_add_calendar_event_but_can_remove_it(self):
        self.project.archived = True
        self.project.save(update_fields=["archived"])
        _, link = self.existing_calendar("first-subject")
        url = f"/api/tasks/{self.task.id}/calendar/"
        with patch("core.calendar.access_token", return_value="test-token"), patch(
            "core.calendar.requests.delete", return_value=Mock(status_code=204),
        ) as delete:
            self.assertEqual(self.client.post(url).status_code, 400)
            delete.assert_not_called()
            self.assertTrue(self.client.delete(url).json()["ok"])
            delete.assert_called_once()
        link.refresh_from_db()
        self.assertEqual(link.event_id, "")

    def test_timed_event_is_thirty_real_minutes_on_both_dst_transitions(self):
        self.task.due_time = time(2, 45)
        for day, start, end, start_utc, end_utc in [
            (date(2026, 3, 29), "03:45:00+02:00", "04:15:00+02:00", "20260329T014500Z", "20260329T021500Z"),
            (date(2026, 10, 25), "02:45:00+02:00", "02:15:00+01:00", "20261025T004500Z", "20261025T011500Z"),
        ]:
            with self.subTest(day=day):
                self.task.due_date = day
                event = event_payload(self.task)
                self.assertEqual(event["start"]["dateTime"], f"{day}T{start}")
                self.assertEqual(event["end"]["dateTime"], f"{day}T{end}")
                ics = calendar_file(self.task)
                self.assertIn(f"DTSTART:{start_utc}\r\n", ics)
                self.assertIn(f"DTEND:{end_utc}\r\n", ics)

    def test_archived_task_cannot_be_moved_to_an_active_project(self):
        self.project.archived = True
        self.project.save(update_fields=["archived"])
        target = Project.objects.create(name="Aktív")
        response = self.client.patch(f"/api/tasks/{self.task.id}/", {"version": self.task.version, "project_id": str(target.id)},
                                     content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("csak olvashatók", response.json()["error"])
        self.task.refresh_from_db()
        self.assertEqual(self.task.project_id, self.project.id)

    def test_invite_can_be_checked_and_accepted_with_code_only_in_body(self):
        Workspace.objects.create(id=1)
        invite = self.client.post("/api/invites/", {"email": "invited@example.com"},
                                  content_type="application/json").json()["url"]
        token = parse_qs(urlparse(invite).query)["invite"][0]
        client = Client(enforce_csrf_checks=True)
        csrf = client.get("/api/session/").json()["csrf"]
        self.assertEqual(client.post("/api/invite/check/", {"token": token}, content_type="application/json").status_code, 403)
        check = client.post("/api/invite/check/", {"token": token}, content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(check.json(), {"email": "invited@example.com"})
        accepted = client.post("/api/invite/accept/", {"token": token, "name": "Meghívott", "password": "Only-a-test-password!2026"},
                               content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(accepted.status_code, 200)
        expired = Client().post("/api/invite/check/", {"token": token}, content_type="application/json")
        self.assertEqual(expired.status_code, 404)
        self.assertIn("A meghívó lejárt", expired.json()["error"])

    def test_logout_removes_only_this_browser_subscription_and_ends_session(self):
        for user, suffix in [(self.user, "here"), (self.user, "elsewhere"), (self.other, "other-user")]:
            endpoint = "https://fcm.googleapis.com/" + suffix
            PushSubscription.objects.create(user=user, endpoint=endpoint,
                endpoint_hash=hashlib.sha256(endpoint.encode()).hexdigest(), keys={})
        result = self.client.post("/api/logout/", {"push_endpoint": "https://fcm.googleapis.com/here"},
                                  content_type="application/json")
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(self.client.get("/api/session/").json()["user"])
        self.assertCountEqual(PushSubscription.objects.values_list("endpoint", flat=True),
            ["https://fcm.googleapis.com/elsewhere", "https://fcm.googleapis.com/other-user"])

    def test_logout_removes_bound_subscription_without_browser_lookup(self):
        endpoint = "https://fcm.googleapis.com/this-device"
        keys = {"p256dh": "test-public-key", "auth": "test-auth-key"}
        self.assertEqual(self.client.post("/api/push/", {"endpoint": endpoint, "keys": keys},
                                          content_type="application/json").status_code, 200)
        other = Client()
        other.force_login(self.other)
        self.assertFalse(other.post("/api/push/status/", {"endpoint": endpoint},
                                    content_type="application/json").json()["enabled"])
        self.assertEqual(other.post("/api/push/", {"endpoint": endpoint, "keys": keys},
                                    content_type="application/json").status_code, 409)
        self.assertEqual(self.client.post("/api/logout/").status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(endpoint=endpoint).exists())

    def test_existing_push_subscription_can_be_adopted_by_its_own_session(self):
        endpoint = "https://fcm.googleapis.com/existing-device"
        sub = PushSubscription.objects.create(user=self.user, endpoint=endpoint, keys={})
        self.assertEqual(sub.session_hash, "")
        response = self.client.post("/api/push/status/", {"endpoint": endpoint}, content_type="application/json")
        self.assertTrue(response.json()["enabled"])
        sub.refresh_from_db()
        self.assertNotEqual(sub.session_hash, "")
        self.assertEqual(self.client.post("/api/logout/").status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(pk=sub.pk).exists())
