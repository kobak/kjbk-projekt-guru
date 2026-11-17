"""Local, disposable fixture for the Xcode UI test. Only binds to loopback."""
import json
import os
import signal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
from uuid import UUID

device = str(UUID(sys.argv[1])).upper()
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ.update(DJANGO_SETTINGS_MODULE="config.settings", DEBUG="true", DATABASE_URL="",
                  SECRET_KEY="simulator-fixture-only", APP_URL="http://127.0.0.1:8021",
                  ALLOWED_HOSTS="127.0.0.1,localhost", NOTIFICATION_EMAIL_ENABLED="false")
from django.conf import settings
from django.core.management import call_command
import django

def end_fixture(*_):
    raise SystemExit(0)


signal.signal(signal.SIGTERM, end_fixture)
task_id = "ce179143-33fc-49ed-9663-48a5cb65615b"
with tempfile.TemporaryDirectory(prefix="guru-ios-") as temp:
    settings.DATABASES["default"]["NAME"] = Path(temp, "demo.sqlite3")
    settings.MEDIA_ROOT = Path(temp, "media")
    settings.APNS_KEY_FILE = settings.VAPID_PRIVATE_KEY = settings.GOOGLE_CLIENT_ID = ""
    settings.STATIC_ROOT = Path(temp, "static")
    django.setup()
    from core.models import Task
    call_command("migrate", verbosity=0)
    call_command("seed_demo", verbosity=0)
    task = Task.objects.first()
    Task.objects.create(pk=task_id, project=task.project, created_by=task.created_by, title="Szimulátoros push megnyitása")
    class PushHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/push":
                self.send_error(404)
                return
            result = subprocess.run(["xcrun", "simctl", "push", device, "com.kjbkinfinity.guru.ios", "-"],
                input=json.dumps({"aps": {"alert": {"title": "GURU távoli próba", "body": "Feladat megnyitása"}, "sound": "default"},
                                  "task_id": task_id}), text=True, timeout=15)
            self.send_response(200 if result.returncode == 0 else 502)
            self.end_headers()
    helper = HTTPServer(("127.0.0.1", 8022), PushHandler)
    Thread(target=helper.serve_forever, daemon=True).start()
    call_command("runserver", "127.0.0.1:8021", use_reloader=False)
