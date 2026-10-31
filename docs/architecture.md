# Felépítés

## Forrás

| Hely | Feladat |
| --- | --- |
| `frontend/src/` | React 19 + TypeScript felület; a Vite build a `frontend/dist` mappába kerül |
| `frontend/public/` | PWA/service worker, ikonok, logók és a kirajzolás előtti témaindítás |
| `core/models.py`, `core/migrations/` | Projektek, feladatok, tagság, értesítések, integrációk és személyes beállítások |
| `core/views.py`, `core/services.py` | Hitelesített webes API, validálás és közös műveletek |
| `core/mcp.py`, `core/oauth.py` | MCP és OAuth-metaadatok, kliensregisztráció, erőforrás- és hatókör-ellenőrzés |
| `core/calendar.py` | Google-események, `.ics` és kézi Google-link; a frissítőtoken titkosítása |
| `core/appearance.py`, `core/list_order.py` | Személyes nézet, megjelenés, készfeladat-láthatóság és saját, verziózott kézi sorrend |
| `core/notifications.py`, `core/worker.py` | Személyes csatornaválasztások, határidőjelzések, küldési sor és újrapróbálás |
| `templates/` | OAuth-belépés/jóváhagyás és e-mail-sablonok |
| `config/` | Django-beállítások és útvonalak |
| `deploy/`, `scripts/` | Telepítési példák, kulcsgenerálás, mentés |

## Folyamatok és adatok

A webszerver reverse proxyként a Gunicorn/Django folyamathoz továbbítja a kéréseket. A statikus fájlokat WhiteNoise szolgálja ki. A worker ugyanazt az adatbázist és környezetet használja; nagyjából 30 másodpercenként dolgozza fel a naptárszinkront és az értesítéseket. **Egy workerpéldányt futtass.** Nincs Redis/Celery-függőség.

Az adatbázis tartalmazza a felhasználókat, jelszóhasheket, munkateret, projekteket, feladatokat, kommenteket, melléklet-metaadatokat, OAuth-kapcsolatokat, naptárszinkron-állapotot és értesítési sort. A fájlok a `media/` mappában vagy a Docker `attachments` volume-jában vannak. A `.env` tárolja a telepítés titkos kulcsait; adatbázis és csatolmányok önmagukban nem adnak teljes mentést.

Az `AppearancePreference` a fiók témáját, asztali betűméretét/sűrűségét és listabeállításait tárolja. A `PersonalListOrder` felhasználónként külön feladatazonosító-sorrendet és verziót őriz; mozgatáskor nem ír a `Task.position` vagy `Task.version` mezőbe, és nem generál közös tevékenységet vagy értesítést. Az API relatív mozgatást fogad, nem a teljes, esetleg szűrt listával írja felül a rejtett sorokat.

A `Comment.mentions` a kiválasztott tag azonosítóját és a megjelenő szöveg UTF-16 kezdő/végpozícióját tárolja. A backend ellenőrzi az aktív tagságot, a név egyezését és a tartományokat; az emoji és a külső szóközök levágása sem tolja el a kiemelést. A komment és a címzettenként egyetlen értesítés közös tranzakcióban jön létre. Az említés értesítéstípusa elsőbbséget kap a hagyományos hozzászólásjelzéssel szemben, de minden csatornán a címzett személyes beállítása érvényes. A régi kommentek üres említéslistával változatlanul megmaradnak.

A feladat dátumválasztóját a React felület rajzolja, magyar napnevekkel és hétfői hétkezdéssel, a böngésző területi beállításától függetlenül. Nyilakkal, Home/End, Page Up/Down és Shift+Page Up/Down billentyűkkel kezelhető; Escape csak a naptárat zárja be. A billentyűs működéshez a [WAI dátumválasztó mintája](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/datepicker-dialog/) szolgált referenciaként.

A feladat az elsődleges adat. Az opcionálisan hozzáadott Google-esemény ebből frissül; naptárból visszafelé nincs szerkesztés. Minden felhasználó a saját Google-kapcsolatával dolgozik. A személyes téma és értesítési beállítás csak az adott felhasználó API-ján módosítható.

A készre jelölés Visszavonás gombja 5 másodpercig él, és a mentés válaszában kapott feladatverzióval csak az előző állapotot küldi vissza. Más mezőket nem másol régi pillanatképből; bármilyen köztes feladatmódosítás verzióütközést eredményez. Egy értesítés művelete egyszer indítható, kijelentkezéskor a lehetőség megszűnik.

Az `Attachment` feltöltött fájlt vagy Drive-hivatkozást jelöl. A forrást adatbázis-kényszer ellenőrzi. A Drive-azonosító SHA-256 lenyomata feladatonként egyedi; ez a kis-/nagybetűre érzéketlen MariaDB-kolláció mellett is helyesen különbözteti meg az azonosítókat. A Google Picker `drive.file` engedélyt kér a felhasználó saját fiókjához. A rövid életű token kizárólag memóriában él, a szerver csak a kiválasztott fájl metaadatait ellenőrzi vele a Drive API-n; fájltartalmat, frissítőtokent vagy teljes Drive-listát nem ment. A név pillanatkép, a megnyitott dokumentum tartalma mindig a Drive-on elérhető változat. A GURU nem módosít Drive-megosztást és nem töröl Google-fájlt. A Naptár külön, titkosított felhasználói frissítőtokent használ.

## Hozzáférés

A normál API Django-munkamenetet és íráskor CSRF-ellenőrzést használ. A meghívó egyszer használható, időkorlátos, az adatbázisban hashként tárolt token. Az admin meghívhat és letilthat csapattagokat; minden aktív tag hozzáfér a közös projektekhez.

Az MCP-kliens OAuth authorization code + kötelező S256 PKCE folyamatban kap a konkrét `/mcp` erőforráshoz kötött hozzáférést. Az olvasási és szerkesztési hatókör külön ellenőrzött. A módosítások az aktuális feladatverziót kérik; ütközéskor nem írnak észrevétlenül felül. Az MCP nem ad fájlletöltést, tagkezelést vagy közvetlen Google-írást.

## Kapacitás és változtatás

A rendszer szándékosan kis csapatra készült. Nem multi-tenant szolgáltatás, nincs projektenkénti szerepkör. A `MAX_MEMBERS` jelenleg 5; növeléskor a jogosultságokat, kapacitást és teszteket is felül kell vizsgálni.

Új funkciónál először a közös szolgáltatási réteget használd, hogy a webes és MCP-műveletek azonos üzleti szabályokat kövessenek. Az adatmodell-változáshoz migráció, a telepítést vagy mentést érintő változáshoz dokumentáció is tartozik.
