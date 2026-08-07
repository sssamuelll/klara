#!/usr/bin/env bash
# Deploy manual de Klara a producción (klara.sdar.dev).
#
# Reemplaza .github/workflows/build-and-deploy.yml, que quedó apagado el
# 2026-08-07: los repos pasaron a privados y cada corrida de Actions se cobra.
# Mismo movimiento que se hizo en Atrium el 2026-08-01.
#
# CUATRO REGLAS QUE ESTE SCRIPT EXISTE PARA HACER CUMPLIR:
#
#  1. Los gates corren ANTES del build. Sin CI en el PR, este es el único sitio
#     donde un test roto se atrapa antes de producción.
#  2. La copia de la base va antes de tocar nada, y se VERIFICA. Klara tiene
#     usuarios reales: historias, progreso SRS, intentos de pronunciación.
#  3. El build es LOCAL. La caja tiene 1,9 GB de RAM — npm ci / vite / uv sync
#     allá es OOM. Viajan artefactos; en la caja sólo se hace COPY.
#  4. Nada de GHCR. En repo privado el registry también se cobra: las imágenes
#     viajan por SSH (docker save | docker load).
#
# Lo que viaja en un deploy normal: el dist del frontend (~1 MB) y el src del
# backend (unos cientos de KB). La base pesada del backend (python + ffmpeg +
# venv, ~1,4 GB) sólo viaja cuando cambian pyproject.toml o uv.lock, y eso lo
# decide un hash, no yo.
#
# Uso:
#   scripts/deploy-prod.sh              # deploy completo
#   scripts/deploy-prod.sh --solo-copia # sólo la copia de la base
#   scripts/deploy-prod.sh --sin-gates  # salta los gates (sólo si ya corrieron)
#   scripts/deploy-prod.sh --ensayo     # todo menos levantar: valida sin tocar
#                                       # un contenedor vivo
#
# Rollback: las imágenes quedan tagueadas por sha en la caja.
#   ssh atrium-aws "docker images | grep klara"
#   ssh atrium-aws "cd ~/klara && IMAGE_TAG=sha-XXXXXXX \
#     docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"

set -euo pipefail

HOST="atrium-aws"
REMOTE_DIR="klara"                    # ~/klara en la caja
REPO_BACK="ghcr.io/sssamuelll/klara-backend"   # nombre heredado: lo referencia
REPO_FRONT="ghcr.io/sssamuelll/klara-frontend" # el compose. Ya no se sube a GHCR.
LOCAL_BACKUPS="/d/Desktop/projects/_backups/klara"
REMOTE_BACKUPS="backups/klara"
RETENCION=20

SOLO_COPIA=0; SIN_GATES=0; ENSAYO=0
for arg in "$@"; do
  case "$arg" in
    --solo-copia) SOLO_COPIA=1 ;;
    --sin-gates)  SIN_GATES=1 ;;
    --ensayo)     ENSAYO=1 ;;
    *) echo "opción desconocida: $arg" >&2; exit 2 ;;
  esac
done

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

paso()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()    { printf '   \033[32m%s\033[0m\n' "$*"; }
fallo() { printf '\033[31mFALLO: %s\033[0m\n' "$*" >&2; exit 1; }

# ── 0. Qué se va a desplegar ────────────────────────────────────────────────
paso "0. Qué se va a desplegar"

RAMA="$(git rev-parse --abbrev-ref HEAD)"
SHA="$(git rev-parse --short=7 HEAD)"
TAG="sha-${SHA}"

[ "$RAMA" = "main" ] || fallo "estás en '$RAMA'. Producción se despliega desde main."
# Un árbol sucio significa que lo desplegado no es lo que dice el sha, y el sha
# es lo único que permite reproducir o revertir después.
[ -z "$(git status --porcelain -- backend frontend docker-compose.yml docker-compose.prod.yml)" ] \
  || fallo "hay cambios sin commitear en backend/, frontend/ o los compose."

echo "   rama:   $RAMA"
echo "   commit: $SHA — $(git log -1 --pretty=%s | cut -c1-70)"
echo "   tag:    $TAG"

# ── 1. Gates ────────────────────────────────────────────────────────────────
# Derivados de .github/workflows/ci.yml, que se mantiene en el repo justamente
# como receta aunque ya no se ejecute. Si ci.yml cambia, esta lista cambia.
if [ "$SOLO_COPIA" = 0 ] && [ "$SIN_GATES" = 0 ]; then
  paso "1. Gates (los mismos de ci.yml)"

  ( cd backend && uv run ruff check src tests )        || fallo "ruff check"
  ( cd backend && uv run ruff format --check src tests ) || fallo "ruff format"
  ok "ruff"

  ( cd frontend && npm run typecheck )  || fallo "typecheck del frontend"
  ( cd frontend && npm run i18n:check ) || fallo "i18n"
  ( cd frontend && npm run test )       || fallo "vitest"
  ok "frontend: typecheck + i18n + tests"

  # pytest necesita Postgres. Se corre de último porque es el más lento (~3 min)
  # y así los errores baratos salen primero.
  ( cd backend && uv run pytest tests/ -q ) || fallo "pytest"
  ok "pytest"
else
  paso "1. Gates — SALTADOS"
fi

# ── 2. Copia de la base, verificada ─────────────────────────────────────────
# Va antes de tocar nada: si el deploy sale mal, el punto de retorno ya existe.
#
# Se vuelca a `.parcial` y sólo se renombra cuando pg_restore confirma que el
# archivo tiene contenido. El motivo: la redirección `>` CREA el archivo antes
# de correr el comando, así que un pg_dump que falla deja un dump de 0 bytes con
# nombre de respaldo — un archivo que parece copia y no lo es, que se descubre
# el día que hace falta.
#
# Todo el pg_dump ocurre EN la caja: el usuario y la base salen de ~/klara/.env,
# que es la única copia viva de esos valores y no debe salir de allá.
paso "2. Copia de la base"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
ssh "$HOST" bash -s -- "$REMOTE_BACKUPS" "$TS" "$RETENCION" <<'REMOTO' || fallo "la copia de la base"
set -euo pipefail
DIR="$1"; TS="$2"; RET="$3"
cd ~/klara
set -a; . ./.env; set +a
mkdir -p ~/"$DIR"
OUT=~/"$DIR"/klara-"$TS".dump
docker exec klara_postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$OUT".parcial
if [ ! -s "$OUT".parcial ] || ! docker exec -i klara_postgres pg_restore -l < "$OUT".parcial >/dev/null 2>&1; then
  rm -f "$OUT".parcial
  echo "el dump salió vacío o ilegible" >&2
  exit 1
fi
mv "$OUT".parcial "$OUT"
echo "   copia verificada en la caja: $OUT ($(du -h "$OUT" | cut -f1))"
ls -1t ~/"$DIR"/klara-*.dump 2>/dev/null | tail -n +$((RET+1)) | xargs -r rm -f
REMOTO

mkdir -p "$LOCAL_BACKUPS"
scp -q "$HOST:${REMOTE_BACKUPS}/klara-${TS}.dump" "$LOCAL_BACKUPS/klara-${TS}.dump.parcial" \
  || fallo "trayendo la copia a local"
REMOTO_SHA="$(ssh "$HOST" "sha256sum ${REMOTE_BACKUPS}/klara-${TS}.dump | cut -d' ' -f1")"
LOCAL_SHA="$(sha256sum "$LOCAL_BACKUPS/klara-${TS}.dump.parcial" | cut -d' ' -f1)"
[ "$REMOTO_SHA" = "$LOCAL_SHA" ] || { rm -f "$LOCAL_BACKUPS/klara-${TS}.dump.parcial"; fallo "el checksum de la copia local no calza"; }
mv "$LOCAL_BACKUPS/klara-${TS}.dump.parcial" "$LOCAL_BACKUPS/klara-${TS}.dump"
ok "copia local verificada: $LOCAL_BACKUPS/klara-${TS}.dump"
ls -1t "$LOCAL_BACKUPS"/klara-*.dump 2>/dev/null | tail -n +$((RETENCION+1)) | xargs -r rm -f

if [ "$SOLO_COPIA" = 1 ]; then
  paso "Listo (--solo-copia): no se desplegó nada."
  exit 0
fi

# ── 3. Base del backend: sólo viaja si cambió ───────────────────────────────
# El hash sale de pyproject.toml + uv.lock. Es una comparación, no una
# corazonada: si el hash ya está en la caja, no se manda 1,4 GB por gusto.
paso "3. Base del backend"

HASH_BASE="$(cat backend/pyproject.toml backend/uv.lock | sha256sum | cut -c1-12)"
BASE_TAG="klara-backend-base:${HASH_BASE}"
echo "   hash de dependencias: $HASH_BASE"

if ssh "$HOST" "docker image inspect '$BASE_TAG' >/dev/null 2>&1"; then
  ok "la base ya está en la caja — no se manda"
else
  echo "   no está allá: construyendo en local y enviando (esto tarda)"
  docker build -f backend/Dockerfile.base -t "$BASE_TAG" ./backend \
    || fallo "construyendo la base del backend"
  docker save "$BASE_TAG" | gzip -1 | ssh "$HOST" "gunzip | docker load" \
    || fallo "enviando la base del backend"
  ok "base enviada"
fi

# ── 4. Build local de los artefactos ────────────────────────────────────────
paso "4. Build local"

( cd frontend && npm run build ) || fallo "build del frontend"
DIST_KB="$(du -sk frontend/dist | cut -f1)"
ok "dist del frontend: ${DIST_KB} KB"

# ── 5. Envío y ensamblado en la caja ────────────────────────────────────────
# Git Bash no trae rsync; la caja sí, pero para esto alcanza tar sobre ssh.
paso "5. Envío y ensamblado"

ssh "$HOST" "rm -rf /tmp/klara-deploy && mkdir -p /tmp/klara-deploy/backend /tmp/klara-deploy/frontend"

tar -C backend -czf - src alembic alembic.ini Dockerfile.app \
  | ssh "$HOST" "tar -C /tmp/klara-deploy/backend -xzf -" || fallo "enviando el backend"
tar -C frontend -czf - dist nginx.conf Dockerfile.assemble \
  | ssh "$HOST" "tar -C /tmp/klara-deploy/frontend -xzf -" || fallo "enviando el frontend"
ok "artefactos enviados"

ssh "$HOST" bash -s -- "$BASE_TAG" "$REPO_BACK" "$REPO_FRONT" "$TAG" <<'REMOTO' || fallo "ensamblando las imágenes"
set -euo pipefail
BASE="$1"; RB="$2"; RF="$3"; TAG="$4"
docker build --build-arg BASE="$BASE" -f /tmp/klara-deploy/backend/Dockerfile.app \
  -t "$RB:$TAG" /tmp/klara-deploy/backend
docker build -f /tmp/klara-deploy/frontend/Dockerfile.assemble \
  -t "$RF:$TAG" /tmp/klara-deploy/frontend
rm -rf /tmp/klara-deploy
REMOTO
ok "imágenes ensambladas: $TAG"

if [ "$ENSAYO" = 1 ]; then
  paso "Listo (--ensayo): las imágenes existen en la caja, no se levantó nada."
  echo "   para levantarlas: ssh $HOST \"cd ~/$REMOTE_DIR && IMAGE_TAG=$TAG docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d\""
  exit 0
fi

# ── 6. Compose y levantada ──────────────────────────────────────────────────
# Los compose viajan por scp: la caja no puede hacer git fetch (repo privado sin
# credencial, y así se queda). .env NO se toca: el de allá es la única copia.
paso "6. Levantando"

scp -q docker-compose.yml docker-compose.prod.yml "$HOST:${REMOTE_DIR}/" || fallo "enviando los compose"

ssh "$HOST" "cd ~/$REMOTE_DIR && IMAGE_TAG=$TAG docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d" \
  || fallo "levantando los contenedores"

# ── 7. Verificación ─────────────────────────────────────────────────────────
# Desde local a propósito: un curl desde la caja hacia el propio dominio no
# vuelve por el hairpin contra la Elastic IP y da un 404 engañoso.
paso "7. Verificación"

ssh "$HOST" "docker ps --filter name=klara --format '   {{.Names}}\t{{.Image}}\t{{.Status}}'"

for intento in $(seq 1 20); do
  CODIGO="$(curl -s -o /dev/null -w '%{http_code}' https://klara.sdar.dev/api/v1/health || true)"
  [ "$CODIGO" = "200" ] && break
  sleep 3
done
[ "$CODIGO" = "200" ] || fallo "el backend no respondió 200 en /api/v1/health (último: $CODIGO)"
ok "backend 200"

FRONT="$(curl -s -o /dev/null -w '%{http_code}' https://klara.sdar.dev/ || true)"
[ "$FRONT" = "200" ] || fallo "el frontend respondió $FRONT"
ok "frontend 200"

# Que el HTML servido apunte al bundle que acabamos de construir. Sin esto un
# nginx sirviendo caché vieja pasaría por deploy exitoso.
SERVIDO="$(curl -s https://klara.sdar.dev/ | grep -o 'assets/index-[A-Za-z0-9_-]*\.js' | head -1 | sed 's|assets/||')"
CONSTRUIDO="$(ls -1 frontend/dist/assets/ | grep -o 'index-[A-Za-z0-9_-]*\.js' | head -1)"
if [ "$SERVIDO" = "$CONSTRUIDO" ]; then
  ok "bundle servido = bundle construido ($SERVIDO)"
else
  fallo "el bundle servido ($SERVIDO) no es el que se construyó ($CONSTRUIDO)"
fi

paso "Desplegado: $TAG"
echo "   rollback: ssh $HOST \"cd ~/$REMOTE_DIR && IMAGE_TAG=sha-XXXXXXX docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d\""
