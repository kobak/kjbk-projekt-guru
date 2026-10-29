#!/usr/bin/env python3
"""Root-only, native VPS database setup. Keeps generated credentials out of stdout."""
import os
import pwd
import re
import secrets
import subprocess
from pathlib import Path
from urllib.parse import urlparse, unquote
from dotenv import dotenv_values

if os.geteuid() != 0:
    raise SystemExit("Root jogosultság kell.")
root = Path(__file__).resolve().parent.parent
if root != Path("/opt/kozos"):
    raise SystemExit("Ez a telepítő csak a /opt/kozos könyvtárban használható.")
env = root / ".env"
values = dotenv_values(env)
app_url = urlparse(values.get("APP_URL") or "")
if app_url.scheme != "https" or not app_url.hostname or app_url.path not in ("", "/") or app_url.query or app_url.fragment or app_url.username:
    raise SystemExit("Előbb generáld a .env fájlt a végleges domainnel.")
url = values.get("DATABASE_URL")
if not url:
    existing = subprocess.run(["mysql", "-N", "-e", "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='kozos'; SELECT COUNT(*) FROM mysql.user WHERE User='kozos' AND Host='localhost';"], check=True, capture_output=True, text=True)
    if any(int(value) for value in existing.stdout.split()):
        raise SystemExit("Már létezik kozos adatbázis vagy felhasználó. Nem generálok hozzá új kulcsot; ellenőrizd a meglévő konfigurációt.")
    password = secrets.token_urlsafe(40)
    url = f"mysql://kozos:{password}@localhost:3306/kozos"
    with env.open("a") as f:
        f.write(f"DATABASE_URL={url}\n")
else:
    parsed = urlparse(url)
    if parsed.scheme not in ("mysql", "mariadb") or parsed.hostname != "localhost" or parsed.path != "/kozos" or parsed.username != "kozos" or parsed.port not in (None, 3306):
        raise SystemExit("Ez a segéd csak a helyi kozos MariaDB-adatbázist kezeli.")
    password = unquote(parsed.password or "")
if not re.fullmatch(r"[A-Za-z0-9_-]{30,100}", password):
    raise SystemExit("A generált adatbáziskulcs formátuma hibás.")
sql = f"""CREATE DATABASE IF NOT EXISTS kozos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'kozos'@'localhost' IDENTIFIED BY '{password}';
GRANT ALL PRIVILEGES ON kozos.* TO 'kozos'@'localhost';
"""
subprocess.run(["mysql"], input=sql, text=True, check=True, capture_output=True)
account = pwd.getpwnam("kozos")
os.chmod(env, 0o600)
os.chown(env, account.pw_uid, account.pw_gid)
media = root / "media"
media.mkdir(exist_ok=True)
os.chown(media, account.pw_uid, account.pw_gid)
os.chmod(media, 0o700)
print("Elkülönített adatbázis és alkalmazásjogosultságok elkészültek.")
