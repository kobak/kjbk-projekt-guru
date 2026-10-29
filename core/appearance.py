from django.core.exceptions import ValidationError

from .models import AppearancePreference


def appearance_json(user):
    preference = AppearancePreference.objects.filter(user=user).first() if user.is_authenticated else None
    return {"theme": preference.theme if preference else "system",
        "updated_at": preference.updated_at.isoformat() if preference else None}


def save_appearance(user, data):
    if set(data) != {"theme"} or not isinstance(data["theme"], str) or data["theme"] not in AppearancePreference.Theme.values:
        raise ValidationError("Válassz világos, sötét vagy rendszer szerinti megjelenést.")
    AppearancePreference.objects.update_or_create(user=user, defaults={"theme": data["theme"]})
    return appearance_json(user)
