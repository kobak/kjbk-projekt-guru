import os
from pathlib import Path
from urllib.parse import urlparse, unquote
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY nincs beállítva. Futtasd: python scripts/configure.py --local")
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [APP_URL] + [x for x in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if x]
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "oauth2_provider", "axes", "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "core.middleware.TrustedProxyMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware", "core.middleware.OAuthResourceMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True, "OPTIONS": {"context_processors": [
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]}}]
WSGI_APPLICATION = "config.wsgi.application"
db = os.getenv("DATABASE_URL", "")
if db:
    u = urlparse(db)
    DATABASES = {"default": {"ENGINE": "django.db.backends.mysql" if u.scheme in ("mysql", "mariadb") else "django.db.backends.postgresql", "NAME": unquote(u.path[1:]),
        "USER": unquote(u.username or ""), "PASSWORD": unquote(u.password or ""),
        "HOST": u.hostname, "PORT": u.port or (3306 if u.scheme in ("mysql", "mariadb") else 5432), "CONN_MAX_AGE": 60}}
    if u.scheme in ("mysql", "mariadb"):
        DATABASES["default"]["OPTIONS"] = {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"}
        DATABASES["default"]["TEST"] = {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci"}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "local.sqlite3", "OPTIONS": {"timeout": 30}}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend"]
AXES_FAILURE_LIMIT = 8
AXES_COOLOFF_TIME = 0.5
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = "core.views.locked_out"
LANGUAGE_CODE = "hu"
TIME_ZONE = "Europe/Budapest"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "frontend" / "dist"] if (BASE_DIR / "frontend" / "dist").exists() else []
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_MEMBERS = 5
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")
NOTIFICATION_EMAIL_ENABLED = os.getenv("NOTIFICATION_EMAIL_ENABLED", "false").lower() == "true"
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")
OAUTH2_PROVIDER = {
    # Match root discovery; do not infer a different issuer from the /oauth/ mount.
    "OIDC_ISS_ENDPOINT": APP_URL,
    "SCOPES": {"tasks:read": "Közös projektek és feladatok olvasása", "tasks:write": "Projektek és feladatok szerkesztése"},
    "DEFAULT_SCOPES": ["tasks:read", "tasks:write"], "PKCE_REQUIRED": True,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 3600, "REFRESH_TOKEN_EXPIRE_SECONDS": 60 * 60 * 24 * 30,
    "ROTATE_REFRESH_TOKEN": True, "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"] + (["http"] if DEBUG else []),
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,
}
