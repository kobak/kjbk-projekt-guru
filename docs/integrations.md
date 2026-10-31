# Integrációk és személyes beállítások

Minden példa a saját telepítésed domainjére és feladójára cserélendő. A külső szolgáltatásokhoz szükséges fiókokat és kulcsokat a repó nem tartalmazza.

## Google Naptár

OAuth nélkül is működik a feladat előre kitöltött **Mentés a Google Naptárba** linkje és a **Másik naptár (.ics)** letöltés. Ezek egyszeri mentések: a későbbi feladatváltozást nem követik.

Automatikus szinkronhoz:

1. A [Google Cloud Console](https://console.cloud.google.com/) felületén hozz létre saját projektet, és engedélyezd a Google Calendar API-t.
2. Állítsd be az OAuth consent screen / Google Auth Platform részt. Google Workspace szervezeten belül Internal közönség választható; External tesztüzemnél a tagokat tesztfelhasználóként kell felvenni.
3. Készíts **Web application** OAuth-klienst, pontos redirect URI-val: `https://projekt.sajatdomain.hu/api/google/callback/`. Helyi teszthez külön `http://localhost:8000/api/google/callback/` kell. A címnek az `APP_URL` értékéből kell következnie, a záró perjellel együtt.
4. Írd a kliensazonosítót és titkot a `.env` `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` mezőibe. Indítsd újra a webet és workert; Docker esetén `docker compose up -d --force-recreate app worker`.
5. Minden tag a **Beállítások → Kapcsolatok** részen a **saját Google-fiókját** csatlakoztassa. Ez naptárengedély, nem Google-belépés az alkalmazásba.
6. Mentett, határidős feladatnál a **Naptárba** gombbal adható hozzá az esemény a saját elsődleges naptárhoz.

Kért hatókör: `https://www.googleapis.com/auth/calendar.events.owned`. A frissítőtoken titkosítva, a szerveren tárolódik. Az egész napos határidő egész napos esemény, a pontos időpont 30 perces, „Szabad” állapotú határidőjelölő. Időzóna: Europe/Budapest. A kész feladat ✓ jelöléssel megmarad, a törölt feladat eseményét a worker eltávolítja.

A worker 30 másodperces ciklusban dolgozik, Google-hibánál ritkábban próbál újra. A szinkron egyirányú: a feladat módosítja az eseményt. Ha a naptárban kézzel törlöd az eseményt, egy későbbi feladatmódosítás visszateheti; a végleges eltávolítást a GURU gombjával végezd. Leválasztás előtt az alkalmazásból távolítsd el a már hozzáadott eseményeket.

Google tesztmódban a frissítőtokenek korlátozott ideig érvényesek lehetnek. Tartós használathoz a Google Console aktuális publikálási és ellenőrzési feltételei irányadók. Hivatalos leírások: [OAuth webalkalmazásokhoz](https://developers.google.com/identity/protocols/oauth2/web-server), [Calendar események](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert).

## Google Drive-fájlválasztó

A feladat **Fájlok → Kiválasztás a Google Drive-ból** gombja Google-fiókválasztót és fájlválasztót nyit. Mindenki a saját Google-fiókjával dolgozik; a közös Cloud-projekt az alkalmazás azonosítására szolgál. A dokumentumot nem tölti fel a GURU szerverére. A meglévő Drive-megosztás érvényes: a csapattagoknak ott is hozzáféréssel kell rendelkezniük. A GURU-ból eltávolított hivatkozás a Google-fájlt megőrzi.

A Google Cloud-projektben a **Google Drive API** és **Google Picker API** szükséges. Webes OAuth-kliensnél add hozzá a saját GURU-címedet az Authorized JavaScript origins listához, például `https://projekt.sajatdomain.hu`. Ugyanaz a kliens használható a Naptárhoz is, annak külön callback címével. A telepítés védett `.env` fájljába kerül:

```dotenv
GOOGLE_CLIENT_ID=WEBES_OAUTH_KLIENSAZONOSITO
GOOGLE_CLIENT_SECRET=NAPTARHOZ_TARTOZO_KLIENSTITOK
GOOGLE_PICKER_API_KEY=KORLATOZOTT_BONGESZOS_API_KULCS
GOOGLE_PICKER_APP_ID=CLOUD_PROJEKT_SZAMA
# Opcionális, ha a Pickerhez külön webes OAuth-kliens kell:
GOOGLE_PICKER_CLIENT_ID=
```

Az app ID a Cloud-projekt **száma**, nem a szöveges projektazonosító. A böngészős API-kulcsot korlátozd a Google Picker API-ra, és webes hivatkozásokhoz engedélyezd a saját domaint (`https://projekt.sajatdomain.hu/*`) és a Google által előírt `https://docs.google.com/*` címet. A kliensazonosító és ez a korlátozott API-kulcs megjelenik a bejelentkezett felhasználó böngészőjében; kliens titkos kulcsa vagy frissítőtoken nem kerül oda.

Beállított Picker mellett a felület `Referrer-Policy: strict-origin-when-cross-origin` fejlécet ad: a Google így ellenőrizheti az engedélyezett webcímet, miközben feladatazonosítót vagy URL-paramétert nem kap. Fordított proxy esetén ezt ne írd felül `same-origin` vagy `no-referrer` értékkel, mert a Google ilyenkor érvénytelen fejlesztői kulcsot jelezhet. Az API-végpontok továbbra is `same-origin` beállítással működnek.

A Picker csak a `https://www.googleapis.com/auth/drive.file` hatókört kéri; a Naptár saját hatóköre külön engedélyezendő. A Drive-token rövid életű, nem kerül helyi tárba vagy az adatbázisba. A szerver kizárólag a kiválasztott fájl nevét és megnyitási hivatkozását ellenőrzi. A fájlválasztó visszalépését vagy bezárását kezeli; a belépéshez felugró Google-ablakot a böngészőben engedélyezni kell. A Google-kapcsolat kiépítése után indítsd újra az alkalmazást. Hiányzó beállítások mellett a GURU jelzi, hogy a Drive-integráció előkészítés alatt van.

Google Workspace szervezeten belüli használatnál Internal közönség választható, ekkor csak a szervezet Google-fiókjai csatlakozhatnak. Külső Gmail-/más domaines fiókokhoz External közönség és a Google aktuális közzétételi/ellenőrzési feltételei szükségesek. Ezek nem azonosak a GURU meghívásos hozzáférésével.

Hivatalos leírások: [Google Picker bekötése](https://developers.google.com/workspace/drive/picker/guides/web-picker), [rövid életű böngészős tokenek](https://developers.google.com/identity/oauth2/web/guides/use-token-model), [Drive fájlmetaadatok](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/get).

## Értesítések és SMTP

A csengő alatt az alkalmazáson belüli értesítések mindig elérhetők. A **Beállítások → Értesítések** részen minden tag külön választ e-mailt és push-t hat eseményhez:

| Esemény | E-mail alapból | Push alapból |
| --- | --- | --- |
| Új feladatot osztottak rá | Igen | Igen |
| Más módosította a feladatát | Nem | Igen |
| Hozzászólás az érintett feladathoz | Nem | Igen |
| Megemlítették egy hozzászólásban | Igen | Igen |
| Közelgő határidő | Nem | Igen |
| Lejárt határidő | Nem | Igen |

Az említéshez írj `@` jelet a hozzászólásba, majd válaszd ki a csapattagot név vagy e-mail alapján. A kiválasztott említések a szerkesztő alatt is látszanak; a pusztán begépelt név önmagában közönséges szöveg. Ha az említés szövegét átírod, válaszd ki újra a tagot. A küldött hozzászólásban az említés kiemelést kap. Az említett tag akkor is értesül, ha korábban nem vett részt a feladatban; a felelős/korábbi hozzászóló sem kap duplán jelzést. Saját említésről nincs külön értesítés. Az `0006_comment_mentions` migráció az új említéstípust mindkét csatornán bekapcsolja a meglévő fiókoknak, a korábbi öt típus választásait megőrzi. Ez később szabadon kikapcsolható.

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

Ugyanitt választható az asztali **Normál/Nagy betűméret**, **Kompakt/Tágas sűrűség**, illetve a **Lista/Kanban alapnézet**. A Normál méret is nagyobb feladatcímeket, listaszöveget és feladatablak-szöveget ad az eredeti változathoz képest. A méret és térköz az asztali nézetet módosítja; a mobil érintőfelülete megmarad. Alapérték: Lista, Normál, Kompakt.

## Lista és saját sorrend

A Tábla/Lista fül váltása automatikusan eltárolja a kiválasztott alapnézetet. A Naptár külön, ideiglenes nézet, nem írja át a Lista/Kanban-választást. Újratöltés, új projekt megnyitása vagy másik eszközön belépés után a saját alapnézeted érvényesül.

A lista felett a **Kész feladatok is** kapcsoló alapból kikapcsolt; ezt is fiókonként mentjük, oldalváltás és a szűrők alaphelyzetbe állítása nem felejti el. Ha az Állapot szűrőben kifejezetten a Kész állapotot választod, a kész feladatokat akkor is megmutatjuk. Ez nem módosítja a mentett láthatósági beállítást. A Kanban Kész oszlopát és a naptárat a listára mentett kapcsoló nem rejti el.

A mentett rendezések:

- **Határidő:** legkorábbi előre, azonos napon az egész napos a pontos időpontok előtt; határidő nélküliek a végén.
- **Prioritás:** Sürgős → Magas → Normál → Alacsony.
- **Létrehozás:** legújabb elöl, az eredeti létrehozási idő alapján; szerkesztéstől nem változik meg.
- **Saját kézi sorrend:** a sor eleji fogantyúval húzható. A fogantyúra fókuszálva a fel/le nyilakkal is átrendezhető. Archivált projektben nem szerkeszthető.

A kézi sorrend egy felhasználó teljes munkaterére vonatkozik; projekt-, keresési és felelősszűrésnél annak látható részét látod. Egy sor áthelyezése a többi, akár rejtett sor egymáshoz képesti sorrendjét megőrzi. Új feladatok a saját kézi sorrend végére kerülnek, törölt feladatok kimaradnak. Más felhasználó sorrendjét, a közös feladat verzióját, naptárát és értesítéseit nem módosítja. Párhuzamos, elavult sorrendmentéskor frissítést kér.
