import time
import logging
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from core.worker import tick

class Command(BaseCommand):
    help = "Határidős értesítések, push-küldés és Google Naptár újrapróbálás. Egyetlen példányban futtasd."
    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
    def handle(self, *args, **options):
        while True:
            try:
                close_old_connections()
                tick()
            except Exception:
                logging.exception("A háttérfolyamat hibát észlelt; a következő ciklusban újrapróbálja.")
                if options["once"]:
                    raise
            if options["once"]:
                return
            time.sleep(30)
