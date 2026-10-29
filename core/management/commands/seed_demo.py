from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Workspace, Project, Task, ChecklistItem, Comment, Activity
from core.services import notify

class Command(BaseCommand):
    help = "Kizárólag helyi, üres fejlesztői adatbázis feltöltése bemutatóadatokkal."
    def handle(self, *args, **options):
        if not settings.DEBUG or User.objects.exists():
            raise CommandError("Csak üres, DEBUG=true fejlesztői adatbázison futtatható.")
        Workspace.objects.create(id=1, name="A mi munkaterünk")
        people=[]
        for name, email in [("Demó Balázs", "demo@kozos.local"), ("Kiss Anna", "anna@kozos.local"), ("Nagy Márk", "mark@kozos.local")]:
            people.append(User.objects.create_user(username=email, email=email, first_name=name, password="Kozos-demo-2026!", is_staff=not people, is_superuser=not people))
        projects=[]
        for name, desc, color in [
            ("Weboldal megújítás", "Egy frissebb, egyszerűbb weboldal. Az ötlettől az élesítésig.", "#638773"),
            ("Őszi workshop", "Közös tanulás, új ötletek. Minden, ami a következő alkalomhoz kell.", "#a28bb2"),
            ("Tartalomtervezés", "Videók, bejegyzések és a következő nagy ötlet.", "#c69a60")]:
            projects.append(Project.objects.create(name=name, description=desc, color=color))
        rows=[
            (0,"Főoldal drótvázának véglegesítése","doing","high",0,0,["Design"],"Nézzük át együtt a főoldal szerkezetét. A mobilnézet legyen az első kiindulópont."),
            (0,"Új szövegek az oldalhoz","todo","normal",1,1,["Szöveg"],"Rövid, közvetlen bemutatkozás és a szolgáltatások leírása."),
            (0,"Mobilnézet tesztelése","todo","high",2,2,["Fejlesztés"],"Telefonon is legyen gyors és kényelmes."),
            (0,"Arculati színek és betűk","done","normal",1,-2,["Design"],"A kiválasztott színek és tipográfia összefoglalása."),
            (0,"Kapcsolati űrlap ellenőrzése","review","normal",2,0,["Fejlesztés"],"Próbaküldés és a visszajelzések ellenőrzése."),
            (1,"Workshop programjának összeállítása","doing","high",0,1,["Tervezés"],"90 perces program, rövid bevezetővel és sok gyakorlattal."),
            (1,"Helyszín és technika egyeztetése","todo","normal",1,3,["Szervezés"],"Projektor, wifi és a csoportmunka helye."),
            (1,"Meghívó kiküldése","todo","normal",2,5,["Kommunikáció"],"A végleges program alapján."),
            (1,"Résztvevői visszajelzések áttekintése","done","low",0,-1,[],"Az előző alkalom tanulságai."),
            (2,"Következő videó vázlata","doing","normal",0,0,["Videó"],"A legfontosabb gondolatok és a bemutató menete."),
            (2,"Októberi témák összegyűjtése","review","low",1,2,["Ötletek"],"Mi foglalkoztat most minket?"),
            (2,"Blogbejegyzés szerkesztése","todo","normal",0,4,["Blog"],"Egy utolsó átolvasás és a képek kiválasztása."),
            (2,"Borítóképek kiválasztása","todo","low",2,None,["Design"],"Három vizuális irány összehasonlítása."),
        ]
        for i,(p,title,status,priority,u,day,labels,description) in enumerate(rows):
            t=Task.objects.create(project=projects[p],title=title,status=status,priority=priority,assignee=people[u],created_by=people[0],due_date=timezone.localdate()+timedelta(days=day) if day is not None else None,labels=labels,description=description,position=i)
            if i==0:
                ChecklistItem.objects.bulk_create([ChecklistItem(task=t,text="Mobilos vázlat",done=True),ChecklistItem(task=t,text="Asztali változat",done=True),ChecklistItem(task=t,text="Közös visszajelzések")])
                Comment.objects.create(task=t,user=people[1],body="A mobilos változatot átnéztem, szerintem jó irány. A nyitó szakasznál hagynék egy kicsivel több helyet.")
                notify(people[0].id,t,"Anna hozzászólt a feladathoz",title)
            Activity.objects.create(user=people[u],task=t,text="lezárta a feladatot" if status=="done" else "frissítette a feladatot")
        self.stdout.write("Helyi demó: demo@kozos.local / Kozos-demo-2026! (élesben nem használható).")
