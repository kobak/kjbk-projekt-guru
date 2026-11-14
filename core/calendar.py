import base64
import hashlib
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote
from urllib.parse import urlencode, urlparse
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo
import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import CalendarLink, GoogleConnection
from .services import Problem

SCOPE = "https://www.googleapis.com/auth/calendar.events.owned"
PRIMARY_EVENTS = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

def cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256((settings.SECRET_KEY + ":calendar").encode()).digest()))

def event_url(event_id):
    return PRIMARY_EVENTS + "/" + quote(event_id, safe="")

def legacy_calendar_match(links, headers):
    # A previously synchronized GURU event in the new credential's primary
    # calendar proves continuity without asking for broader Calendar access.
    recent = links.order_by("-synced_version", "-attempted_at", "pk").values_list("pk", "event_id", "task_id")[:3]
    for link_id, event_id, task_id in list(recent):
        response = requests.get(event_url(event_id), headers=headers, timeout=(3, 5),
            params={"fields": "status,organizer(self),extendedProperties/private"})
        if response.status_code == 200:
            event = response.json()
            if (event.get("status") != "cancelled" and event.get("organizer", {}).get("self")
                    and event.get("extendedProperties", {}).get("private", {}).get("kozos_task") == str(task_id)):
                return link_id, event_id
    return None

def unlink_calendar(links, *, leave_events):
    if leave_events:
        links.update(event_id="", event_url="", enabled=False, error="", attempted_at=None)
    else:
        links.filter(enabled=True).update(enabled=False, error="")

def timed_event_range(task):
    zone = ZoneInfo(settings.TIME_ZONE)
    # The first occurrence wins during the autumn overlap. A nonexistent
    # spring time rolls forward by the size of the gap on the UTC round-trip.
    start_utc = datetime.combine(task.due_date, task.due_time, zone).astimezone(dt_timezone.utc)
    return start_utc.astimezone(zone), (start_utc + timedelta(minutes=30)).astimezone(zone)

def event_payload(task):
    result = {"summary": ("✓ " if task.status == "done" else "") + task.title,
        "description": f"{task.project_name}\n\n{task.description}\n\n{settings.APP_URL}/?task={task.id}",
        "source": {"title": "kjbk projekt guru", "url": f"{settings.APP_URL}/?task={task.id}"},
        "transparency": "transparent", "extendedProperties": {"private": {"kozos_task": str(task.id)}}}
    if task.project_id is None:
        result["visibility"] = "private"
    if task.due_time:
        start, end = timed_event_range(task)
        result["start"] = {"dateTime": start.isoformat(), "timeZone": settings.TIME_ZONE}
        result["end"] = {"dateTime": end.isoformat(), "timeZone": settings.TIME_ZONE}
    else:
        result["start"] = {"date": task.due_date.isoformat()}
        result["end"] = {"date": (task.due_date + timedelta(days=1)).isoformat()}
    return result

def event_dates(task):
    if not task.due_date:
        raise Problem("Előbb adj meg határidőt.")
    if task.due_time:
        start, end = timed_event_range(task)
        return start.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ"), end.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return task.due_date.strftime("%Y%m%d"), (task.due_date + timedelta(days=1)).strftime("%Y%m%d")

def template_url(task):
    start, end = event_dates(task)
    return "https://calendar.google.com/calendar/render?" + urlencode({"action": "TEMPLATE", "text": task.title,
        "dates": start + "/" + end, "ctz": settings.TIME_ZONE,
        "details": f"{task.project_name}\n\n{task.description[:700]}\n\n{settings.APP_URL}/?task={task.id}"})

def calendar_file(task):
    def escape(value):
        return value.replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
    def fold(line):
        pieces, current = [], b""
        for char in line:
            encoded = char.encode("utf-8")
            if len(current) + len(encoded) > 74:
                pieces.append(current.decode("utf-8"))
                current = b" "
            current += encoded
        pieces.append(current.decode("utf-8"))
        return "\r\n".join(pieces)
    start, end = event_dates(task)
    date_suffix = "" if task.due_time else ";VALUE=DATE"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Kozos//Projektkezelo//HU", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT", f"UID:{task.id}@{urlparse(settings.APP_URL).hostname}",
        "DTSTAMP:" + timezone.now().strftime("%Y%m%dT%H%M%SZ"),
        f"DTSTART{date_suffix}:{start}", f"DTEND{date_suffix}:{end}", "SUMMARY:" + escape(task.title),
        "DESCRIPTION:" + escape(f"{task.project_name}\n\n{task.description}\n\n{settings.APP_URL}/?task={task.id}"),
        "TRANSP:TRANSPARENT", "END:VEVENT", "END:VCALENDAR"]
    if task.project_id is None:
        lines.insert(-2, "CLASS:PRIVATE")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"

def access_token(connection):
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": cipher().decrypt(connection.encrypted_refresh_token.encode()).decode(),
        "grant_type": "refresh_token"}, timeout=15)
    if response.status_code != 200 or not response.json().get("access_token"):
        raise Problem("A Google-kapcsolat lejárt vagy nem elérhető. Csatlakoztasd újra a Beállításokban.", 502)
    return response.json()["access_token"]

def sync_link(link_id):
    user_id = CalendarLink.objects.filter(id=link_id).values_list("user_id", flat=True).first()
    if user_id is None:
        return False
    snapshot = GoogleConnection.objects.filter(user_id=user_id).first()
    token, token_error = None, None
    if snapshot:
        try:
            token = access_token(snapshot)
        except (Problem, requests.RequestException, ValueError, InvalidToken) as exc:
            token_error = exc

    # Keep the account and link stable during Calendar writes. Token exchange
    # can run before locking because it never writes to the calendar.
    with transaction.atomic():
        connection = GoogleConnection.objects.select_for_update().filter(user_id=user_id).first()
        link = CalendarLink.objects.select_for_update().filter(id=link_id).first()
        if link is None:
            return False
        task = link.task
        if connection and (not snapshot or connection.pk != snapshot.pk
                           or connection.encrypted_refresh_token != snapshot.encrypted_refresh_token):
            return False
        link.attempted_at = timezone.now()
        link.save(update_fields=["attempted_at"])
        try:
            if connection is None:
                raise GoogleConnection.DoesNotExist
            if token_error:
                raise token_error
            headers = {"Authorization": f"Bearer {token}"}
            if not link.event_id and link.enabled and not task.deleted and task.due_date:
                link.event_id = "k" + uuid.uuid4().hex
                link.save(update_fields=["event_id"])
            event_id = link.event_id
            if not event_id:
                link.synced_version, link.enabled, link.error = task.version, False, ""
                link.save()
                return True
            url = event_url(event_id)
            if not link.enabled or task.deleted or not task.due_date:
                response = requests.delete(url, headers=headers, timeout=15)
                if response.status_code not in (200, 204, 404, 410):
                    raise Problem("A naptáresemény törlése nem sikerült. A háttérfolyamat újrapróbálja.", 502)
                link.event_url = ""
                link.enabled = False
                link.event_id = ""
            else:
                payload = event_payload(task)
                # Persist the ID before network I/O; retries reuse it, re-adds use a new ID.
                response = requests.put(url, headers=headers, json=payload, timeout=15)
                if response.status_code in (404, 410):
                    payload["id"] = event_id
                    response = requests.post(PRIMARY_EVENTS, headers=headers, json=payload, timeout=15)
                    if response.status_code == 409:
                        response = requests.put(url, headers=headers, json=event_payload(task), timeout=15)
                if response.status_code not in (200, 201):
                    raise Problem("A Google Naptár mentése nem sikerült. A háttérfolyamat újrapróbálja.", 502)
                link.event_id = event_id
                link.event_url = response.json().get("htmlLink", "")
            link.synced_version = task.version
            link.error = ""
            link.save()
            GoogleConnection.objects.filter(id=connection.id).update(error="")
            return True
        except (Problem, requests.RequestException, ValueError, InvalidToken, GoogleConnection.DoesNotExist) as exc:
            link.error = exc.message if isinstance(exc, Problem) else "A Google Naptár nem elérhető. Ellenőrizd a kapcsolatot a Beállításokban."
            link.save(update_fields=["error", "attempted_at"])
            return False
