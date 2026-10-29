from django.conf import settings
from django.http import JsonResponse
import ipaddress

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
