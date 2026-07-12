# Klara

A personal language-learning app built around an LLM tutor named **Klara**.

Klara supports six languages — `de`, `en`, `fr`, `ja`, `pt`, `es` — as either the
target (what you're learning) or native (what the UI talks back in). Each user
picks their own pair in Settings; the app's source-of-truth is the user row.

## Stack

- **Backend**: FastAPI + SQLAlchemy async + Alembic on PostgreSQL 16, packaged
  as `klara`. Auth uses fastapi-users with cookie sessions and optional Google
  OAuth.
- **Frontend**: React + Vite + TypeScript, six locales under
  `frontend/src/locales/` (Spanish is the source of truth, enforced by
  `npm run i18n:check`). Ships as an installable PWA — `vite-plugin-pwa`
  generates an auto-updating service worker, and `/api` is excluded from the
  SPA fallback so OAuth callbacks pass through.
- **LLM**: provider-agnostic via LiteLLM. Three model slots — story, chat,
  correction — are configured independently (`LLM_STORY_MODEL`,
  `LLM_CHAT_MODEL`, `LLM_CORRECTION_MODEL`). Anthropic, DeepSeek, and OpenAI
  keys are accepted; the model string picks which provider gets called.
- **TTS**: two providers behind a single `TTSProvider` protocol — ElevenLabs
  and Inworld. Per-language voice overrides (`ELEVENLABS_VOICE_ID_DE`, etc.)
  matter because one voice that nails German rarely sounds native in Spanish.
  Inworld voices are language-locked by design. Each provider has two model
  tiers — a realtime model for Speak replies and an expressive narration model
  for pre-cached story audio (`ELEVENLABS_MODEL` /
  `ELEVENLABS_NARRATION_MODEL`). Synthesised audio is cached in
  Postgres (`audio_cache`) keyed by `(provider, model, voice, lang, text)`.
- **STT + pronunciation scoring**: Azure Cognitive Services Speech. Audio is
  uploaded from the browser in any container format, transcoded to 16 kHz mono
  WAV via ffmpeg in the backend container, and sent to Azure Pronunciation
  Assessment. The response carries per-word and per-phoneme accuracy.
- **Orchestration**: Docker Compose for local; an overlay
  (`docker-compose.prod.yml`) swaps `build:` for GHCR-published images in prod.

## Repository layout

```
app/
├── backend/                # FastAPI app (Python package: klara)
│   ├── src/klara/
│   │   ├── routers/        # stories, srs, gender, modules, practice, speak, tts, pronunciation, users, invitations, health
│   │   ├── curriculum/     # learning-path modules, story library, word selection, gender oracle + rules, L1 notes
│   │   ├── pronunciation/  # Azure client (batch + streaming), ffmpeg transcode, response schemas
│   │   ├── tts/            # ElevenLabs + Inworld implementations of TTSProvider
│   │   ├── llm/            # LiteLLM-backed LLMClient + prompts
│   │   ├── services/       # story_gen, finish_lessons, srs_engine, gender_grading, practice_*, speak_*, pronunciation_diagnose, phonetic_hints, voice_mc, tts_*
│   │   ├── auth/           # fastapi-users wiring, invitations, OAuth, email
│   │   ├── models/         # SQLAlchemy models (users, stories, srs, attempts, audio_cache, …)
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── scripts/        # seeders (load_de_*), build_story_library, rewarm_audio_cache
│   │   └── i18n/           # backend message catalog + language registry
│   ├── alembic/versions/   # migrations (one file per schema change)
│   └── tests/              # pytest suite (see "Tests" below)
├── frontend/
│   └── src/
│       ├── routes/         # Home, NewStory, Story, Practice, Speak, Module, GenderReview, Settings, auth screens
│       ├── components/     # SentenceView, StoryFinish, WordPopover, GenderReviewSession, …
│       ├── onboarding/     # first-run setup flow (/onboarding)
│       ├── lib/            # auth, pronunciation, streamClient + pcmCapture (live scoring), tts, silenceDetector, preferences
│       ├── api/            # typed fetch client
│       └── locales/        # de / en / es / fr / ja / pt (source: es)
├── docs/                   # runbooks/ (ops procedures) + superpowers/ (design plans & specs)
├── docker-compose.yml
├── docker-compose.prod.yml
└── .github/workflows/      # CI + build-and-deploy (see workflows/README.md)
```

## Local setup

1. Copy `.env.example` to `.env` and fill in the keys you actually need:

   ```bash
   cp .env.example .env
   ```

   At minimum, set an LLM key matching whichever provider is in
   `LLM_*_MODEL`. TTS, pronunciation, and Google OAuth are optional — their
   endpoints return `503` when their keys are missing so the frontend can fall
   back gracefully.

2. Bring everything up:

   ```bash
   docker compose up --build
   ```

3. Open:
   - Frontend: <http://localhost:5273>
   - Backend (OpenAPI): <http://localhost:8000/docs>
   - Postgres: `localhost:5432` (user/password from `.env`)

Alembic runs `alembic upgrade head` on backend container start, so the first
boot creates the schema.

### Bootstrapping the first user

Signup is invite-only — every new account requires a token issued by an admin.
For the very first user (chicken-and-egg), set `INITIAL_OWNER_EMAIL` in `.env`
before the first run. The lifespan hook plants a legacy user row, and that
email's first signup adopts the row and becomes a superuser. After that, the
owner issues invites from the admin panel (`/api/v1/admin/invitations`).

### Seeding the curriculum

A fresh database has no learning-path modules — `GET /api/v1/modules/current`
returns null — until the seed scripts in `backend/src/klara/scripts/` run.
Nothing runs them automatically. For a local dev database (against the compose
`backend` service):

```bash
# the 8 A1 modules — self-contained; the minimum for the learning path to work
docker compose exec backend python -m klara.scripts.load_de_modules
# optional: the 20 ES→DE gender trap notes — self-contained
docker compose exec backend python -m klara.scripts.load_de_l1_notes
# optional: pre-generate + pre-cache the story library so module story-claims
# skip the LLM (costs LLM + TTS credits)
docker compose exec backend python -m klara.scripts.build_story_library
```

The der/die/das gender oracle (`load_de_gender`) and the frequency/CEFR data
(`load_de_lexical`) need datasets that aren't vendored in the repo, and the
gender loaders have a strict ordering constraint. Turning the gender axis on —
in dev or prod — is documented end to end in
[`docs/runbooks/gender-prod-activation.md`](docs/runbooks/gender-prod-activation.md).

## Environment variables

`.env.example` is the compose stack's env contract (`cp .env.example .env`).
The optional LLM `*_EXTRA_BODY` extras are shown commented out; the Postgres
password is the `POSTGRES_PASSWORD` knob, injected into the DB connection
out-of-band so it never lands in the DSN (issue #81). The highlights:

| Variable | Required? | Notes |
|---|---|---|
| `LLM_STORY_MODEL` / `LLM_CHAT_MODEL` / `LLM_CORRECTION_MODEL` | yes | LiteLLM model strings (e.g. `anthropic/claude-haiku-4-5-20251001`). |
| `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | one of | Whichever provider your `LLM_*_MODEL` strings target. |
| `TTS_PROVIDER` | no | `elevenlabs` (default) or `inworld`. |
| `ELEVENLABS_API_KEY` / `INWORLD_API_KEY` | conditional | Required when that provider is selected; if missing, `/api/v1/tts` returns 503. |
| `ELEVENLABS_VOICE_ID_{DE,ES,FR,JA,PT,EN}` / `INWORLD_VOICE_ID_…` | optional | Per-language overrides; otherwise the provider's default voice is used. |
| `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` | for pronunciation | Without these, `/api/v1/pronunciation/score`, `/quiz/resolve-mc`, and `/speak/turn` return 503; the UI hides the mic affordance. |
| `INITIAL_OWNER_EMAIL` | first run only | Adopts the legacy user row so the first signup can bypass invites. |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` | optional | Enables Google sign-in. The callback URL must match `BACKEND_BASE_URL/api/v1/auth/google/callback`. |
| `RESEND_API_KEY` / `EMAIL_FROM` | for email | Verification and password-reset links go through Resend. |
| `AUTH_JWT_SECRET` | yes in prod | Used for session cookies and reset/verify tokens. The dev default is fine locally; change for prod. |
| `FRONTEND_BASE_URL` / `BACKEND_BASE_URL` | yes | Used inside emails and the OAuth redirect. |

## Features (what's actually implemented)

- **Stories.** `POST /api/v1/stories` asks the LLM for a level-appropriate
  story in the user's target language, plus comprehension questions and a set
  of target vocab. The response is persisted so re-opens are free; TTS for the
  story sentences and target words is pre-cached in a background task.
- **Sentence-by-sentence audio + per-word tooltips.** In a story, each
  sentence has a listen button (1× / 0.7×) and every word is tappable —
  target vocab opens a full popover with example + "send to review"; other
  words open a compact popover with translation and pronunciation. Translations
  come from a story-side `WordBreakdown` map produced at generation time.
- **Pronunciation practice.** Press the mic on a sentence to record; the
  recorder auto-stops after 1.5 s of silence (RMS-threshold VAD on the
  time-domain signal — see `frontend/src/lib/silenceDetector.ts`). The clip
  is sent to `/api/v1/pronunciation/score`, which transcodes to WAV and calls
  Azure; words are coloured by accuracy band (≥70 good, ≥45 ok, <45 bad).
  When the browser supports AudioWorklet PCM capture, audio instead streams
  live over `WS /api/v1/pronunciation/stream` and words colour as Azure
  returns them; the batch `POST /score` is the fallback.
  Mispronounced words trigger a separate LLM call to `/phonetic-hints` that
  returns hyphenated stress hints (`au-to-BÚS`, `Bä-cke-REI`), and
  `/pronunciation/diagnose` returns an LLM diagnosis of recurring errors.
- **Story Finish flow.** After the last sentence, the UI fetches an
  interleaved 4-item quiz (`mc` → `cloze` → `shadow` → `cloze`; for German a
  cloze slot may swap to a `gender_cloze` when the story has oracle-stamped
  nouns), a
  comprehension insight, a one-line "Klara note", and a per-target-word SRS
  schedule. Quiz items and the insight are persisted on the story after first
  generation; subsequent visits are DB-only. The MC step supports
  voice-picking: speak the option, the backend transcribes and fuzzy-matches
  against the options, returning the picked index or null.
- **SRS.** SM-2-lite engine (see `backend/src/klara/services/srs_engine.py`).
  Users can add target words to their personal deck from the story view;
  `/api/v1/srs/cards/due` returns the queue and `/cards/{id}/review` records a
  rating and reschedules.
- **Learning path + story library.** German-first module sequence:
  `GET /api/v1/modules` returns the ordered path with per-module progress; a
  module completes after 3 finished stories and unlocks the next.
  `POST /api/v1/modules/{id}/story` clones the next unseen pre-generated
  library story — copy-on-claim, no LLM call, audio already cached — while
  `POST /stories` picks its target vocab from the active module and recycles
  fresh stories back into the shared pool (capped at 50 per language pair).
- **Gender (der/die/das) training.** Weak-noun review queue
  (`GET /api/v1/gender/review`), oracle-graded attempts
  (`POST /gender/attempts` — a curated lexicon grades, never the LLM), the
  `gender_cloze` quiz slot, and per-story L1 notes. Inert until the seed
  scripts run — see "Seeding the curriculum".
- **Speak.** Voice conversation with Klara at `/chat`: each turn is audio in →
  `POST /api/v1/speak/turn` → Azure assessment of your unscripted speech plus
  a reply from `LLM_CHAT_MODEL`, spoken back automatically. Corrections render
  as margin notes; `/speak/finish` pushes struggled words into SRS. If the LLM
  call fails, the scored turn survives with `reply=null`.
- **Practice queue.** `/review` pulls today's pronunciation set from
  `GET /api/v1/practice/queue` — sentences you recently fumbled plus SRS-due
  words to say aloud — and reuses the story view's mic/scoring flow.
- **Invite-only signup.** `ALLOWED_SIGNUP_EMAILS` no longer exists. New
  accounts need a token from `POST /api/v1/admin/invitations`. The signup form
  prefills the email and shows expiry by hitting the public
  `GET /api/v1/invitations/{token}`. Google OAuth follows the same rule —
  unknown accounts that aren't the bootstrap owner are rejected.
- **TTS cache and stats.** `/api/v1/tts/stats` returns counts of synthesised
  vs replayed audio, used in the admin view to track provider credit usage.

## Tests

Backend (`backend/tests/`):

```bash
cd backend && uv sync
uv run pytest tests/ -v          # needs a local Postgres; defaults to the compose DB, override with TEST_DATABASE_URL
uv run ruff check src tests
uv run ruff format --check src tests
```

Frontend (`frontend/`):

```bash
npm ci
npm run typecheck                # tsc --noEmit
npm test                         # vitest unit tests (src/lib/*.test.ts)
npm run i18n:check               # locale-key parity vs `es`
npm run build                    # tsc -b + vite build
```

`npm run i18n:check` is enforced in CI; adding a key to `es/common.json`
without mirroring it in the other five locales fails the build.

There is no e2e suite. CI covers pytest + ruff + a migration roundtrip on the
backend, and typecheck + vitest + i18n:check + build on the frontend.

## Deploy

Production runs on EC2 (`eu-north-1`) behind <https://klara.sdar.dev>.

Push to `main` → GitHub Actions builds `ghcr.io/sssamuelll/klara-{backend,frontend}` →
SSH into the server → `docker compose -f docker-compose.yml -f docker-compose.prod.yml pull && up -d` →
external health check.

See [`.github/workflows/README.md`](.github/workflows/README.md) for manual
rollback (`workflow_dispatch` with `image_tag`), branch protection setup, and
the disaster-recovery procedure.

The deploy job rewrites the server's `.env` from GitHub secrets/vars and runs
`git reset --hard origin/main` on the box — never hand-edit either on the
server. Operational runbooks live in `docs/runbooks/`;
[`gender-prod-activation.md`](docs/runbooks/gender-prod-activation.md) must
run before the German gender features do anything in prod.

Local builds use `docker-compose.yml` only and pick up the `build:` blocks.
The prod overlay reverses that with `image:` from GHCR and locks the
listeners to `127.0.0.1` so nginx in front can terminate TLS.

## Notes

- Klara is provider-agnostic for both LLM and TTS — neither is hardcoded.
  Swapping providers is an env-var change.
- The dev `AUTH_JWT_SECRET` in `.env.example` is a placeholder. Generate a
  real secret for any deployment that isn't your laptop.
- Speech locales target Latin American Spanish (`es-MX`) and Brazilian
  Portuguese (`pt-BR`); see the comment in
  `backend/src/klara/i18n/languages.py` for why.
