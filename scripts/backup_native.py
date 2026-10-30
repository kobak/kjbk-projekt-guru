#!/usr/bin/env python3
"""Consistent, manual backup for the native MariaDB/systemd deployment."""
import gzip
import json
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

if os.geteuid() != 0:
    raise SystemExit("Futtasd sudo-val, a szerveren.")
root = Path("/opt/kozos")
if not (root / ".env").exists():
    raise SystemExit("A /opt/kozos/.env nem található.")
os.umask(0o077)
dest = Path("/var/backups/kozos") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
dest.mkdir(parents=True, exist_ok=False)
active = [name for name in ("kozos-worker", "kozos") if subprocess.run(["systemctl", "is-active", "--quiet", name]).returncode == 0]
try:
    if active:
        subprocess.run(["systemctl", "stop", *active], check=True)
    process = subprocess.Popen(["mariadb-dump", "--single-transaction", "--quick", "--skip-lock-tables", "kozos"], stdout=subprocess.PIPE)
    with gzip.open(dest / "database.sql.gz", "wb") as output:
        shutil.copyfileobj(process.stdout, output)
    if process.wait() != 0:
        raise RuntimeError("Az adatbázismentés sikertelen; a mappa nem teljes mentés.")
    with tarfile.open(dest / "attachments.tar.gz", "w:gz") as archive:
        archive.add(root / "media", arcname="media")
    shutil.copy2(root / ".env", dest / "environment.env")
    os.chmod(dest / "environment.env", 0o600)
    # A futó példány forrása is kell; a függőségek a lockokból újratelepíthetők.
    source_paths = ["config", "core", "templates", "scripts", "deploy", "docs", "frontend/src", "frontend/public", "frontend/dist",
        "frontend/tests", "frontend/index.html", "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json", "frontend/vite.config.ts",
        "manage.py", "Dockerfile", "compose.yaml", ".env.example", ".gitignore", ".dockerignore", "README.md", "LICENSE", "BRANDING.md",
        "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", "requirements.txt", "requirements.lock",
        "requirements-mariadb.txt", "requirements-native.lock", ".github"]
    def source_filter(info):
        return None if "__pycache__" in Path(info.name).parts or info.name.endswith(".pyc") else info
    with tarfile.open(dest / "source.tar.gz", "w:gz") as archive:
        for relative in source_paths:
            if (root / relative).exists():
                archive.add(root / relative, arcname=relative, filter=source_filter)
    revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True)
    (dest / "source-commit.txt").write_text(revision.stdout if revision.returncode == 0 else "Ismeretlen Git-verzió; a source.tar.gz a mentett példány pontos forrása.\n")
    (dest / "manifest.json").write_text(json.dumps({"application": "kjbk projekt guru", "database": "MariaDB", "created_at": datetime.now(timezone.utc).isoformat(),
        "files": ["database.sql.gz", "attachments.tar.gz", "environment.env", "source.tar.gz", "source-commit.txt"]}, ensure_ascii=False, indent=2) + "\n")
    (dest / "COMPLETE").write_text("Kozos: MariaDB + media + environment + source\n")
    print(f"Teljes mentés: {dest}")
finally:
    if active:
        subprocess.run(["systemctl", "start", *reversed(active)], check=True)
