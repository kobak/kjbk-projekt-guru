import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from django.conf import settings
from django.db import transaction

from .models import Attachment, Task
from .services import Problem, activity


def picker_config():
    enabled = bool(settings.GOOGLE_PICKER_CLIENT_ID and settings.GOOGLE_PICKER_API_KEY and settings.GOOGLE_PICKER_APP_ID)
    return {
        "enabled": enabled,
        "client_id": settings.GOOGLE_PICKER_CLIENT_ID if enabled else "",
        "api_key": settings.GOOGLE_PICKER_API_KEY if enabled else "",
        "app_id": settings.GOOGLE_PICKER_APP_ID if enabled else "",
    }


def link_drive_file(task_id, user, data):
    if not picker_config()["enabled"]:
        raise Problem("A Google Drive-fájlválasztó Google-beállításai még hiányoznak.", 503)
    if set(data) - {"file_id", "resource_key", "access_token"}:
        raise Problem("Érvénytelen Drive-fájlválasztás.")
    file_id, resource_key, token = data.get("file_id"), data.get("resource_key", ""), data.get("access_token")
    if not isinstance(file_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", file_id):
        raise Problem("Érvénytelen Drive-fájlazonosító.")
    if not isinstance(resource_key, str) or resource_key and not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", resource_key):
        raise Problem("Érvénytelen Drive-fájlazonosító.")
    if not isinstance(token, str) or len(token) > 4096 or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
        raise Problem("Válaszd ki újra a fájlt a Google Drive-ból.")
    # Check the task before contacting Google, then lock and check it again on save.
    Task.objects.get(id=task_id, deleted=False, project__archived=False)
    headers = {"Authorization": f"Bearer {token}"}
    if resource_key:
        headers["X-Goog-Drive-Resource-Keys"] = f"{file_id}/{resource_key}"
    try:
        response = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}", headers=headers,
            params={"fields": "id,name,mimeType,webViewLink,resourceKey,trashed", "supportsAllDrives": "true"},
            timeout=(3, 10), allow_redirects=False)
        if response.status_code in (401, 403, 404):
            raise Problem("A fájl nem érhető el ezzel a Google-engedéllyel. Válaszd ki újra a Drive-fájlválasztóban.")
        if response.status_code != 200:
            raise Problem("A Google Drive most nem elérhető. Próbáld újra később.", 502)
        metadata = response.json()
    except (requests.RequestException, ValueError):
        raise Problem("A Google Drive most nem elérhető. Próbáld újra később.", 502)
    if (not isinstance(metadata, dict) or metadata.get("id") != file_id
            or not isinstance(metadata.get("name"), str) or not metadata["name"].strip()
            or not isinstance(metadata.get("mimeType"), str)):
        raise Problem("A Google Drive fájladatai nem olvashatók. Próbáld újra.", 502)
    if metadata.get("trashed") or metadata["mimeType"] == "application/vnd.google-apps.folder":
        raise Problem("Válassz egy használható fájlt; mappa vagy törölt fájl nem csatolható.")
    url = metadata.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"
    try:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.hostname not in ("drive.google.com", "docs.google.com")
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError()
        key = metadata.get("resourceKey") or resource_key
        if key and (not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", key)):
            raise ValueError()
        if key and not any(k == "resourcekey" for k, _ in parse_qsl(parsed.query)):
            url = urlunparse(parsed._replace(query=urlencode(parse_qsl(parsed.query) + [("resourcekey", key)])))
        if len(url) > 2000:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise Problem("A Google Drive érvénytelen fájlhivatkozást adott vissza.", 502)
    with transaction.atomic():
        task = Task.objects.select_for_update().get(id=task_id, deleted=False, project__archived=False)
        attachment, created = Attachment.objects.get_or_create(task=task, drive_file_hash=hashlib.sha256(file_id.encode()).hexdigest(),
            defaults={"user": user, "kind": "drive", "file": "", "size": 0, "drive_file_id": file_id,
                "name": metadata["name"].strip()[:255], "external_url": url})
        if created:
            activity(user, task, "Google Drive-fájlt csatolt")
    # The short-lived token is used only above and is never persisted.
    return {"ok": True, "created": created, "id": attachment.id}
