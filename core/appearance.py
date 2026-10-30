from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import transaction

from .models import AppearancePreference

DEFAULTS = {"theme": "system", "default_view": "list", "show_completed": False,
    "list_sort": "due", "font_size": "normal", "density": "compact"}
CHOICES = {"theme": ("system", "light", "dark"), "default_view": ("board", "list"),
    "list_sort": ("due", "priority", "created", "manual"), "font_size": ("normal", "large"),
    "density": ("compact", "spacious")}

def appearance_json(user):
    preference = AppearancePreference.objects.filter(user=user).first() if user.is_authenticated else None
    return {**{key: getattr(preference, key) if preference else value for key, value in DEFAULTS.items()},
        "updated_at": preference.updated_at.isoformat() if preference else None}


def save_appearance(user, data):
    if not data or not set(data) <= DEFAULTS.keys():
        raise ValidationError("Adj meg érvényes személyes megjelenési beállításokat.")
    for key, value in data.items():
        if key == "show_completed":
            valid = type(value) is bool
        else:
            valid = isinstance(value, str) and value in CHOICES[key]
        if not valid:
            raise ValidationError("Érvénytelen megjelenési beállítás.")
    with transaction.atomic():
        User.objects.select_for_update().get(id=user.id)
        preference, _ = AppearancePreference.objects.get_or_create(user=user)
        for key, value in data.items():
            setattr(preference, key, value)
        preference.save(update_fields=[*data.keys(), "updated_at"])
    return appearance_json(user)
