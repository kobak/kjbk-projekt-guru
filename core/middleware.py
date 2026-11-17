from django.conf import settings
from django.http import JsonResponse
import ipaddress
import time

class ActiveSessionMiddleware:
    """Renew the existing login on visible app activity, at most once an hour.

    Native background notification polling deliberately cannot keep an unused
    account signed in. Session keys stay stable for the native cookie bridge.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (request.method == "GET" and request.path in ("/api/session/", "/api/bootstrap/")
                and 200 <= response.status_code < 300 and request.user.is_authenticated):
            now = int(time.time())
            if now - request.session.get("_guru_active_at", 0) >= 3600:
                request.session["_guru_active_at"] = now
        return response

class TrustedProxyMiddleware:
    """Apache appends the actual client to X-Forwarded-For; accept only its last hop on loopback."""
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        if request.META.get("REMOTE_ADDR") in ("127.0.0.1", "::1"):
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
            try:
                request.META["REMOTE_ADDR"] = str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
        return self.get_response(request)

class OAuthResourceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        if request.path.startswith("/oauth/"):
            resource = request.GET.get("resource") or request.POST.get("resource")
            if resource and resource != settings.APP_URL + "/mcp":
                return JsonResponse({"error": "invalid_target"}, status=400)
        response = self.get_response(request)
        if request.path.startswith(("/api/", "/oauth/", "/mcp", "/.well-known/")):
            response["Cache-Control"] = "no-store"
        if request.path.startswith(("/oauth/token", "/oauth/register", "/oauth/revoke", "/.well-known/", "/mcp")):
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, MCP-Protocol-Version, Accept"
            response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE"
            response["Access-Control-Expose-Headers"] = "WWW-Authenticate"
        return response
