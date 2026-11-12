import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponseBadRequest
from oauthlib.oauth2 import InvalidGrantError
from oauth2_provider.http import OAuth2ResponseRedirect
from oauth2_provider.models import RefreshToken
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.views import AuthorizationView


class RevokedRefreshGrant(InvalidGrantError):
    @property
    def headers(self):
        return {**super().headers, "Content-Type": "application/json",
                "Cache-Control": "no-store", "Pragma": "no-cache"}


class MCPOAuthValidator(OAuth2Validator):
    def _save_bearer_token(self, token, request, *args, **kwargs):
        # Share a lock with the connection settings. Validation may have succeeded
        # before the user revoked this connection or another request rotated it.
        refresh = getattr(request, "refresh_token_instance", None)
        if refresh is not None:
            User.objects.select_for_update().get(pk=refresh.user_id)
            if not RefreshToken.objects.filter(
                pk=refresh.pk, revoked__isnull=True, access_token__isnull=False,
            ).exists():
                raise RevokedRefreshGrant(request=request)
        return super()._save_bearer_token(token, request, *args, **kwargs)


def is_loopback_callback(uri):
    if not uri or "\\" in uri or any(c.isspace() or ord(c) < 32 for c in uri):
        return False
    try:
        parts = urlsplit(uri)
        return (
            parts.scheme == "http"
            and "#" not in uri
            and re.fullmatch(
                r"(?:127\.0\.0\.1|localhost|\[::1\])(?::[0-9]+)?",
                parts.netloc,
                flags=re.IGNORECASE | re.ASCII,
            ) is not None
            and parts.port != 0
        )
    except ValueError:
        return False


class MCPAuthorizationView(AuthorizationView):
    def redirect(self, redirect_to, application):
        parts = urlsplit(redirect_to)
        callback_data = self.request.POST if self.request.method == "POST" else self.request.GET
        callback = callback_data.get("redirect_uri", "")
        if self.request.method == "POST" or parts.scheme == "http":
            # The toolkit's denial path can reach this hook without validating the form callback.
            try:
                callback_parts = urlsplit(callback)
                matches_callback = (
                    application is not None
                    and (parts.scheme, parts.netloc, parts.path)
                    == (callback_parts.scheme, callback_parts.netloc, callback_parts.path)
                    and application.redirect_uri_allowed(callback)
                )
            except ValueError:
                matches_callback = False
            if not matches_callback:
                return HttpResponseBadRequest("Érvénytelen OAuth-visszahívási cím.")

        # The toolkit adds the issuer on success. Error and denial redirects need it too.
        query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "iss"]
        query.append(("iss", settings.APP_URL))
        destination = urlunsplit(parts._replace(query=urlencode(query)))
        if parts.scheme == "http":
            if application.client_type != application.CLIENT_PUBLIC or not is_loopback_callback(callback):
                return HttpResponseBadRequest("Érvénytelen OAuth-visszahívási cím.")
            return OAuth2ResponseRedirect(destination, ["http"])
        return super().redirect(destination, application)
