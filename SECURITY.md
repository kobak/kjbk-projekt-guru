# Biztonság

## Hiba bejelentése

Érzékeny hibához használd a repó **Security → Report a vulnerability** lehetőségét:

https://github.com/kobak/kjbk-projekt-guru/security/advisories/new

Ne tegyél nyilvános issue-ba működő tokent, jelszót, OAuth-kulcsot, teljes meghívólinket, adatbázismentést vagy személyes adatot. Ha a privát bejelentési lehetőség nem elérhető, előbb általános issue-ban kérj privát kapcsolatfelvételt a hiba részletei nélkül.

Jelenleg a legújabb kiadás az elsődlegesen karbantartott változat. Nincs vállalt válaszadási idő vagy külső biztonsági audit.

## Üzemeltetés

- A rendszer egy közös munkateret használ, legfeljebb 5 aktív felhasználóval. Minden aktív tag minden projektet lát és szerkeszthet; nincs több ügyfél közötti elkülönítés.
- Publikus telepítéshez HTTPS és `DEBUG=false` kell. A belső alkalmazásport csak loopbacken érhető el; a reverse proxy állítsa be a megfelelő Host és protokoll fejléceket.
- A `.env` fájl olvasását korlátozd a szolgáltatásfiókra/rootra (`0600`). A kulcsok ne kerüljenek böngészőbe, repóba, issue-ba vagy build-artefaktumba.
- A mellékleteket hitelesített végpont szolgálja ki. Feltöltött fájlokhoz nincs beépített vírusellenőrzés; ne futtass ismeretlen csatolmányt.
- A függőségek, az operációs rendszer és az adatbázis frissítése, a visszaállítási próba és a titkosított, külön gépen tárolt mentés az üzemeltető feladata.
- A `/health/` a webfolyamatot és egy egyszerű adatbázis-lekérdezést ellenőriz; az SMTP, Google és push kézbesítést külön kell vizsgálni.
- MCP-hozzáférést csak a szándékolt kliensnek engedélyezz. A kapcsolat a felhasználó közös projektekhez való hozzáférését kapja; a Beállításokban visszavonható.

Elveszett kulcsoknál a következményt is vizsgáld: a `SECRET_KEY` a Google-frissítőtokenek titkosításához is szükséges; a VAPID-kulcs cseréje új push-feliratkozást igényelhet. Lásd a [mentési leírást](docs/backup-and-restore.md).
