from django.contrib.auth.models import User
from django.db import transaction

from .models import Comment, Notification, Task
from .services import Problem, activity, notify, text


def validated_comment(data):
    body = text(data, "body", 10000, True)
    raw = data["body"]
    if len(raw) > 10000:
        raise Problem("A hozzászólás legfeljebb 10000 karakter lehet.")
    spans = data.get("mentions", [])
    if not isinstance(spans, list) or len(spans) > 100:
        raise Problem("Érvénytelen említések.")
    for span in spans:
        if (not isinstance(span, dict) or set(span) != {"user_id", "start", "end"}
                or any(type(span[key]) is not int for key in span)
                or span["user_id"] < 1 or not 0 <= span["start"] < span["end"]):
            raise Problem("Érvénytelen említések.")
    users = {u.id: u for u in User.objects.filter(id__in={s["user_id"] for s in spans}, is_active=True)}
    # Browser selection offsets count UTF-16 code units, including emoji pairs.
    try:
        encoded = raw.encode("utf-16-le")
        leading = len(raw[:len(raw) - len(raw.lstrip())].encode("utf-16-le")) // 2
        clean = []
        previous_end = 0
        for span in sorted(spans, key=lambda item: item["start"]):
            user = users.get(span["user_id"])
            start, end = span["start"], span["end"]
            if not user or start < previous_end or end * 2 > len(encoded):
                raise Problem("Érvénytelen vagy már nem elérhető említés. Válaszd ki újra a csapattagot.")
            expected = "@" + " ".join((user.first_name or user.username).split())
            if encoded[start * 2:end * 2].decode("utf-16-le") != expected:
                raise Problem("Az említés szövege megváltozott. Válaszd ki újra a csapattagot.")
            clean.append({"user_id": user.id, "start": start - leading, "end": end - leading})
            previous_end = end
    except UnicodeError:
        raise Problem("Érvénytelen karakter a hozzászólásban.")
    return body, clean


@transaction.atomic
def add_comment(task_id, user, data):
    body, mentions = validated_comment(data)
    # Serialize with task edits/deletion; the comment and all notices commit together.
    task = Task.objects.select_for_update().get(id=task_id, deleted=False, project__archived=False)
    comment = Comment.objects.create(task=task, user=user, body=body, mentions=mentions)
    mentioned = {span["user_id"] for span in mentions}
    participants = {task.created_by_id, task.assignee_id} | set(task.comments.values_list("user_id", flat=True))
    recipients = User.objects.filter(id__in=(participants | mentioned) - {None, user.id}, is_active=True)
    name = user.first_name or user.email
    for recipient in recipients:
        is_mention = recipient.id in mentioned
        notify(recipient.id, task,
            f"{name} megemlített egy hozzászólásban" if is_mention else f"{name} hozzászólt",
            task.title, f"comment:{comment.id}:{recipient.id}",
            kind=Notification.Kind.MENTION if is_mention else Notification.Kind.COMMENT)
    activity(user, task, "hozzászólt a feladathoz")
    return comment
