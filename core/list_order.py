from uuid import UUID

from django.contrib.auth.models import User
from django.db import transaction

from .models import PersonalListOrder, Task
from .services import Problem


def ordered_task_ids(saved_ids):
    existing = [str(value) for value in Task.objects.filter(deleted=False).order_by("position", "created_at", "id").values_list("id", flat=True)]
    alive = set(existing)
    saved = list(dict.fromkeys(value for value in saved_ids if value in alive))
    selected = set(saved)
    return saved + [value for value in existing if value not in selected]


def list_order_json(user):
    order = PersonalListOrder.objects.filter(user=user).first()
    return {"task_ids": ordered_task_ids(order.task_ids if order else []), "version": order.version if order else 0}


def save_list_order(user, data):
    if set(data) != {"task_id", "target_id", "placement", "version"}:
        raise Problem("Add meg az áthelyezett feladatot, a célhelyet és a sorrend verzióját.")
    if type(data["version"]) is not int or data["version"] < 0 or data["placement"] not in ("before", "after"):
        raise Problem("Érvénytelen sorrend vagy verzió.")
    try:
        if any(not isinstance(data[key], str) for key in ("task_id", "target_id")):
            raise ValueError()
        moving, target = (str(UUID(data[key])) for key in ("task_id", "target_id"))
    except (ValueError, TypeError, AttributeError):
        raise Problem("Érvénytelen feladatazonosító.")
    with transaction.atomic():
        User.objects.select_for_update().get(id=user.id)
        order = PersonalListOrder.objects.filter(user=user).first()
        version = order.version if order else 0
        if data["version"] != version:
            raise Problem("A személyes sorrended közben megváltozott. Frissítsd a listát, majd próbáld újra.", 409)
        tasks = list(Task.objects.filter(id__in=[moving, target], deleted=False).select_related("project"))
        if len(tasks) != len({moving, target}):
            raise Problem("A feladat már nem található. Frissítsd a listát.", 404)
        if any(task.project.archived for task in tasks):
            raise Problem("Archivált projekt feladata nem rendezhető át.")
        ids = ordered_task_ids(order.task_ids if order else [])
        if moving != target:
            ids.remove(moving)
            ids.insert(ids.index(target) + (data["placement"] == "after"), moving)
            if order is None:
                order = PersonalListOrder(user=user)
            order.task_ids = ids
            order.version = version + 1
            order.save()
            version = order.version
        return {"task_ids": ids, "version": version}
