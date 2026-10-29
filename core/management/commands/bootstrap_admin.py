import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from core.models import Workspace, Invite

class Command(BaseCommand):
    help = "Üres éles munkatér első adminjának egyszer használható meghívója, jelszó nélkül."
    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        validate_email(email)
        if User.objects.filter(is_active=True).exists():
            raise CommandError("A munkatérnek már van aktív tagja; nem készítek új adminmeghívót.")
        if User.objects.exclude(username=email).exists():
            raise CommandError("A munkatér nem üres.")
        Workspace.objects.get_or_create(id=1)
        user, _ = User.objects.get_or_create(username=email, defaults={"email": email, "first_name": options["name"], "is_staff": True, "is_superuser": True, "is_active": False})
        if user.is_active:
            raise CommandError("Az adminfiók már aktív.")
        user.set_unusable_password()
        user.save()
        raw = secrets.token_urlsafe(32)
        Invite.objects.filter(email=email, accepted_at=None).delete()
        Invite.objects.create(email=email, token_hash=hashlib.sha256(raw.encode()).hexdigest(), created_by=user, expires_at=timezone.now()+timedelta(days=1))
        self.stdout.write(settings.APP_URL + "/?invite=" + raw)
