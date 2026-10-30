import json

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q

from .models import Invite, Workspace
from .services import Problem, person, text


def change_member_email(actor, user_id, data):
    if not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise Problem("Ehhez adminisztrátori hozzáférés kell.", 403)
    if set(data) != {"email", "current_email"}:
        raise Problem("Az új és a jelenlegi e-mail-címet add meg.")
    email = text(data, "email", 254, True).lower()
    current_email = text(data, "current_email", 254, True)
    validate_email(email)
    if len(email) > User._meta.get_field("username").max_length:
        raise Problem("A belépési e-mail-cím legfeljebb 150 karakter lehet.")
    try:
        with transaction.atomic():
            # A meghívóelfogadás is ezt a sort zárolja: egy címnek egy fiókja lehet.
            Workspace.objects.select_for_update().get_or_create(id=1)
            member = User.objects.select_for_update().get(id=user_id, is_active=True)
            if member.email != current_email:
                raise Problem("A tag e-mail-címe közben megváltozott. Frissítsd a csapatlistát, majd próbáld újra.", 409)
            if User.objects.exclude(id=member.id).filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
                raise Problem("Ez az e-mail-cím már másik fiókhoz tartozik.", 409)
            if member.email == email and member.username == email:
                return {"user": person(member)}
            previous_username = member.username
            member.email = member.username = email
            member.save(update_fields=["email", "username"])
            # A régi címre kiadott, még élő link ne hozhasson létre új fiókot;
            # az új cím korábbi meghívója se maradjon használható.
            Invite.objects.filter(accepted_at=None).filter(
                Q(email__iexact=current_email) | Q(email__iexact=previous_username) | Q(email__iexact=email)
            ).delete()
            LogEntry.objects.create(user=actor, content_type=ContentType.objects.get_for_model(User),
                object_id=str(member.id), object_repr=member.first_name or member.email, action_flag=CHANGE,
                change_message=json.dumps([{"changed": {"fields": ["E-mail-cím", "Belépési cím"]}}], ensure_ascii=False))
            return {"user": person(member)}
    except IntegrityError:
        raise Problem("Ez az e-mail-cím már másik fiókhoz tartozik.", 409)
