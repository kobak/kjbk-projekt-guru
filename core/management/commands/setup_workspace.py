import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from core.models import Workspace

class Command(BaseCommand):
    help = "Első adminisztrátor létrehozása. Meglévő felhasználót és adatot nem módosít."
    def add_arguments(self, parser):
        parser.add_argument("--email")
        parser.add_argument("--name")
    def handle(self, *args, **options):
        if User.objects.exists():
            raise CommandError("Már van felhasználó. Jelszóhoz: python manage.py changepassword <email>")
        email = (options["email"] or input("E-mail: ")).strip().lower()
        validate_email(email)
        name = options["name"] or input("Név: ").strip()
        password = getpass.getpass("Jelszó (min. 10 karakter): ")
        if password != getpass.getpass("Jelszó újra: "):
            raise CommandError("A két jelszó eltér.")
        user = User(username=email, email=email, first_name=name, is_staff=True, is_superuser=True)
        validate_password(password, user)
        user.set_password(password)
        user.save()
        Workspace.objects.get_or_create(id=1)
        self.stdout.write(self.style.SUCCESS("A munkatér elkészült. A többi tagot a Beállításokban hívhatod meg."))
