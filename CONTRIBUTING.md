# Közreműködés

Forkold a repót, készíts külön ágat, és nyiss pull requestet. A javítás konkrét hibát vagy egyeztetett funkciót oldjon meg; a meglévő kiscsapatos működés és magyar felület megőrzése a cél.

## Fejlesztés

A [README](README.md) helyi telepítése után a `frontend/src/`, `core/`, `templates/` mappákban dolgozhatsz. A Django a `frontend/dist` lefordított állományait szolgálja ki; a frontend módosítása után `npm --prefix frontend run build` szükséges. A helyi `.env` és adatbázis ne kerüljön commitba.

Ellenőrzések pull request előtt:

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test core --noinput
npm --prefix frontend run build
npm --prefix frontend test
git diff --check
```

Adatmodell-változáshoz mellékeld a migrációt. Jogosultságot, adatvesztést, naptár- vagy értesítési működést érintő javításhoz írj a hibát bizonyító tesztet. Felületi változásnál ellenőrizd a világos/sötét témát, az asztali és mobilnézetet; a PR-ba személyes adat nélküli képernyőképet tegyél.

## Hibajelentés

Írd le a verziót vagy commitot, a környezetet, a lépéseket, az elvárt és a tapasztalt eredményt. Böngészős hibánál a böngésző és képernyőméret is hasznos. Naplóból távolítsd el a tokeneket, meghívólinkeket, e-mail-címeket és feladatszövegeket.

Biztonsági hibát a [SECURITY.md](SECURITY.md) szerint jelents, ne nyilvános issue-ban. A beküldött saját hozzájárulások a projekt MIT-licence alatt kerülnek be; idegen kód és képek forrását, illetve licencét tüntesd fel. A KJBK-logókra a [külön feltételek](BRANDING.md) vonatkoznak.
