import json
from datetime import timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from jwcrypto import jwk, jwt

from .apple_push import deliver, provider_token
from .models import AppleDevice, AppleDelivery, Project, Task
from .notifications import save_preferences
from .services import notify


@override_settings(SECURE_SSL_REDIRECT=False, AXES_ENABLED=False, ALLOWED_HOSTS=["testserver"],
                   APNS_TEAM_ID="test-team", APNS_KEY_ID="test-key", APNS_KEY_FILE="unused-test-key.p8",
                   APNS_ENVIRONMENT="sandbox", APNS_TOPIC="com.example.guru")
class ApplePushTests(TestCase):
    endpoint = "/api/apple/device/"
    token = "ab" * 32

    def setUp(self):
        self.user = User.objects.create_user(username="tester")
        self.client.force_login(self.user)
        self.task = Task.objects.create(project=Project.objects.create(name="Projekt"), title="Bizalmas feladat",
                                        created_by=self.user, assignee=self.user)
        self.http = Mock(spec=httpx.Client)
        self.http.post.return_value = httpx.Response(200)

    def register(self, client=None, **overrides):
        data = {"environment": "sandbox", "user_id": self.user.pk, "token": self.token, **overrides}
        return (client or self.client).post(self.endpoint, data, content_type="application/json")

    def emit(self):
        notify(self.user.pk, self.task, "Új feladatot kaptál", self.task.title, "unique", kind="task_assigned")

    def send(self, pk):
        with patch("core.apple_push.provider_token", return_value="test-signed-token"):
            deliver(self.http, pk)

    def test_session_csrf_and_environment(self):
        self.assertEqual(Client().get(self.endpoint).status_code, 401)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(self.register(csrf).status_code, 403)
        self.assertEqual(self.register(environment="production").status_code, 409)
        self.assertEqual(self.register(user_id=self.user.pk + 1).status_code, 409)
        self.assertEqual(self.register(token="../oops").status_code, 400)
        with self.settings(APNS_KEY_FILE=""):
            self.assertEqual(self.register().status_code, 503)
            self.assertFalse(self.client.get(self.endpoint).json()["configured"])
        self.assertEqual(AppleDevice.objects.count(), 0)

    def test_device_renewal_and_logout(self):
        self.assertEqual(self.register().status_code, 200)
        self.register(token="cd" * 64)
        self.assertEqual(AppleDevice.objects.get().token, "cd" * 64)
        self.assertTrue(self.client.get(self.endpoint).json()["enabled"])
        self.emit()
        self.assertEqual(AppleDelivery.objects.count(), 1)
        self.client.post("/api/logout/", {}, content_type="application/json")
        self.assertFalse(AppleDelivery.objects.exists())
        self.assertFalse(AppleDevice.objects.exists())

    def test_one_copy_per_device_transient_failure_and_invalid_token(self):
        other = Client()
        other.force_login(self.user)
        self.register()
        self.register(other, token="bc" * 32)
        self.emit()
        self.emit()
        first, second = AppleDelivery.objects.order_by("pk")
        self.send(first.pk)
        args, kwargs = self.http.post.call_args
        self.assertEqual(args[0], "https://api.sandbox.push.apple.com/3/device/" + self.token)
        self.assertEqual(kwargs["headers"]["apns-topic"], "com.example.guru")
        self.assertEqual(kwargs["headers"]["apns-push-type"], "alert")
        self.assertEqual(kwargs["json"]["task_id"], str(self.task.pk))
        self.assertNotIn(self.task.title, json.dumps(kwargs["json"], ensure_ascii=False))
        self.http.post.return_value = httpx.Response(503, json={"reason": "ServiceUnavailable"})
        self.send(second.pk)
        remaining = AppleDelivery.objects.get()
        self.assertEqual(remaining.pk, second.pk)
        self.assertEqual(remaining.attempts, 1)
        self.assertGreater(remaining.next_attempt_at, timezone.now())
        self.send(second.pk)
        self.assertEqual(self.http.post.call_count, 2)
        AppleDelivery.objects.filter(pk=second.pk).update(next_attempt_at=timezone.now())
        self.http.post.return_value = httpx.Response(410, json={"reason": "Unregistered"})
        self.send(second.pk)
        self.assertEqual(AppleDevice.objects.count(), 1)
        self.assertFalse(AppleDelivery.objects.exists())

    def test_live_token_cannot_be_claimed_by_another_user(self):
        self.register()
        other_user = User.objects.create_user(username="other")
        other = Client()
        other.force_login(other_user)
        self.assertEqual(self.register(other, user_id=other_user.pk).status_code, 409)
        self.assertEqual(AppleDevice.objects.get().user_id, self.user.pk)
        self.client.post("/api/logout/", {}, content_type="application/json")
        self.assertEqual(self.register(other, user_id=other_user.pk).status_code, 200)
        self.assertEqual(AppleDevice.objects.get().user_id, other_user.pk)

    def test_private_and_opted_out_not_sent(self):
        self.register()
        self.emit()
        d = AppleDelivery.objects.get()
        save_preferences(self.user, {"preferences": {"task_assigned": {"push": False}}})
        self.send(d.pk)
        self.assertFalse(AppleDelivery.objects.exists())
        save_preferences(self.user, {"preferences": {"task_assigned": {"push": True}}})
        notify(self.user.pk, self.task, "Teszt", kind="task_assigned")
        self.task.project = None
        self.task.created_by = User.objects.create_user(username="owner")
        self.task.save()
        self.send(AppleDelivery.objects.get().pk)
        self.http.post.assert_not_called()

    def test_expired_or_invalidated_session_cannot_receive(self):
        self.register()
        self.emit()
        Session.objects.update(expire_date=timezone.now() - timedelta(seconds=1))
        self.send(AppleDelivery.objects.get().pk)
        self.assertFalse(AppleDevice.objects.exists())
        self.client.force_login(self.user)
        self.register()
        notify(self.user.pk, self.task, "Teszt", kind="task_assigned")
        self.user.set_password("another-test-password")
        self.user.save()
        self.send(AppleDelivery.objects.get().pk)
        self.assertFalse(AppleDevice.objects.exists())
        self.http.post.assert_not_called()

    def test_disable_removes_only_this_device_and_its_queue(self):
        self.register()
        other = Client()
        other.force_login(self.user)
        self.register(other, token="de" * 32)
        self.emit()
        self.client.delete(self.endpoint, {"user_id": self.user.pk}, content_type="application/json")
        self.assertEqual(AppleDelivery.objects.count(), 1)
        self.assertEqual(AppleDevice.objects.get().token, "de" * 32)

    def test_provider_signs_es256_with_matching_team_and_key(self):
        key = jwk.JWK.generate(kty="EC", crv="P-256")
        with TemporaryDirectory() as temp:
            path = Path(temp, "test.p8")
            path.write_bytes(key.export_to_pem(private_key=True, password=None))
            signed = provider_token("team", "key", str(path), 42)
            token = jwt.JWT(jwt=signed, key=key, algs=["ES256"])
            self.assertEqual(json.loads(token.claims)["iss"], "team")
            self.assertEqual(token.token.jose_header["kid"], "key")
