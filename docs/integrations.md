# Integrációk és személyes beállítások

Minden példa a saját telepítésed domainjére és feladójára cserélendő. A külső szolgáltatásokhoz szükséges fiókokat és kulcsokat a repó nem tartalmazza.

## Google Naptár

OAuth nélkül is működik a feladat előre kitöltött **Mentés a Google Naptárba** linkje és a **Másik naptár (.ics)** letöltés. Ezek egyszeri mentések: a későbbi feladatváltozást nem követik.

Automatikus szinkronhoz:

1. A [Google Cloud Console](https://console.cloud.google.com/) felületén hozz létre saját projektet, és engedélyezd a Google Calendar API-t.
2. Állítsd be az OAuth consent screen / Google Auth Platform részt, saját kiscsapatos tesztüzemnél a tagokat tesztfelhasználóként felvéve.
3. Készíts **Web application** OAuth-klienst, pontos redirect URI-val: `https://projekt.sajatdomain.hu/api/google/callback/`. Helyi teszthez külön `http://localhost:8000/api/google/callback/` kell. A címnek az `APP_URL` értékéből kell következnie, a záró perjellel együtt.
4. Írd a kliensazonosítót és titkot a `.env` `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` mezőibe. Indítsd újra a webet és workert; Docker esetén `docker compose up -d --force-recreate app worker`.
5. Minden tag a **Beállítások → Kapcsolatok** részen a **saját Google-fiókját** csatlakoztassa. Ez naptárengedély, nem Google-belépés az alkalmazásba.
6. Mentett, határidős feladatnál a **Naptárba** gombbal adható hozzá az esemény a saját elsődleges naptárhoz.

Kért hatókör: `https://www.googleapis.com/auth/calendar.events.owned`. A frissítőtoken titkosítva, a szerveren tárolódik. Az egész napos határidő egész napos esemény, a pontos időpont 30 perces, „Szabad” állapotú határidőjelölő. Időzóna: Europe/Budapest. A kész feladat ✓ jelöléssel megmarad, a törölt feladat eseményét a worker eltávolítja.

A worker 30 másodperces ciklusban dolgozik, Google-hibánál ritkábban próbál újra. A szinkron egyirányú: a feladat módosítja az eseményt. Ha a naptárban kézzel törlöd az eseményt, egy későbbi feladatmódosítás visszateheti; a végleges eltávolítást a GURU gombjával végezd. Leválasztás előtt az alkalmazásból távolítsd el a már hozzáadott eseményeket.

Google tesztmódban a frissítőtokenek korlátozott ideig érvényesek lehetnek. Tartós használathoz a Google Console aktuális publikálási és ellenőrzési feltételei irányadók. Hivatalos leírások: [OAuth webalkalmazásokhoz](https://developers.google.com/identity/protocols/oauth2/web-server), [Calendar események](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert).

## Értesítések és SMTP

A csengő alatt az alkalmazáson belüli értesítések mindig elérhetők. A **Beállítások → Értesítések** részen minden tag külön választ e-mailt és push-t öt eseményhez:

| Esemény | E-mail alapból | Push alapból |
| --- | --- | --- |
| Új feladatot osztottak rá | Igen | Igen |
| Más módosította a feladatát | Nem | Igen |
| Hozzászólás az érintett feladathoz | Nem | Igen |
| Közelgő határidő | Nem | Igen |
| Lejárt határidő | Nem | Igen |

A push alapértéke nem jelent automatikus böngészőengedélyt: az eszközön külön engedélyezni kell. Az egész napos határidő emlékeztetőjének referenciaideje 09:00, a közelgő jelzés az előző 24 órában válik esedékessé.

SMTP-hez használható például Brevo vagy más tranzakciós szolgáltató. A `.env` mezői:

```dotenv
NOTIFICATION_EMAIL_ENABLED=false
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=SAJAT_SMTP_AZONOSITO
EMAIL_HOST_PASSWORD=SAJAT_SMTP_KULCS
DEFAULT_FROM_EMAIL=projekt guru <guru@sajatdomain.hu>
```

Hitelesítsd a saját domaint és feladót a szolgáltatónál; az általa kért DKIM/ellenőrző rekordok telepítésenként eltérnek. A meglévő bejövő Google/Microsoft levelezés MX-rekordjait nem szükséges lecserélni. A meglévő SPF-/DMARC-szabályokat a domain többi küldőjével együtt kezeld.

A kulcs csak a védett `.env` fájlba kerüljön. Saját tesztcímzettel ellenőrizd a kézbesítést, majd állítsd `NOTIFICATION_EMAIL_ENABLED=true` értékre, és indítsd újra a webet/workert. A próbalevél küldésére külön Django shellből a `django.core.mail.send_mail` használható; ne futtass ellenőrzés közben tömeges küldést.

A küldési sor átmeneti SMTP-hibánál 1, 5 és 30 perc múlva próbál újra, összesen legfeljebb négyszer. Régi, törölt, archivált, másra kiosztott vagy átütemezett értesítésből nem indul elavult levél. A kikapcsolt csatorna sorban álló küldéseit is kihagyja; utólagos bekapcsoláskor nem küldi újra a korábbi értesítéseket. A levelek szöveges/HTML változatot és feladat-/beállításlinket tartalmaznak.

A szolgáltató általi átvétel még nem bizonyítja a postafiókba érkezést: nézd meg a szolgáltatói naplót és a tesztcímzett visszajelzését. Kulcslejáratot és szolgáltatói limiteket az adott fiókban ellenőrizd. [Brevo SMTP-leírás](https://help.brevo.com/hc/en-us/articles/7924908994450-Send-transactional-emails-using-Brevo-SMTP).

## Push és PWA

A környezetgeneráló létrehozza a VAPID-kulcspárt. A web és worker ugyanazokat a kulcsokat használja; őrizd meg őket a mentésben. A **Beállítások → Kapcsolatok → Push értesítések** gomb az adott eszközön kér engedélyt.

HTTPS és támogató böngésző szükséges. iPhone/iPad készüléken előbb a Főképernyőhöz kell adni az oldalt, és onnan megnyitni. A kézbesítést az eszköz engedélyei, a böngésző és az energiatakarékosság befolyásolják. Kijelentkezéskor az aktuális eszköz előfizetését leválasztja. A service worker nem gyorsítótáraz feladatokat, API-válaszokat vagy fájlokat; az alkalmazás használatához internet kell.

## MCP-kapcsolat

Távoli cím: `https://projekt.sajatdomain.hu/mcp`.

Kompatibilis kliensben ezt add meg OAuth-hitelesítéssel és dinamikus kliensregisztrációval. A pontos menüpontok, elérhető csatlakozók és előfizetési feltételek kliensenként változhatnak. A GURU saját meghívásos fiókjával jelentkezz be a megnyíló oldalon, majd engedélyezd a szükséges `tasks:read` / `tasks:write` hatókört. A kapcsolat a **Beállítások → Kapcsolatok** részen visszavonható.

Elérhető eszközök: `list_projects`, `list_members`, `list_tasks`, `get_task`, `create_project`, `create_task`, `update_task`. Módosításhoz a `get_task` által adott aktuális `version` kell. Fájlletöltés, tagkezelés és Google-naptárírás nincs az MCP-n keresztül.

Az OAuth `issuer` mindenhol pontosan az `APP_URL`. A `/.well-known/oauth-authorization-server` metaadat és az engedélyezési válasz `iss` paramétere is ugyanazt használja. Ezt a `config/settings.py` és `core/oauth.py` szándékosan rögzíti; eltéréskor a Claude biztonsági ellenőrzése megszakíthatja a kapcsolatot. Az MCP-címet ne téveszd össze az issuer címével: előbbi végén `/mcp` van.

## Megjelenés

A fejléc nap/hold/monitor ikonjával vagy a **Beállítások → Saját fiók → Megjelenés** részen választható Világos, Sötét és Rendszer szerint mód. A választás automatikusan a fiókhoz mentődik, másik eszközön a következő bejelentkezéskor/betöltéskor is érvényes. Az alapérték rendszer szerinti; ilyenkor a készülék témaváltását is követi. A helyi gyorsítótár a betöltés eleji felvillanást csökkenti, az elsődleges mentés a szerveren van.
