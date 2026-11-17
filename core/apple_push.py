import logging
import re
import time
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import httpx
from django.conf import settings
from django.contrib.auth import HASH_SESSION_KEY, SESSION_KEY
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from jwcrypto import jwk, jwt

from .models import AppleDelivery, AppleDevice
from .notifications import notification_is_relevant, preference_channels
from .services import Problem

logger = logging.getLogger(__name__)
HOSTS = {"sandbox": "https://api.sandbox.push.apple.com", "production": "https://api.push.apple.com"}


def configured():
    return bool(settings.APNS_TEAM_ID and settings.APNS_KEY_ID and settings.APNS_KEY_FILE
                and settings.APNS_TOPIC and settings.APNS_ENVIRONMENT in HOSTS)


def device_settings(request):
    own = AppleDevice.objects.filter(user=request.user, session_id=request.session.session_key)
    if request.method == "GET":
        return {"configured": configured(), "enabled": own.filter(environment=settings.APNS_ENVIRONMENT).exists(),
                "user_id": request.user.pk}
    if request.data.get("user_id") != request.user.pk:
        raise Problem("A bejelentkezett fiók megváltozott.", 409)
    if request.method == "DELETE":
        own.delete()
        return {"enabled": False}
    if not configured():
        raise Problem("Az Apple push beállítása folyamatban van.", 503)
    token = request.data.get("token")
    if not isinstance(token, str) or not re.fullmatch(r"(?:[0-9a-f]{2}){1,128}", token):
        raise Problem("Érvénytelen Apple-eszközazonosító.")
    if request.data.get("environment") != settings.APNS_ENVIRONMENT:
        raise Problem("Ehhez a kiadáshoz eltérő Apple push környezet szükséges.", 409)
    try:
        with transaction.atomic():
            # A new login can adopt the same device, but never inherit its queued notifications.
            # Expired sessions can remain in django_session until clearsessions runs.
            previous = AppleDevice.objects.select_for_update().filter(token=token).exclude(session_id=request.session.session_key).first()
            if previous:
                if previous.user_id != request.user.pk and previous.session.expire_date > timezone.now():
                    raise Problem("Az eszköz egy másik bejelentkezéshez tartozik. Ott előbb jelentkezz ki.", 409)
                previous.delete()
            AppleDevice.objects.update_or_create(session_id=request.session.session_key, defaults={
                "user": request.user, "token": token, "environment": settings.APNS_ENVIRONMENT})
    except IntegrityError:
        raise Problem("Az eszköz regisztrációja közben változás történt. Próbáld újra.", 409)
    return {"enabled": True}


@lru_cache(maxsize=2)
def provider_token(team, key_id, key_file, period):
    key = jwk.JWK.from_pem(Path(key_file).read_bytes())
    signed = jwt.JWT(header={"alg": "ES256", "kid": key_id}, claims={"iss": team, "iat": int(time.time())})
    signed.make_signed_token(key)
    return signed.serialize()


def deliver(client, delivery_id):
    with transaction.atomic():
        # Lock in the same order as device replacement and cascade deletion.
        device_id = AppleDelivery.objects.filter(pk=delivery_id).values_list("device_id", flat=True).first()
        if device_id is None:
            return
        device = AppleDevice.objects.select_for_update().filter(pk=device_id).first()
        delivery = AppleDelivery.objects.select_for_update().filter(pk=delivery_id).first()
        if not device or not delivery or delivery.next_attempt_at > timezone.now():
            return
        n = delivery.notification
        now = timezone.now()
        session = device.session
        auth = session.get_decoded()
        if (session.expire_date <= now or not device.user.is_active or
                str(device.user_id) != auth.get(SESSION_KEY) or
                not constant_time_compare(auth.get(HASH_SESSION_KEY, ""), device.user.get_session_auth_hash())):
            device.delete()
            return
        if (device.environment != settings.APNS_ENVIRONMENT or n.user_id != device.user_id or
                n.read or n.created_at < now - timedelta(hours=24) or
                n.kind not in preference_channels(n.user_id)[1] or not notification_is_relevant(n)):
            delivery.delete()
            return
        endpoint = f"{HOSTS[device.environment]}/3/device/{device.token}"
        try:
            bearer = provider_token(settings.APNS_TEAM_ID, settings.APNS_KEY_ID, settings.APNS_KEY_FILE, int(time.time()) // 2400)
            response = client.post(endpoint, headers={
                "authorization": f"bearer {bearer}", "apns-topic": settings.APNS_TOPIC,
                "apns-push-type": "alert", "apns-priority": "10",
                "apns-expiration": str(int(min(n.created_at + timedelta(days=1), now + timedelta(hours=1)).timestamp())),
                "apns-collapse-id": f"guru-{n.id}",
            }, json={"aps": {"alert": {"title": "GURU", "body": n.title}, "sound": "default"}, "task_id": str(n.task_id)})
            if response.status_code == 200:
                delivery.delete()
                return
            reason = response.json().get("reason") if response.content else ""
            if response.status_code == 410 or reason in ("BadDeviceToken", "DeviceTokenNotForTopic"):
                device.delete()
                return
            # Log no device tokens, authentication headers or task data.
            logger.warning("Apple push %s: HTTP %s", n.pk, response.status_code)
        except Exception as exc:
            logger.warning("Apple push %s: %s", n.pk, type(exc).__name__)
        delivery.attempts += 1
        if delivery.attempts >= 5:
            delivery.delete()
        else:
            delivery.next_attempt_at = now + timedelta(minutes=(1, 5, 15, 60)[delivery.attempts - 1])
            delivery.save(update_fields=["attempts", "next_attempt_at"])


def deliver_pending():
    if configured():
        ids = list(AppleDelivery.objects.filter(next_attempt_at__lte=timezone.now())
                   .order_by("next_attempt_at").values_list("id", flat=True)[:25])
        if ids:
            with httpx.Client(http2=True, http1=False, timeout=5, trust_env=False) as client:
                for pk in ids:
                    deliver(client, pk)
