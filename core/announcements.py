from urllib.parse import urlsplit

from django.db import transaction
from .models import Announcement, AnnouncementDismissal, Workspace
from .services import Problem, text


FIELDS = {"title", "body", "link_label", "link_url"}


def announcement_json(item, *, admin=False):
    value = {"id": item.id, "title": item.title, "body": item.body, "link_label": item.link_label,
        "link_url": item.link_url, "version": item.version}
    if admin:
        value.update(published=item.active_slot == 1, updated_at=item.updated_at.isoformat())
    return value


def visible_announcement(user):
    item = Announcement.objects.filter(active_slot=1).first()
    if item and not AnnouncementDismissal.objects.filter(user=user, announcement=item, version=item.version).exists():
        return announcement_json(item)
    return None


def content(data):
    values = {"title": text(data, "title", 120, True), "body": text(data, "body", 500),
        "link_label": text(data, "link_label", 50), "link_url": text(data, "link_url", 2000)}
    url = values["link_url"]
    if bool(url) != bool(values["link_label"]):
        raise Problem("A linkhez címet és gombfeliratot is adj meg.")
    if url:
        try:
            parsed = urlsplit(url)
            internal = url.startswith("/") and not url.startswith("//") and not parsed.netloc and not parsed.scheme
            external = parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None and parsed.port in (None, 443)
        except ValueError:
            raise Problem("Érvénytelen hivatkozás.")
        if not (internal or external) or "\\" in url or any(ord(char) < 33 or ord(char) == 127 for char in url):
            raise Problem("A link HTTPS-cím vagy / jellel kezdődő belső hivatkozás lehet.")
    return values


def lock_workspace():
    # One row serializes publication on every supported database; nullable UNIQUE is the final guard.
    Workspace.objects.get_or_create(id=1)
    Workspace.objects.select_for_update().get(id=1)


def checked_item(item_id, data):
    item = Announcement.objects.select_for_update().filter(id=item_id).first()
    if not item:
        raise Problem("A hír nem található.", 404)
    version = data.get("version")
    if type(version) is not int or version < 1:
        raise Problem("Hiányzó vagy hibás hírverzió.")
    if item.version != version:
        raise Problem("A hírt közben módosították. Töltsd újra a szerkesztés előtt.", 409)
    return item


@transaction.atomic
def save_announcement(data, actor, item_id=None):
    if set(data) - (FIELDS | ({"version"} if item_id is not None else set())):
        raise Problem("Ismeretlen hírmező.")
    if item_id is None:
        values = content(data)
        lock_workspace()
        return announcement_json(Announcement.objects.create(**values, created_by=actor, updated_by=actor), admin=True)
    lock_workspace()
    item = checked_item(item_id, data)
    values = content({key: data[key] if key in data else getattr(item, key) for key in FIELDS})
    if any(getattr(item, key) != value for key, value in values.items()):
        for key, value in values.items():
            setattr(item, key, value)
        item.version += 1
        item.updated_by = actor
        item.save()
    return announcement_json(item, admin=True)


@transaction.atomic
def set_publication(item_id, data, actor, published):
    if set(data) != {"version"}:
        raise Problem("Csak a hír verziója adható meg.")
    lock_workspace()
    item = checked_item(item_id, data)
    if (item.active_slot == 1) != published:
        if published:
            for previous in Announcement.objects.select_for_update().filter(active_slot=1).exclude(id=item.id):
                previous.active_slot, previous.updated_by = None, actor
                previous.version += 1
                previous.save(update_fields=["active_slot", "version", "updated_by", "updated_at"])
        item.active_slot = 1 if published else None
        item.version += 1
        item.updated_by = actor
        item.save(update_fields=["active_slot", "version", "updated_by", "updated_at"])
    return announcement_json(item, admin=True)


@transaction.atomic
def dismiss_announcement(item_id, data, user):
    if set(data) != {"version"}:
        raise Problem("Csak a hír verziója adható meg.")
    item = checked_item(item_id, data)
    if item.active_slot != 1:
        raise Problem("Ez a hír már nincs közzétéve.", 409)
    AnnouncementDismissal.objects.update_or_create(user=user, announcement=item, defaults={"version": item.version})
    return {"ok": True}
