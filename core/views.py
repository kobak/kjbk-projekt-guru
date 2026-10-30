import hashlib
import json
import secrets
from datetime import timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode, urlparse
import requests
from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse, HttpResponse, FileResponse
from django.http.response import HttpResponseBase
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Workspace, Project, Task, ChecklistItem, Comment, Attachment, Notification, Activity, Invite, PushSubscription, GoogleConnection, CalendarLink
from .services import Problem, person, project_json, task_json, task_queryset, text, password_text, save_project, save_task, delete_task, notify, activity
from .calendar import SCOPE, cipher, sync_link, calendar_file
from .notifications import preference_json, save_preferences, email_configured
from .appearance import appearance_json, save_appearance
from .members import change_member_email

def locked_out(request, credentials=None, *args, **kwargs):
    return JsonResponse({"error": "Túl sok sikertelen belépés. Próbáld újra 30 perc múlva."}, status=429)

def api(methods=("GET",), admin=False, anonymous=False):
    def decorate(fn):
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return JsonResponse({"error": "Nem támogatott metódus."}, status=405)
            if not anonymous and not request.user.is_authenticated:
                return JsonResponse({"error": "Jelentkezz be."}, status=401)
            if admin and not request.user.is_staff:
                return JsonResponse({"error": "Ehhez adminisztrátori hozzáférés kell."}, status=403)
            try:
                if request.content_type == "application/json" and request.body:
                    request.data = json.loads(request.body)
                    if not isinstance(request.data, dict):
                        raise Problem("A kérésnek objektumnak kell lennie.")
                else:
                    request.data = {}
                result = fn(request, *args, **kwargs)
                return result if isinstance(result, HttpResponseBase) else JsonResponse(result)
            except Problem as e:
                return JsonResponse({"error": e.message}, status=e.status)
            except ObjectDoesNotExist:
                return JsonResponse({"error": "A kért adat nem található."}, status=404)
            except (ValidationError, ValueError, TypeError) as e:
                return JsonResponse({"error": "; ".join(e.messages) if isinstance(e, ValidationError) else "Érvénytelen adat vagy azonosító."}, status=400)
        return wrapper
    return decorate

@ensure_csrf_cookie
@api(anonymous=True)
def session(request):
    return {"user": person(request.user) if request.user.is_authenticated else None, "csrf": get_token(request),
        "appearance": appearance_json(request.user)}

@api(("GET", "PATCH"))
def appearance(request):
    if request.method == "PATCH":
        return save_appearance(request.user, request.data)
    return appearance_json(request.user)

@api(("POST",), anonymous=True)
def login(request):
    email = text(request.data, "email", 254, True).lower()
    user = authenticate(request, username=email, password=password_text(request.data))
    if not user:
        raise Problem("Hibás e-mail-cím vagy jelszó.", 401)
    auth_login(request, user)
    return {"user": person(user), "csrf": get_token(request)}

@api(("POST",))
def logout(request):
    auth_logout(request)
    return {"ok": True}

@api(("PATCH",))
def profile(request):
    user = request.user
    changed_fields = []
    if "name" in request.data:
        user.first_name = text(request.data, "name", 100, True)
        changed_fields.append("first_name")
    if request.data.get("password"):
        if not user.check_password(request.data.get("current_password", "")):
            raise Problem("A jelenlegi jelszó nem megfelelő.")
        password = password_text(request.data)
        validate_password(password, user)
        user.set_password(password)
        changed_fields.append("password")
    user.save(update_fields=changed_fields)
    update_session_auth_hash(request, user)
    return {"user": person(user)}

@api()
def bootstrap(request):
    ws = Workspace.objects.first()
    tasks = task_queryset().order_by("position", "-created_at")
    return {"workspace": ws.name if ws else "Közös munkatér", "user": person(request.user),
        "appearance": appearance_json(request.user),
        "members": [person(u) for u in User.objects.filter(is_active=True).order_by("id")],
        "projects": [project_json(p) for p in Project.objects.order_by("created_at")],
        "tasks": [task_json(t, request.user) for t in tasks],
        "notifications": [notification_json(n) for n in Notification.objects.filter(user=request.user)[:60]],
        "unread": Notification.objects.filter(user=request.user, read=False).count(),
        "activity": [{"id": a.id, "user": person(a.user), "text": a.text,
            "task_id": str(a.task_id) if a.task_id else None, "task_title": a.task.title if a.task else "",
            "created_at": a.created_at.isoformat()} for a in Activity.objects.select_related("user", "task")[:15]],
        "integrations": integration_state(request.user)}

def integration_state(user):
    connection = GoogleConnection.objects.filter(user=user).first()
    return {"google_configured": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        "google_connected": bool(connection), "google_error": connection.error if connection else "",
        "email_configured": email_configured(),
        "push_configured": bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY),
        "vapid_public_key": settings.VAPID_PUBLIC_KEY, "mcp_url": settings.APP_URL + "/mcp"}

@api(("POST", "PATCH"))
def projects(request, project_id=None):
    p = get_object_or_404(Project, id=project_id) if project_id else None
    return {"project": project_json(save_project(request.data, request.user, p))}

@api(("POST",))
def create_task(request):
    t = save_task(request.data, request.user)
    return {"task": task_json(task_queryset().get(id=t.id), request.user, True)}

@api(("GET", "PATCH", "DELETE"))
def task(request, task_id):
    if request.method == "PATCH":
        save_task(request.data, request.user, task_id)
    elif request.method == "DELETE":
        delete_task(task_id, request.data.get("version"), request.user)
        return {"ok": True}
    return {"task": task_json(get_object_or_404(task_queryset(), id=task_id), request.user, True)}

@api(("POST",))
def comments(request, task_id):
    t = get_object_or_404(Task, id=task_id, deleted=False, project__archived=False)
    body = text(request.data, "body", 10000, True)
    Comment.objects.create(task=t, user=request.user, body=body)
    recipients = {t.created_by_id, t.assignee_id} | set(t.comments.values_list("user_id", flat=True))
    for uid in recipients - {None, request.user.id}:
        notify(uid, t, f"{request.user.first_name or request.user.email} hozzászólt", t.title, kind=Notification.Kind.COMMENT)
    activity(request.user, t, "hozzászólt a feladathoz")
    return {"ok": True}

@api(("POST", "PATCH", "DELETE"))
def checklist(request, task_id, item_id=None):
    t = get_object_or_404(Task, id=task_id, deleted=False, project__archived=False)
    if request.method == "POST":
        ChecklistItem.objects.create(task=t, text=text(request.data, "text", 250, True))
    else:
        item = get_object_or_404(ChecklistItem, id=item_id, task=t)
        if request.method == "DELETE":
            item.delete()
        else:
            if "done" in request.data:
                if type(request.data["done"]) is not bool:
                    raise Problem("Érvénytelen állapot.")
                item.done = request.data["done"]
            if "text" in request.data:
                item.text = text(request.data, "text", 250, True)
            item.save()
    return {"ok": True}

@api(("POST",))
def attachments(request, task_id):
    t = get_object_or_404(Task, id=task_id, deleted=False, project__archived=False)
    f = request.FILES.get("file")
    if not f or f.size > settings.MAX_UPLOAD_BYTES:
        raise Problem("Válassz legfeljebb 25 MB méretű fájlt.")
    Attachment.objects.create(task=t, user=request.user, file=f, name=Path(f.name).name[:255], size=f.size)
    activity(request.user, t, "fájlt csatolt")
    return {"ok": True}

@api(("GET", "DELETE"))
def attachment(request, attachment_id):
    a = get_object_or_404(Attachment, id=attachment_id, task__deleted=False)
    if request.method == "DELETE":
        if a.user_id != request.user.id and not request.user.is_staff:
            raise Problem("Csak a feltöltő vagy az adminisztrátor törölheti a fájlt.", 403)
        a.file.delete(save=False)
        a.delete()
        return {"ok": True}
    response = FileResponse(a.file.open("rb"), as_attachment=True, filename=a.name, content_type="application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    return response

def notification_json(n):
    return {"id": n.id, "title": n.title, "body": n.body, "read": n.read,
        "task_id": str(n.task_id) if n.task_id else None, "created_at": n.created_at.isoformat()}

@api(("GET", "PATCH"))
def notification_preferences(request):
    if request.method == "PATCH":
        save_preferences(request.user, request.data)
    return preference_json(request.user)

@api(("POST",))
def read_notifications(request):
    qs = Notification.objects.filter(user=request.user)
    if request.data.get("id"):
        qs = qs.filter(id=request.data["id"])
    qs.update(read=True)
    return {"ok": True}

@api(("POST", "DELETE"))
def push_subscription(request):
    endpoint = request.data.get("endpoint", "")
    url = urlparse(endpoint)
    host = (url.hostname or "").lower()
    allowed = ("fcm.googleapis.com", "push.services.mozilla.com", "push.apple.com", "notify.windows.com")
    if len(endpoint) > 2000 or url.scheme != "https" or url.username or url.password or url.port not in (None, 443) or not any(host == h or host.endswith("." + h) for h in allowed):
        raise Problem("Nem támogatott push-szolgáltató.")
    if request.method == "DELETE":
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    else:
        keys = request.data.get("keys", {})
        if not isinstance(keys, dict) or any(not isinstance(keys.get(k), str) or not 10 < len(keys[k]) < 200 for k in ("p256dh", "auth")):
            raise Problem("Hiányzó push-kulcsok.")
        PushSubscription.objects.update_or_create(endpoint_hash=hashlib.sha256(endpoint.encode()).hexdigest(), defaults={"endpoint": endpoint, "user": request.user, "keys": keys})
    return {"ok": True}

@api(("GET", "POST", "DELETE"), admin=True)
def invites(request):
    if request.method == "GET":
        return {"invites": [{"id": i.id, "email": i.email, "expires_at": i.expires_at.isoformat()} for i in Invite.objects.filter(accepted_at=None, expires_at__gt=timezone.now())]}
    if request.method == "DELETE":
        Invite.objects.filter(id=request.data.get("id"), accepted_at=None).delete()
        return {"ok": True}
    from django.core.validators import validate_email
    email = text(request.data, "email", 254, True).lower()
    validate_email(email)
    if User.objects.filter(username=email, is_active=True).exists():
        raise Problem("Ez a felhasználó már tag.")
    if User.objects.filter(is_active=True).count() >= settings.MAX_MEMBERS:
        raise Problem("A munkatérben legfeljebb 5 aktív felhasználó lehet.")
    raw = secrets.token_urlsafe(32)
    Invite.objects.filter(email=email, accepted_at=None).delete()
    Invite.objects.create(email=email, token_hash=hashlib.sha256(raw.encode()).hexdigest(), created_by=request.user, expires_at=timezone.now() + timedelta(days=7))
    return {"url": settings.APP_URL + "/?invite=" + raw, "email": email}

@api(("GET", "POST"), anonymous=True)
def accept_invite(request, token):
    invite = get_object_or_404(Invite, token_hash=hashlib.sha256(token.encode()).hexdigest(), accepted_at=None, expires_at__gt=timezone.now())
    if request.method == "GET":
        return {"email": invite.email}
    with transaction.atomic():
        Workspace.objects.select_for_update().get_or_create(id=1)
        invite = Invite.objects.select_for_update().get(id=invite.id)
        if invite.accepted_at:
            raise Problem("Ezt a meghívót már felhasználták.")
        if User.objects.filter(is_active=True).count() >= settings.MAX_MEMBERS:
            raise Problem("A munkatér betelt.")
        if User.objects.filter(username=invite.email, is_active=True).exists():
            raise Problem("Ez a felhasználó már tag.")
        password = password_text(request.data)
        validate_password(password, User(username=invite.email, email=invite.email))
        name = text(request.data, "name", 100, True)
        user, _ = User.objects.get_or_create(username=invite.email, defaults={"email": invite.email})
        user.first_name, user.is_active = name, True
        user.set_password(password)
        user.save()
        invite.accepted_at = timezone.now()
        invite.save()
    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return {"user": person(user), "csrf": get_token(request)}

@api(("PATCH",), admin=True)
def member_email(request, user_id):
    return change_member_email(request.user, user_id, request.data)

@api(("POST",), admin=True)
def deactivate_member(request, user_id):
    if user_id == request.user.id:
        raise Problem("Saját magadat itt nem kapcsolhatod ki.")
    u = get_object_or_404(User, id=user_id, is_active=True)
    if u.is_staff:
        raise Problem("Másik adminisztrátort csak a szerver adminfelületén lehet kikapcsolni.")
    u.is_active = False
    u.save(update_fields=["is_active"])
    PushSubscription.objects.filter(user=u).delete()
    GoogleConnection.objects.filter(user=u).delete()
    from oauth2_provider.models import AccessToken, RefreshToken
    RefreshToken.objects.filter(user=u).delete()
    AccessToken.objects.filter(user=u).delete()
    return {"ok": True}

@login_required
def google_start(request):
    if not settings.GOOGLE_CLIENT_ID:
        return redirect("/?settings=1&google=unconfigured")
    state = secrets.token_urlsafe(32)
    request.session["google_state"] = {"value": state, "time": timezone.now().timestamp()}
    params = {"client_id": settings.GOOGLE_CLIENT_ID, "redirect_uri": settings.APP_URL + "/api/google/callback/",
        "response_type": "code", "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state}
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))

@login_required
def google_callback(request):
    saved = request.session.pop("google_state", {})
    if not saved or not secrets.compare_digest(saved.get("value", ""), request.GET.get("state", "")) or timezone.now().timestamp() - saved.get("time", 0) > 600:
        return redirect("/?settings=1&google=state_error")
    if request.GET.get("error") or not request.GET.get("code"):
        return redirect("/?settings=1&google=cancelled")
    try:
        response = requests.post("https://oauth2.googleapis.com/token", data={"code": request.GET["code"],
            "client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.APP_URL + "/api/google/callback/", "grant_type": "authorization_code"}, timeout=15)
        result = response.json()
        if response.status_code != 200 or not result.get("refresh_token") or SCOPE not in result.get("scope", "").split():
            return redirect("/?settings=1&google=error")
        GoogleConnection.objects.update_or_create(user=request.user, defaults={"encrypted_refresh_token": cipher().encrypt(result["refresh_token"].encode()).decode(), "error": ""})
        CalendarLink.objects.filter(user=request.user).update(attempted_at=None)
        return redirect("/?settings=1&google=connected")
    except (requests.RequestException, ValueError):
        return redirect("/?settings=1&google=error")

@api(("POST",))
def google_disconnect(request):
    if CalendarLink.objects.filter(user=request.user).exclude(event_id="").exists():
        raise Problem("Előbb távolítsd el a naptárból a hozzáadott feladatokat. Így nem maradnak hátra események.")
    GoogleConnection.objects.filter(user=request.user).delete()
    return {"ok": True}

@api(("GET", "DELETE"))
def mcp_connections(request):
    from oauth2_provider.models import Application, AccessToken, RefreshToken
    if request.method == "DELETE":
        app_id = request.data.get("id")
        RefreshToken.objects.filter(user=request.user, application_id=app_id).delete()
        AccessToken.objects.filter(user=request.user, application_id=app_id).delete()
        return {"ok": True}
    ids = AccessToken.objects.filter(user=request.user, expires__gt=timezone.now()).values_list("application_id", flat=True)
    return {"connections": [{"id": a.id, "name": a.name} for a in Application.objects.filter(id__in=ids)]}

@api(("POST", "DELETE"))
def task_calendar(request, task_id):
    t = get_object_or_404(Task, id=task_id, deleted=False)
    if not GoogleConnection.objects.filter(user=request.user).exists():
        raise Problem("Előbb csatlakoztasd a saját Google Naptáradat a Beállításokban.")
    if request.method == "POST" and not t.due_date:
        raise Problem("Előbb adj meg határidőt.")
    link, _ = CalendarLink.objects.get_or_create(task=t, user=request.user)
    link.enabled = request.method == "POST"
    link.attempted_at = None
    link.synced_version = 0
    link.save()
    success = sync_link(link.id)
    link.refresh_from_db()
    return {"ok": success, "error": link.error, "task": task_json(task_queryset().get(id=t.id), request.user, True)}

@api()
def task_calendar_file(request, task_id):
    t = get_object_or_404(Task.objects.select_related("project"), id=task_id, deleted=False)
    response = HttpResponse(calendar_file(t), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="kozos-feladat.ics"'
    return response

def spa(request, path=""):
    if path.startswith(("api/", "static/", "media/", "oauth/", ".well-known/")):
        return HttpResponse(status=404)
    index = settings.BASE_DIR / "frontend" / "dist" / "index.html"
    if not index.exists():
        return HttpResponse("A felület még nincs lefordítva. Futtasd: cd frontend && npm run build", status=503)
    response = HttpResponse(index.read_text(), content_type="text/html")
    response["Cache-Control"] = "no-cache"
    return response

def health(request):
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"ok": True})

def service_worker(request):
    response = FileResponse(open(settings.BASE_DIR / "frontend" / "public" / "sw.js", "rb"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response
