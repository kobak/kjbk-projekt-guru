import json
from unittest.mock import Mock, patch

import requests
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings

from .models import Activity, Attachment, Project, Task


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], AXES_ENABLED=False,
    GOOGLE_PICKER_CLIENT_ID="test-client.apps.googleusercontent.com", GOOGLE_PICKER_API_KEY="test-picker-key",
    GOOGLE_PICKER_APP_ID="123456789")
class DriveAttachmentTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner@example.com", email="owner@example.com", is_staff=True)
        self.member = User.objects.create_user(username="member@example.com", email="member@example.com")
        self.other = User.objects.create_user(username="other@example.com", email="other@example.com")
        self.project = Project.objects.create(name="Drive-próba")
        self.task = Task.objects.create(project=self.project, title="Közös feladat", created_by=self.owner)
        self.url = f"/api/tasks/{self.task.id}/drive-attachments/"
        self.client.force_login(self.member)
        self.metadata = {"id": "DriveFile_AbC123", "name": "Projektterv", "mimeType": "application/vnd.google-apps.document",
            "webViewLink": "https://docs.google.com/document/d/DriveFile_AbC123/edit", "trashed": False}
        self.get = patch("core.drive.requests.get").start()
        self.addCleanup(patch.stopall)
        self.get.return_value = Mock(status_code=200, json=Mock(return_value=self.metadata))

    def post(self, data=None, client=None):
        return (client or self.client).post(self.url, json.dumps(data or {
            "file_id": "DriveFile_AbC123", "access_token": "test-only-token", "resource_key": ""}), content_type="application/json")

    def test_config_is_authenticated_and_contains_no_client_secret_or_tokens(self):
        response = self.client.get("/api/drive/config/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"enabled", "client_id", "api_key", "app_id"})
        self.assertTrue(response.json()["enabled"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(Client().get("/api/drive/config/").status_code, 401)
        with override_settings(GOOGLE_PICKER_APP_ID=""):
            self.assertEqual(self.client.get("/api/drive/config/").json(),
                {"enabled": False, "client_id": "", "api_key": "", "app_id": ""})

    def test_selection_stores_verified_metadata_and_link_without_file_or_token(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["created"])
        attachment = Attachment.objects.get()
        self.assertEqual((attachment.kind, attachment.name, attachment.user_id), ("drive", "Projektterv", self.member.id))
        self.assertFalse(attachment.file)
        self.assertEqual(attachment.drive_file_id, self.metadata["id"])
        self.assertEqual(attachment.external_url, self.metadata["webViewLink"])
        self.assertNotIn("test-only-token", json.dumps(attachment.__dict__, default=str))
        self.assertEqual(Activity.objects.count(), 1)
        self.get.assert_called_once()
        args, kwargs = self.get.call_args
        self.assertEqual(args, ("https://www.googleapis.com/drive/v3/files/DriveFile_AbC123",))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-only-token")
        self.assertFalse(kwargs["allow_redirects"])
        self.assertNotIn("alt", kwargs["params"])
        self.assertEqual(kwargs["params"]["supportsAllDrives"], "true")
        self.task.refresh_from_db()
        self.assertEqual(self.task.version, 1)

    def test_resource_key_is_preserved_in_request_and_link(self):
        self.metadata["resourceKey"] = "resourceKey_123"
        response = self.post({"file_id": self.metadata["id"], "access_token": "test-only-token", "resource_key": "resourceKey_123"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("resourcekey=resourceKey_123", Attachment.objects.get().external_url)
        self.assertEqual(self.get.call_args.kwargs["headers"]["X-Goog-Drive-Resource-Keys"], "DriveFile_AbC123/resourceKey_123")

    def test_reselecting_same_file_deduplicates_without_changing_original_author(self):
        first = self.post().json()
        self.client.force_login(self.other)
        second = self.post().json()
        self.assertEqual(first["id"], second["id"])
        self.assertFalse(second["created"])
        self.assertEqual(Attachment.objects.count(), 1)
        self.assertEqual(Attachment.objects.get().user_id, self.member.id)
        self.assertEqual(Activity.objects.count(), 1)

    def test_file_ids_are_case_sensitive_even_on_mariadb(self):
        self.post()
        self.metadata["id"] = "DriveFile_abc123"
        response = self.post({"file_id": self.metadata["id"], "access_token": "test-only-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attachment.objects.count(), 2)

    def test_existing_uploads_and_drive_links_appear_together_for_the_team(self):
        self.post()
        for name in ("first.txt", "second.txt"):
            Attachment.objects.create(task=self.task, user=self.member, file=f"attachments/{name}", name=name, size=12)
        self.client.force_login(self.other)
        task = self.client.get(f"/api/tasks/{self.task.id}/").json()["task"]
        self.assertEqual(task["attachment_count"], 3)
        self.assertEqual(sorted(a["kind"] for a in task["attachments"]), ["drive", "file", "file"])
        self.assertTrue(all(not a["can_delete"] for a in task["attachments"]))

    def test_unlink_only_removes_reference_and_never_deletes_from_drive(self):
        self.post()
        attachment = Attachment.objects.get()
        self.get.reset_mock()
        with patch("django.db.models.fields.files.FieldFile.delete") as delete_file, patch("core.drive.requests.delete") as delete_drive:
            response = self.client.delete(f"/api/attachments/{attachment.id}/")
        self.assertEqual(response.status_code, 200)
        delete_file.assert_not_called()
        delete_drive.assert_not_called()
        self.get.assert_not_called()
        self.assertFalse(Attachment.objects.exists())

    def test_only_attacher_or_admin_can_unlink_and_archived_is_read_only(self):
        self.post()
        attachment = Attachment.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.delete(f"/api/attachments/{attachment.id}/").status_code, 403)
        self.client.force_login(self.owner)
        self.project.archived = True
        self.project.save()
        self.assertEqual(self.client.delete(f"/api/attachments/{attachment.id}/").status_code, 400)
        self.project.archived = False
        self.project.save()
        self.assertEqual(self.client.delete(f"/api/attachments/{attachment.id}/").status_code, 200)

    def test_legacy_download_route_redirects_drive_links_after_authentication(self):
        self.post()
        attachment = Attachment.objects.get()
        url = f"/api/attachments/{attachment.id}/download/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.metadata["webViewLink"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertEqual(Client().get(url).status_code, 401)

    def test_unauthenticated_csrf_and_missing_config_never_contact_google(self):
        self.assertEqual(self.post(client=Client()).status_code, 401)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.member)
        self.assertEqual(self.post(client=client).status_code, 403)
        with override_settings(GOOGLE_PICKER_API_KEY=""):
            self.assertEqual(self.post().status_code, 503)
        self.get.assert_not_called()

    def test_invalid_ids_tokens_urls_and_cross_user_payloads_are_rejected(self):
        base = {"file_id": self.metadata["id"], "access_token": "test-only-token"}
        for changes in [{"file_id": "../files"}, {"file_id": "https://evil.example/file"}, {"file_id": True},
                {"access_token": "a\r\nb"}, {"access_token": ""}, {"resource_key": "bad/value"},
                {"user_id": self.other.id}, {"url": "javascript:alert(1)"}, {"name": "Forged title"}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.post({**base, **changes}).status_code, 400)
        self.get.assert_not_called()
        self.assertFalse(Attachment.objects.exists())

    def test_unavailable_google_and_invalid_responses_do_not_save_or_leak_provider_details(self):
        for status in (401, 403, 404, 429, 500, 302):
            with self.subTest(status=status):
                self.get.return_value.status_code = status
                response = self.post()
                self.assertIn(response.status_code, (400, 502))
                self.assertNotIn("test-only-token", response.content.decode())
                self.assertFalse(Attachment.objects.exists())
        self.get.side_effect = requests.Timeout("test-only-token")
        self.assertEqual(self.post().status_code, 502)
        self.assertFalse(Attachment.objects.exists())

    def test_folder_trashed_wrong_id_and_unsafe_provider_url_are_rejected(self):
        original = dict(self.metadata)
        for changes in [{"mimeType": "application/vnd.google-apps.folder"}, {"trashed": True},
                {"id": "different-file"}, {"name": ""}, {"webViewLink": "javascript:alert(1)"},
                {"webViewLink": "https://docs.google.com.evil.example/file"},
                {"webViewLink": "https://user:password@docs.google.com/file"}, {"resourceKey": "bad/key"}]:
            with self.subTest(changes=changes):
                self.get.return_value.json.return_value = {**original, **changes}
                self.assertIn(self.post().status_code, (400, 502))
                self.assertFalse(Attachment.objects.exists())
        self.get.return_value.json.side_effect = ValueError("test-invalid-json")
        self.assertEqual(self.post().status_code, 502)

    def test_archiving_or_deleting_during_lookup_cannot_add_attachment(self):
        def deleted_while_fetching(*args, **kwargs):
            Task.objects.filter(id=self.task.id).update(deleted=True)
            return Mock(status_code=200, json=Mock(return_value=self.metadata))
        self.get.side_effect = deleted_while_fetching
        self.assertEqual(self.post().status_code, 404)
        self.assertFalse(Attachment.objects.exists())
        self.get.reset_mock()
        self.assertEqual(self.post().status_code, 404)
        self.get.assert_not_called()

    def test_database_rejects_missing_source_and_duplicate_drive_reference(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attachment.objects.create(task=self.task, user=self.member, name="Missing source", size=0)
        self.post()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attachment.objects.create(task=self.task, user=self.member, kind="drive", name="Duplicate", size=0,
                drive_file_id=self.metadata["id"], external_url=self.metadata["webViewLink"])

    def test_spa_supports_restricted_picker_only_when_configured(self):
        response = self.client.get("/")
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin-allow-popups")
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertEqual(self.client.get("/api/session/")["Referrer-Policy"], "same-origin")
        with override_settings(GOOGLE_PICKER_API_KEY=""):
            response = self.client.get("/")
            self.assertNotEqual(response.get("Cross-Origin-Opener-Policy"), "same-origin-allow-popups")
            self.assertEqual(response["Referrer-Policy"], "same-origin")
