"""One-use Django reset tokens, delivered by the existing background worker."""
import hashlib
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import PasswordResetDelivery, PushSubscription
from .ratelimit import allow
from .services import Problem

logger = logging.getLogger(__name__)
REQUEST_MESSAGE = "Ha ehhez a címhez aktív GURU-fiók tartozik, hamarosan e-mailt küldünk a jelszó-visszaállításhoz."
INVALID_LINK = "A jelszó-visszaállító link lejárt vagy már felhasználták. Kérj új linket."


def security_state(user):
    # A queued request must not survive a password, address or login change.
    return hashlib.sha256(f"{user.password}|{user.last_login}|{user.email}|{user.is_active}".encode()).hexdigest()


def request_reset(email, ip):
    email_allowed = allow("password-reset-email:" + hashlib.sha256(email.encode()).hexdigest(), 3, 3600)
    ip_allowed = allow("password-reset-ip:" + ip, 10, 3600)
    if not email_allowed or not ip_allowed:
        raise Problem("Túl sok kérés. Próbáld újra egy óra múlva.", 429)
    for user in User.objects.filter(email__iexact=email, is_active=True):
        if user.has_usable_password():
            PasswordResetDelivery.objects.create(user=user, email=user.email, security_state=security_state(user))
    return {"message": REQUEST_MESSAGE}


@transaction.atomic
def confirm_reset(uid, token, password):
    try:
        user_id = urlsafe_base64_decode(uid).decode()
        user = User.objects.select_for_update().get(pk=user_id, is_active=True)
    except (ValueError, UnicodeError, OverflowError, User.DoesNotExist):
        raise Problem(INVALID_LINK)
    if not user.has_usable_password() or not default_token_generator.check_token(user, token):
        raise Problem(INVALID_LINK)
    validate_password(password, user)
    user.set_password(password)
    user.save(update_fields=["password"])
    # Password changes invalidate Django session hashes. Old browser push
    # subscriptions must also stop receiving account details.
    PushSubscription.objects.filter(user=user).delete()
    from axes.utils import reset
    reset(username=user.username)
    return {"message": "A jelszavad megváltozott. Jelentkezz be az új jelszóval."}


@transaction.atomic
def deliver_reset(delivery_id):
    item = PasswordResetDelivery.objects.select_for_update().select_related("user").get(pk=delivery_id)
    now = timezone.now()
    if item.finished or (item.next_attempt_at and item.next_attempt_at > now):
        return
    if (item.created_at <= now - timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT)
            or item.security_state != security_state(item.user) or not item.user.is_active
            or not item.user.has_usable_password()):
        item.finished = True
        item.save(update_fields=["finished"])
        return
    uid = urlsafe_base64_encode(force_bytes(item.user_id))
    token = default_token_generator.make_token(item.user)
    context = {"reset_url": f"{settings.APP_URL}/#reset={uid}/{token}",
               "name": item.user.first_name, "minutes": settings.PASSWORD_RESET_TIMEOUT // 60}
    message = EmailMultiAlternatives(
        subject="[GURU] Jelszó-visszaállítás", from_email=settings.DEFAULT_FROM_EMAIL,
        to=[item.email], body=render_to_string("password_reset/email.txt", context))
    message.attach_alternative(render_to_string("password_reset/email.html", context), "text/html")
    item.attempts += 1
    try:
        if message.send() != 1:
            raise RuntimeError("Email backend did not accept the reset message")
    except Exception as exc:
        item.error = type(exc).__name__[:120]
        item.finished = item.attempts >= 3
        item.next_attempt_at = now + timedelta(minutes=(1, 5, 15)[min(item.attempts - 1, 2)])
        logger.warning("Password reset delivery %s failed (%s)", item.id, type(exc).__name__)
    else:
        item.sent_at, item.finished, item.error = timezone.now(), True, ""
        item.next_attempt_at = None
    item.save(update_fields=["attempts", "finished", "sent_at", "error", "next_attempt_at"])


def deliver_pending_resets():
    now = timezone.now()
    ids = list(PasswordResetDelivery.objects.filter(finished=False).filter(
        Q(next_attempt_at=None) | Q(next_attempt_at__lte=now)).order_by("created_at").values_list("id", flat=True)[:10])
    for delivery_id in ids:
        deliver_reset(delivery_id)
    PasswordResetDelivery.objects.filter(created_at__lt=now - timedelta(days=30)).delete()
