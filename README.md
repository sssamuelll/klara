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
  `npm run i18n:check`).
- **LLM**: provider-agnostic via LiteLLM. Three model slots — story, chat,
  correction — are configured independently (`LLM_STORY_MODEL`,
  `LLM_CHAT_MODEL`, `LLM_CORRECTION_MODEL`). Anthropic, DeepSeek, and OpenAI
  keys are accepted; the model string picks which provider gets called.
- **TTS**: two providers behind a single `TTSProvider` protocol — ElevenLabs
  and Inworld. Per-language voice overrides (`ELEVENLABS_VOICE_ID_DE`, etc.)
  matter because one voice that nails German rarely sounds native in Spanish.
  Inworld voices are language-locked by design. Synthesised audio is cached in
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
│   │   ├── routers/        # stories, srs, tts, pronunciation, users, invitations, health
│   │   ├── pronunciation/  # Azure client, ffmpeg transcode, response schemas
│   │   ├── tts/            # ElevenLabs + Inworld implementations of TTSProvider
│   │   ├── llm/            # LiteLLM-backed LLMClient + prompts
│   │   ├── services/       # story_gen, finish_lessons, srs_engine, phonetic_hints, voice_mc, tts_*
│   │   ├── auth/           # fastapi-users wiring, invitations, OAuth, email
│   │   ├── models/         # SQLAlchemy models (users, stories, srs, attempts, audio_cache, …)
│   │   └── i18n/           # backend message catalog + language registry
│   ├── alembic/versions/   # migrations (one file per schema change)
│   └── tests/              # pytest suite (see "Tests" below)
├── frontend/
│   └── src/
│       ├── routes/         # Home, NewStory, Story, Settings, Login, Signup, …
│       ├── components/     # SentenceView, StoryFinish, WordPopover, …
│       ├── lib/            # auth, pronunciation, tts, silenceDetector, preferences
│       └── locales/        # de / en / es / fr / ja / pt (source: es)
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

## Environment variables

`.env.example` is the authoritative list. The highlights:

| Variable | Required? | Notes |
|---|---|---|
| `LLM_STORY_MODEL` / `LLM_CHAT_MODEL` / `LLM_CORRECTION_MODEL` | yes | LiteLLM model strings (e.g. `anthropic/claude-haiku-4-5-20251001`). |
| `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | one of | Whichever provider your `LLM_*_MODEL` strings target. |
| `TTS_PROVIDER` | no | `elevenlabs` (default) or `inworld`. |
| `ELEVENLABS_API_KEY` / `INWORLD_API_KEY` | conditional | Required when that provider is selected; if missing, `/api/v1/tts` returns 503. |
| `ELEVENLABS_VOICE_ID_{DE,ES,FR,JA,PT,EN}` / `INWORLD_VOICE_ID_…` | optional | Per-language overrides; otherwise the provider's default voice is used. |
| `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` | for pronunciation | Without these, `/api/v1/pronunciation/score` and `/quiz/resolve-mc` return 503; the UI hides the mic affordance. |
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
  Mispronounced words trigger a separate LLM call to `/phonetic-hints` that
  returns hyphenated stress hints (`au-to-BÚS`, `Bä-cke-REI`).
- **Story Finish flow.** After the last sentence, the UI fetches an
  interleaved 4-item quiz (`mc` → `cloze` → `shadow` → `cloze`), a
  comprehension insight, a one-line "Klara note", and a per-target-word SRS
  schedule. Quiz items and the insight are persisted on the story after first
  generation; subsequent visits are DB-only. The MC step supports
  voice-picking: speak the option, the backend transcribes and fuzzy-matches
  against the options, returning the picked index or null.
- **SRS.** SM-2-lite engine (see `backend/src/klara/services/srs_engine.py`).
  Users can add target words to their personal deck from the story view;
  `/api/v1/srs/cards/due` returns the queue and `/cards/{id}/review` records a
  rating and reschedules.
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
uv run pytest tests/ -v          # requires TEST_DATABASE_URL pointing at a real Postgres
uv run ruff check src tests
uv run ruff format --check src tests
```

Frontend (`frontend/`):

```bash
npm ci
npm run typecheck                # tsc --noEmit
npm run i18n:check               # locale-key parity vs `es`
npm run build                    # tsc -b + vite build
```

`npm run i18n:check` is enforced in CI; adding a key to `es/common.json`
without mirroring it in the other five locales fails the build.

End-to-end smoke scripts (`e2e-*.mjs` at the repo root) drive the running app
via Playwright-style direct fetches and are run manually. They're not wired
into CI.

## Deploy

Production runs on EC2 (`eu-north-1`) behind <https://klara.sdar.dev>.

Push to `main` → GitHub Actions builds `ghcr.io/sssamuelll/klara-{backend,frontend}` →
SSH into the server → `docker compose -f docker-compose.yml -f docker-compose.prod.yml pull && up -d` →
external health check.

See [`.github/workflows/README.md`](.github/workflows/README.md) for manual
rollback (`workflow_dispatch` with `image_tag`), branch protection setup, and
the disaster-recovery procedure.

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
