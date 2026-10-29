# Telepítés és frissítés

Válassz Docker/PostgreSQL vagy natív Ubuntu/MariaDB telepítést. Ne futtasd ugyanazon az alkalmazásporton mindkettőt. Mindkettő külön aldomain mögött, a meglévő WordPress-oldalak mellett használható. A példákban `projekt.sajatdomain.hu` a saját címedre cserélendő.

Élesítés előtt cseréld a [logókat és a nevet](../BRANDING.md). A `.env.example` tájékoztató minta; a valódi, egyedi kulcsokat a `scripts/configure.py` generálja. A `.env` nem kerülhet Gitbe.

## Docker + PostgreSQL

Előfeltétel: működő Docker Engine és Compose plugin, DNS-rekord a szerverre, szabad `127.0.0.1:8094` port és HTTPS-t végző reverse proxy.

```sh
git clone https://github.com/kobak/kjbk-projekt-guru.git
cd kjbk-projekt-guru
```

A környezetet létrehozhatod Python telepítése nélkül, a Compose frontendtől független képfelépítésével:

```sh
docker build --tag kozos:local .
docker run --rm --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD,dst=/app" \
  --entrypoint python kozos:local scripts/configure.py \
  --url https://projekt.sajatdomain.hu
chmod 600 .env
```

Alternatíva: Python 3.12-környezetben telepítsd a `requirements.lock` függőségeit, és futtasd a `python scripts/configure.py --url https://projekt.sajatdomain.hu` parancsot. Meglévő `.env` fájlt egyik módszer sem ír felül.

A `.env` fájlban a `VAPID_SUBJECT` legyen a saját működő kapcsolati e-mail-címed, például `mailto:admin@sajatdomain.hu`. Ellenőrizd az `APP_URL` és `ALLOWED_HOSTS` értékeit.

```sh
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose exec app python manage.py setup_workspace
```

A webfolyamat induláskor migrál és gyűjti a statikus fájlokat. A worker az egészséges webfolyamatra vár; egy példányban futtasd. Az első admin e-mail-címét, nevét és jelszavát az interaktív `setup_workspace` parancs kéri. A többi felhasználó a **Beállítások → Csapat** részen hívható meg; a meghívó linkjét az admin továbbítja.

Adatok: `database` és `attachments` nevű Compose-volume. A Compose-projekt neve `kozos`, ezért az ugyanazon Docker-gépen futó második telepítéshez külön projektnevet és alkalmazásportot kell választani. **A `docker compose down -v` törli a volume-okban lévő adatokat.**

## Reverse proxy és HTTPS

A belső alkalmazásport csak a `127.0.0.1:8094` címen figyeljen. Ne nyisd ki publikus portra; a proxy ellenőrzött `Host` és `X-Forwarded-Proto` fejlécet továbbítson. A beépített HTTPS-átirányítás miatt a HTTPS-vhostban `X-Forwarded-Proto: https` szükséges.

- Apache-példa: `deploy/apache.conf.example`. Szükséges modulok: `proxy`, `proxy_http`, `headers`, `ssl`.
- Részletes natív HTTP/HTTPS-példák: `deploy/apache-http.conf.example`, `deploy/apache-ssl.conf.example`.
- Nginx-példa: `deploy/nginx.conf.example`.

Az új vhost legyen külön fájl, a meglévő WordPress-konfigurációkat ne írd felül. Előbb állítsd be a DNS-t és a HTTP-vhostot, majd kérj tanúsítványt, például `certbot --apache -d projekt.sajatdomain.hu` vagy `certbot --nginx -d projekt.sajatdomain.hu` segítségével. A TLS-példát csak létező tanúsítvánnyal kapcsold be. Újratöltés előtt `apache2ctl configtest`, illetve `nginx -t` szükséges.

A webroot tanúsítványkéréshez a HTTP-példa `/var/lib/kozos-acme/.well-known/acme-challenge/` könyvtárát is hozd létre. A `deploy/kozos-cert-renew-hook` opcionális példa: a saját domainedre átírva, root tulajdonnal telepíthető a Certbot deploy hookjai közé. A szolgáltatók DNS- és megújítási beállításai telepítésenként eltérhetnek.

Cloudflare proxy esetén **Full (strict)** TLS-mód kell; a Flexible mód átirányítási hurkot okozhat. DNS only esetén a VPS érvényes tanúsítványa szolgálja ki a böngészőt.

## Natív Ubuntu + MariaDB

A mellékelt systemd-példák `/opt/kozos` útvonalat, `kozos` szolgáltatásfiókot és helyi `kozos` MariaDB-adatbázist használnak. A kialakítás Ubuntu 22.04 / Python 3.10 / MariaDB 10.6 környezetben is működik. Más környezetben előbb külön teszttelepítésen próbáld ki.

Szükséges: Python + venv + fejlesztői fejlécek, MariaDB, C fordító, `pkg-config`, MariaDB/MySQL kliensfejlesztői csomagok, Node.js 22, Gunicorn és Apache vagy Nginx. A meglévő WordPress adatbázisaihoz ne nyúlj. A rendszerfelhasználó és adatbázis neve legyen kizárólag az alkalmazásé.

Egy friss telepítés vázlata:

```sh
sudo useradd --system --home-dir /opt/kozos --shell /usr/sbin/nologin kozos
sudo git clone https://github.com/kobak/kjbk-projekt-guru.git /opt/kozos
cd /opt/kozos
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements-native.lock
sudo .venv/bin/python scripts/configure.py --url https://projekt.sajatdomain.hu
sudo .venv/bin/python deploy/provision_native.py
```

A natív lock Python 3.10-hez rögzített környezet. Más Python-verzión új feloldáshoz a `requirements-mariadb.txt` használható. A `provision_native.py` csak helyi `/opt/kozos` telepítéshez és a külön `kozos` adatbázishoz való. Már létező adatbázis/felhasználó esetén, konfigurált `DATABASE_URL` nélkül leáll, hogy ne állítson be hozzájuk ismeretlen új jelszót. Meglévő telepítés frissítésekor ne generálj új környezetet és ne futtasd újra az első telepítőt.

A forrás legyen root/telepítő tulajdonában, a `.env` csak a `kozos` szolgáltatásfiók számára olvasható (`0600`), a `media/` számára írható. A provisioning ezt a két útvonalat beállítja; a többi forrásfájl nem igényel írási jogot a szolgáltatástól.

```sh
sudo npm --prefix frontend ci
sudo npm --prefix frontend run build
sudo .venv/bin/python manage.py migrate --noinput
sudo .venv/bin/python manage.py collectstatic --noinput
sudo -u kozos .venv/bin/python manage.py setup_workspace
sudo install -m 644 deploy/kozos.service /etc/systemd/system/kozos.service
sudo install -m 644 deploy/kozos-worker.service /etc/systemd/system/kozos-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now kozos kozos-worker
```

A szolgáltatások loopbacken, egy Gunicorn munkásfolyamattal és négy szállal működnek; a példák 1 GB-os VPS-hez memóriahatárokat is adnak. A kapacitást saját terhelés alapján méretezd. A HTTPS/proxy beállítása ezután az előző fejezet szerint következik.

## Frissítés

1. Jegyezd fel az aktuális commitot: `git rev-parse HEAD`. Készíts [teljes mentést](backup-and-restore.md), és olvasd el a kiadás változásnaplóját.
2. Tiszta munkakönyvtárban `git fetch --tags`, majd válts az ellenőrzött kiadás címkéjére, például `git switch --detach v1.0.0`. Helyi módosításokat ne írj felül.
3. Docker: `docker compose up -d --build`. Az adatvolume-okat és a `.env` fájlt őrizd meg.
4. Natív: állítsd le a workert és az alkalmazást; szükség szerint frissítsd a függőségeket, futtasd az `npm ci`, `npm run build`, `manage.py migrate --noinput`, `manage.py collectstatic --noinput` lépéseket, majd `sudo systemctl start kozos kozos-worker`.
5. Ellenőrizd a bejelentkezést, egy projekt megnyitását, a `/health/` választ, a szolgáltatásokat és a naplókat. Az SMTP/Google/push küldést külön is ellenőrizd, ha ezek konfigurációja változott.

Sémafrissítés utáni visszalépésnél önmagában a régi Git-verzióra váltás nem feltétlenül elég: az adott kódhoz illő adatbázismentést is vissza kell állítani.

## Üzemeltetési ellenőrzések

```sh
# Docker
docker compose ps
docker compose logs --tail=100 app worker
docker compose exec app python manage.py check --deploy

# Natív
sudo systemctl status kozos kozos-worker
sudo journalctl -u kozos -u kozos-worker --since '30 minutes ago'
sudo -u kozos /opt/kozos/.venv/bin/python /opt/kozos/manage.py check --deploy
```

A HSTS aldomain/preload opciói nincsenek bekapcsolva, mert ugyanazon domainen más szolgáltatások is lehetnek. A Django erre figyelmeztethet; csak akkor módosítsd, ha az összes érintett aldomain HTTPS-üzemét biztosítani tudod.

Elfelejtett jelszóhoz a szerver adminja futtathatja a `manage.py changepassword felhasznalo@example.com` parancsot az adott környezetben. Ez interaktív; ne adj jelszót parancssori argumentumban vagy issue-ban.
