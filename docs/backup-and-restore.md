# Mentés és visszaállítás

## Mi kell egy teljes mentéshez?

1. **Forrás és pontos verzió:** Git commit/címke és a telepítés helyi módosításai. A nyilvános GitHub-repó ezt őrzi, nem a működő alkalmazás adatait.
2. **Adatbázis:** felhasználók, jelszóhashek, projektek, feladatok, hozzászólások, beállítások és kapcsolatok.
3. **Csatolmányok:** `media/` könyvtár vagy `attachments` Docker-volume.
4. **Környezet:** az eredeti `.env`, benne a Django `SECRET_KEY`, VAPID-, OAuth-, SMTP- és adatbázisadatok.
5. **Telepítési konfiguráció:** az adott gép proxy-/systemd-fájljai, domain, tanúsítvány-megújítás és a választott környezet leírása.

Az adatbázis Google-frissítőtokenjei a `SECRET_KEY` segítségével titkosítottak. Kulcs nélküli adatbázismentésből ezek nem állíthatók helyre. A VAPID-kulcsok cseréje után az eszközöknek újra fel kell iratkozniuk.

**Adatbázist, csatolmányt és `.env` fájlt ne tölts GitHubra**, privát repóba vagy kiadási csatolmányként sem. A mentést titkosítva, a szervertől külön gépen/szolgáltatásban tárold; a visszafejtőkulcs külön megőrzendő. A mentési könyvtárak `0700`, a titkos fájlok `0600` jogosultságúak legyenek. Az SSH a szállítást védi, a lemezen tárolást külön titkosítás védi.

## Docker-mentés

```sh
sh scripts/backup.sh
```

A script röviden leállítja a webet és workert, konzisztensen menti a PostgreSQL-t, a mellékleteket és a `.env` fájlt, majd a korábban futó két szolgáltatást visszaindítja. A mentés a `backups/<UTC-időbélyeg>/` könyvtárba kerül:

```text
database.dump          PostgreSQL custom-format dump
attachments.tar.gz     A media könyvtár tartalma
environment.env        Az eredeti .env
source-commit.txt      Git-verzió, ha elérhető
source.tar.gz          A commitolt forrás, ha Gitből futtatod
COMPLETE               Csak sikeres mentésnél jön létre
```

A Git-archívum a commitolt forrást menti; a helyi, nem commitolt arculati vagy konfigurációs módosításokat külön tedd a privát mentésbe. A script nem töröl régi mentéseket, nem titkosít és nem másol külső tárhelyre. Ütemezést sem telepít automatikusan.

## Natív MariaDB-mentés

```sh
sudo /opt/kozos/.venv/bin/python /opt/kozos/scripts/backup_native.py
```

Root szükséges, mert az adatbázishoz a helyi admin kapcsolódik, és a `.env` korlátozott hozzáférésű. A script a korábban futó alkalmazást/workert leállítja, majd hiba esetén is megpróbálja visszaindítani. A `/var/backups/kozos/<UTC-időbélyeg>/` mappába ment:

```text
database.sql.gz        A kozos MariaDB-adatbázis SQL-mentése
attachments.tar.gz     A media/ könyvtár
environment.env        Az eredeti .env
source.tar.gz          A mentett telepítés forrása és frontend-buildje
source-commit.txt      Git-verzió, ha ismert
manifest.json          Formátum és időpont
COMPLETE               Sikeres befejezés jelzője
```

Csak a GURU adatbázisát, fájljait és kódját érinti. Nem teljes VPS-/WordPress-mentés. A gépre telepített Apache/Nginx/systemd konfigurációkat és a TLS beállítását külön őrizd meg. A `/opt/kozos/.venv`, `node_modules`, Python-cache és statikus másolat nem szükséges: a lockfájlokból és forrásból újraépíthetők. Az archívum a helyi forrásfájlokat is tartalmazza, ezért ezt is privát mentésként kezeld.

## Visszaállítás előtti lépések

- Először **külön tesztrendszeren** gyakorold, ne az élő adatokat írd felül.
- Ellenőrizd a `COMPLETE` fájlt, a fájlok sértetlenségét és az archívumok tartalmát (`tar -tzf`, PostgreSQL-nél `pg_restore --list`).
- Használd a mentéshez tartozó forrásverziót és adatbázis-motort. A MariaDB SQL-dump és a PostgreSQL custom dump nem csereszabatos.
- A helyreállítás és ellenőrzés alatt a worker maradjon leállítva. Izolált próbán tiltsd a kimenő küldést, és állítsd `NOTIFICATION_EMAIL_ENABLED=false` értékre a helyi másolatot. Az eredeti `.env` kulcsait őrizd meg; SMTP-/push-/Google-küldést ne engedj valódi címzettekre.
- Meglévő céladatokról készíts külön mentést. A következő példák **üres, új céladatbázist és fájltárat** feltételeznek.

## Docker-visszaállítás új gépre

A projekt könyvtárában állítsd vissza a megfelelő forrást, és másold vissza a mentett környezetet. A `backup_path` a már visszafejtett, védett mentési könyvtár:

```sh
backup_path=/vedett/mentes/20260101T120000Z
cp "$backup_path/environment.env" .env
chmod 600 .env
docker compose build app
docker compose up -d db
```

Várd meg a DB egészséges állapotát (`docker compose ps`). Az új PostgreSQL-példány inicializálásához ugyanaz a `POSTGRES_PASSWORD` kell a visszaállított `.env` fájlból.

```sh
docker compose exec -T db pg_restore -U kozos -d kozos --no-owner --exit-on-error \
  < "$backup_path/database.dump"
docker compose run --rm --no-deps -T --entrypoint tar app -C /app/media -xzf - \
  < "$backup_path/attachments.tar.gz"
docker compose run --rm --no-deps app python manage.py check
docker compose up -d app
```

A webfolyamat elvégzi az esetleg szükséges migrációt/statikusgyűjtést. Ellenőrizd a belépést, egy projektet és csatolmányletöltést. Csak sikeres ellenőrzés és az integrációk megfelelő beállítása után indítsd a workert: `docker compose up -d worker`.

Meglévő, már adattal feltöltött volume-ba ne futtasd vakon a restore-t; ehhez külön leállítási, ürítési és visszalépési terv kell.

## Natív visszaállítás új gépre

1. Telepítsd a megfelelő Python/MariaDB környezetet és a `kozos` szolgáltatásfiókot a [telepítési leírás](deployment.md) szerint. A web és worker még ne induljon el.
2. Bontsd a `source.tar.gz` fájlt az üres `/opt/kozos` könyvtárba. Állítsd vissza az eredeti `environment.env` fájlt `.env` néven, `kozos:kozos` tulajdonossal és `0600` jogosultsággal.
3. A `.env` `DATABASE_URL` értéke szerinti külön adatbázist/felhasználót hozd létre a régi jelszóval. A mellékelt provisioning csak a dokumentált helyi `kozos` beállításhoz használható. A jelszót ne írd shell argumentumba vagy naplóba.
4. Üres céladatbázisba töltsd vissza az SQL-t:

```sh
backup_path=/vedett/mentes/20260101T120000Z
gzip -dc "$backup_path/database.sql.gz" | sudo mariadb kozos
sudo tar -xzf "$backup_path/attachments.tar.gz" -C /opt/kozos
sudo chown -R kozos:kozos /opt/kozos/media
sudo chmod 700 /opt/kozos/media
```

5. Hozd létre a `.venv` környezetet, telepítsd az adott Pythonhoz tartozó lockfájlt, fordítsd a frontendet, futtasd a `manage.py check`, `manage.py migrate --noinput` és `manage.py collectstatic --noinput` parancsokat.
6. Állítsd vissza a saját domainre szabott proxy-/systemd-konfigurációt és érvényes HTTPS-tanúsítványt. Először csak a webet indítsd, végezd el az alábbi próbát, majd indítsd a workert.

Új gépen a Let's Encrypt-tanúsítvány újra kiadható; a régi tanúsítvány privát kulcsát nem szükséges a nyilvános forráshoz csatolni.

## Visszaállítási próba és megőrzés

Jegyezd fel a mentés és a próba időpontját, a forrásverziót és az eredményt. Ellenőrizd legalább:

- Felhasználók, projektek és feladatok száma, belépés és jogosultságok.
- Egy hozzászólás, csatolmány és személyes megjelenési/értesítési beállítás.
- Migrációs állapot és a web/worker naplói.
- Éles váltáskor az SMTP, Google és push működése; próbán csak elkülönített tesztcímzettet használj.

Az adatbázis/volume visszaállítását időnként gyakorold. A megtartási időt a saját igényedhez állítsd; a külön gépen lévő titkosított példány és a tőle külön megőrzött kulcs véd a VPS elvesztése ellen is. Ez a projekt automatikus mentési ütemezést nem hoz létre.
