# GitHub Actions workflows — klara

3 workflows + Dependabot.

| Workflow | Trigger | Función |
|---|---|---|
| `ci.yml` | `pull_request`, `push` a `main` | pytest, ruff, migration roundtrip, frontend typecheck/build/i18n, docker build smoke |
| `build-and-deploy.yml` | `push` a `main`, `workflow_dispatch` | build imágenes → push GHCR → SSH deploy → health check |
| `codeql.yml` | `pull_request`, `push` a `main`, weekly cron | CodeQL python + javascript-typescript |
| `../dependabot.yml` | weekly | Auto-bumps de las action versions |

## Cómo deployar manualmente (rollback / re-deploy)

1. Ve a `Actions` → `Build & Deploy` → `Run workflow`.
2. Selecciona la rama `main`.
3. (Opcional) En `Tag a deployar`, pon un tag anterior: `sha-abc1234` (visible en el run de Actions o en `ghcr.io/sssamuelll/klara-backend`).
4. Run.

Si no especificas `image_tag`, se deploya el SHA actual de `main`.

**Rollback con migration entre versiones**: si entre el tag objetivo y `main` hay una migration destructiva, el rollback con `image_tag` no la revierte. En ese caso: revertir el commit en main + push (genera deploy nuevo de imagen actualizada).

## Branch protection (manual, una vez)

Settings → Branches → Add rule para `main`:

- Require status checks before merge:
  - `backend / pytest`
  - `backend / ruff`
  - `backend / migration roundtrip`
  - `frontend / typecheck + build + i18n`
  - `docker / build smoke (backend)`
  - `docker / build smoke (frontend)`
  - `CodeQL (python)`
  - `CodeQL (javascript-typescript)`
- Require branches up to date before merging
- Require linear history
- Restrict pushes (solo via PRs)

## Disaster recovery (server perdido)

1. SSH a una máquina nueva, `git clone https://github.com/sssamuelll/klara.git ~/klara`.
2. Verificar postgres data o partir limpio.
3. Si imágenes son privadas: `echo "$GHCR_PULL_TOKEN" | docker login ghcr.io -u sssamuelll --password-stdin`. Si públicas (recomendado), skip.
4. GitHub UI → `Build & Deploy` → Run workflow on `main`.

`.env` se regenera desde secrets, imágenes se pulean de GHCR, containers arrancan.

## Server caveats

- **No commitees en el server**. El deploy ejecuta `git reset --hard origin/main`, lo que descarta cualquier commit local. Si necesitas un hotfix urgente, push una rama y dispatcha el workflow contra `main`.
- **Postgres volume es el único punto donde vive la data**. Implementar backups (cron `pg_dump | gzip` + offsite) antes de tratar prod como crítico.
