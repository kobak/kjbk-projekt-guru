import json

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from .models import AppearancePreference, Workspace
from .appearance import DEFAULTS


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost"], AXES_ENABLED=False)
class AppearanceTests(TestCase):
    def setUp(self):
        Workspace.objects.create(id=1)
        self.alice = User.objects.create_user(username="alice@example.com", email="alice@example.com")
        self.bob = User.objects.create_user(username="bob@example.com", email="bob@example.com")
        self.client.force_login(self.alice)

    def choose(self, value, client=None):
        return (client or self.client).patch("/api/appearance/", json.dumps(value), content_type="application/json")

    def test_default_is_system_without_creating_a_preference_on_read(self):
        result = self.client.get("/api/appearance/").json()
        self.assertEqual(result, {**DEFAULTS, "updated_at": None})
        self.assertFalse(AppearancePreference.objects.exists())
        self.assertEqual(Client().get("/api/session/").json()["appearance"]["theme"], "system")

    def test_all_three_choices_persist_across_sessions_and_devices(self):
        second_device = Client()
        second_device.force_login(self.alice)
        for theme in ("dark", "light", "system"):
            response = self.choose({"theme": theme})
            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(response.json()["updated_at"])
            self.assertEqual(second_device.get("/api/appearance/").json()["theme"], theme)
            self.assertEqual(second_device.get("/api/session/").json()["appearance"]["theme"], theme)

    def test_users_cannot_change_another_accounts_appearance(self):
        self.choose({"theme": "dark"})
        bob_client = Client()
        bob_client.force_login(self.bob)
        self.assertEqual(bob_client.get("/api/appearance/").json()["theme"], "system")
        self.assertEqual(self.choose({"theme": "light", "user_id": self.bob.id}).status_code, 400)
        self.assertFalse(AppearancePreference.objects.filter(user=self.bob).exists())
        self.assertEqual(self.client.get("/api/appearance/").json()["theme"], "dark")

    def test_invalid_choices_are_rejected_without_writes(self):
        for data in ({"theme": "sepia"}, {"theme": True}, {"theme": None}, {"theme": ["dark"]}, {}, {"theme": "dark", "extra": True}):
            with self.subTest(data=data):
                self.assertEqual(self.choose(data).status_code, 400)
        self.assertFalse(AppearancePreference.objects.exists())

    def test_login_and_csrf_are_required_to_change_theme(self):
        self.assertEqual(Client().get("/api/appearance/").status_code, 401)
        self.assertEqual(self.choose({"theme": "dark"}, Client()).status_code, 401)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.alice)
        self.assertEqual(self.choose({"theme": "dark"}, protected).status_code, 403)

    def test_bootstrap_contains_only_own_appearance_and_auth_pages_render_it(self):
        self.choose({"theme": "dark"})
        result = self.client.get("/api/bootstrap/").json()
        self.assertEqual(result["appearance"]["theme"], "dark")
        self.assertTrue(all("appearance" not in member and "theme" not in member for member in result["members"]))
        native = self.client.get("/accounts/login/")
        self.assertEqual(native.status_code, 200)
        self.assertContains(native, 'window.GuruAppearance.apply("dark")')
        self.assertContains(native, "kjbk-infinity-negative.png")

    def test_personal_task_view_defaults_and_partial_updates(self):
        self.assertEqual(self.client.get("/api/appearance/").json(), {**DEFAULTS, "updated_at": None})
        self.choose({"theme": "dark", "font_size": "large", "density": "spacious"})
        response = self.choose({"default_view": "board", "list_sort": "priority", "show_completed": True})
        self.assertEqual(response.status_code, 200)
        stored = self.client.get("/api/session/").json()["appearance"]
        self.assertEqual({key: stored[key] for key in DEFAULTS}, {"theme": "dark", "font_size": "large", "density": "spacious", "default_view": "board", "list_sort": "priority", "show_completed": True})
        other = Client()
        other.force_login(self.bob)
        self.assertEqual(other.get("/api/appearance/").json(), {**DEFAULTS, "updated_at": None})

    def test_view_preferences_validate_types_and_reject_all_changes_atomically(self):
        invalid = [{"default_view": "calendar"}, {"density": "dense"}, {"font_size": "small"}, {"list_sort": "title"},
            {"show_completed": 1}, {"show_completed": "false"}, {"font_size": "large", "show_completed": None},
            {"default_view": "list", "user_id": self.bob.id}]
        for value in invalid:
            with self.subTest(value=value): self.assertEqual(self.choose(value).status_code, 400)
        self.assertFalse(AppearancePreference.objects.exists())

    def test_sort_and_visibility_survive_new_device_and_theme_changes(self):
        for sorting in ("due", "priority", "created", "manual"):
            self.assertEqual(self.choose({"list_sort": sorting}).status_code, 200)
        self.choose({"show_completed": True, "default_view": "board"})
        self.choose({"theme": "light"})
        device = Client()
        device.force_login(self.alice)
        data = device.get("/api/bootstrap/").json()["appearance"]
        self.assertEqual(data["list_sort"], "manual")
        self.assertTrue(data["show_completed"])
        self.assertEqual(data["default_view"], "board")
