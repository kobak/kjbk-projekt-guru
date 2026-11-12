import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponseBadRequest
from oauth2_provider.http import OAuth2ResponseRedirect
from oauth2_provider.views import AuthorizationView


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
