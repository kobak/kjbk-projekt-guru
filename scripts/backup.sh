#!/bin/sh
# Konzisztens, kézi Docker-mentés; röviden leállítja a webet és a workert.
set -eu
umask 077
cd "$(dirname "$0")/.."
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dest="backups/$stamp"
mkdir -p backups
mkdir "$dest"
active=""
for service in $(docker compose ps --services --status running); do
    case "$service" in app|worker) active="$active $service" ;; esac
done
cleanup() {
    # active kizárólag az előbb felsorolt app/worker szolgáltatásneveket tartalmazza.
    if [ -n "$active" ]; then docker compose start $active; fi
}
trap cleanup EXIT
docker compose stop worker app
docker compose exec -T db pg_dump -U kozos -d kozos -Fc > "$dest/database.dump"
docker compose run --rm --no-deps -T --entrypoint tar app -C /app/media -czf - . > "$dest/attachments.tar.gz"
cp .env "$dest/environment.env"
if git rev-parse HEAD > "$dest/source-commit.txt" 2>/dev/null; then
    git archive --format=tar.gz HEAD > "$dest/source.tar.gz"
else
    printf 'Nem Git-munkakönyvtár; az alkalmazás forrását külön őrizd meg.\n' > "$dest/source-commit.txt"
fi
printf 'PostgreSQL + media + environment; Git-forrás, ha elérhető.\n' > "$dest/COMPLETE"
printf 'Mentés kész: %s\nA mentés titkos adatokat tartalmaz; titkosítva, külön gépen tárold.\n' "$dest"
