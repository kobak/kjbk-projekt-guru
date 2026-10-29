from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from oauth2_provider.views import AuthorizationView


class MCPAuthorizationView(AuthorizationView):
    def redirect(self, redirect_to, application):
        # The toolkit validates client callbacks before reaching this hook.
        # Include the same RFC 9207 issuer on success, denial and error redirects.
        # Its built-in backend currently adds iss only on the success path.
        parts = urlsplit(redirect_to)
        query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "iss"]
        query.append(("iss", settings.APP_URL))
        return super().redirect(urlunsplit(parts._replace(query=urlencode(query))), application)
