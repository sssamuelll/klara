# Recomendaciones del consenso (2026-07-13) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar lo recomendado a construir por el consenso del roster: (1) final adaptativo del quiz + instrumentación de tiempo por ítem, (2) tap "¿muy fácil?" como señal primaria de dificultad, (3) sesgo offline del claim de stories hacia vocab SRS-due, (4) gate lingüístico por reglas (artículo+género) en la entrada al pool.

**Architecture:** Todo se para encima de mecanismos existentes: el retry round es un reducer puro cliente-side (patrón `recallSession.ts`), la instrumentación usa el slot `QuizAttempt.detail` JSONB que ya existe (cero migraciones), el sesgo re-rankea `pick_library_entry` por overlap de UUIDs (cero LLM, binding offline), y el gate se inserta en generación/reciclaje/build — **nunca en el claim** (el claim es sin-LLM por contrato). Una sola migración en todo el plan (columna `stories.perceived_difficulty`).

**Tech Stack:** FastAPI + SQLAlchemy async + alembic + pytest (Postgres real) · React + Vite + TS + vitest (solo `src/lib`/`src/api`) · i18n 6 locales (es = source of truth).

## Global Constraints

- **Base:** rama nueva off `origin/main` (`93d5a12`). El working tree del repo está en `fix/onboarding-langs-must-differ-trap` con cambios sin commitear — usar worktree aislado (skill `superpowers:using-git-worktrees`).
- **Migración siguiente:** `revision = "20260713_0015"`, `down_revision = "20260703_0014"`. No se crean tablas nuevas → el TRUNCATE de `backend/tests/conftest.py:76-79` NO se toca.
- **Backend:** routers = `APIRouter` a nivel de módulo (prefix ya montado `/api/v1` en main.py); services = funciones async libres, no clases; `HTTPException detail` = códigos máquina o `t(...)` según el patrón del archivo tocado.
- **Dos canales SRS intocables:** `schedule_next_review` (recall, muta ease/reps) y `schedule_pronunciation_maintenance` (escalera fija). Este plan NO toca `srs_engine.py` ni `srsProjection.ts`.
- **El claim queda sin-LLM:** ninguna tarea añade generación, red o gates al camino `POST /modules/{id}/story`.
- **Tests backend:** `cd backend && uv run pytest tests/<archivo> -v` (Postgres local; override con `TEST_DATABASE_URL`). Lint: `uv run ruff check . && uv run ruff format --check .`
- **Tests frontend:** `cd frontend && npx vitest run <archivo>`; gates de CI: `npm run typecheck`, `npm run i18n:check` (los 6 locales es/en/de/fr/ja/pt deben tener las mismas keys, `es` es la fuente), `npm run build`.
- **`vocab_items` y `quiz_attempts`/`pronunciation_attempts` no se truncan directamente entre tests** (cascada vía stories/users): lemmas de test SIEMPRE con sufijo uuid (`f"Haus{uuid.uuid4().hex[:6]}"`) salvo cuando el test necesita el lemma exacto y siembra su propia fila de lexicón (que SÍ se trunca).
- **Commits:** conventional commits con scope (`feat(quiz): ...`), commit por tarea.
- **Instrumentación tolerante por diseño:** la persistencia de attempts es best-effort (`catch(() => undefined)`) y "Back to quiz" genera duplicados — el análisis posterior debe tolerar pérdida y duplicados; NO "arreglar" esto añadiendo reintentos o dedup.

## File Structure

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `frontend/src/lib/quizSession.ts` | Create | Reducer puro de la sesión de quiz con retry round (máx 4) |
| `frontend/src/lib/quizSession.test.ts` | Create | Tests vitest del reducer |
| `frontend/src/components/StoryFinish.tsx` | Modify | Quiz usa el reducer; timing por ítem; banner retry; sección DifficultyTap en Summary |
| `frontend/src/api/types.ts` | Modify | `QuizAttemptIn.detail`, `StoryDifficultyValue`, `Story.perceived_difficulty` |
| `frontend/src/api/client.ts` | Modify | `setStoryDifficulty` |
| `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` | Modify | keys `story.finish.quiz.retry.*` y `story.finish.summary.difficulty.*` |
| `backend/alembic/versions/20260713_0015_story_perceived_difficulty.py` | Create | Columna `stories.perceived_difficulty` |
| `backend/src/klara/models/story.py` | Modify | Campo `perceived_difficulty` |
| `backend/src/klara/schemas/finish.py` | Modify | `StoryDifficultyIn/Out` |
| `backend/src/klara/schemas/story.py` | Modify | `StoryOut.perceived_difficulty` |
| `backend/src/klara/routers/stories.py` | Modify | Endpoint `POST /stories/{id}/difficulty`; pasar `gender_violations` al recycle; serializar `perceived_difficulty` |
| `backend/tests/test_story_difficulty.py` | Create | Tests del endpoint |
| `backend/src/klara/curriculum/library.py` | Modify | `pick_library_entry` con overlap due; `maybe_recycle_to_library` con gate de lint |
| `backend/tests/test_library_service.py` | Modify | Tests del sesgo + gate en recycle |
| `backend/src/klara/services/story_lint.py` | Create | `gender_article_violations` (reglas deterministas) |
| `backend/tests/test_story_lint.py` | Create | Tests del lint + wiring del draft |
| `backend/src/klara/services/story_gen.py` | Modify | `StoryDraft`/`GeneratedStory` ganan `gender_violations`; draft corre el lint |
| `backend/src/klara/scripts/build_story_library.py` | Modify | Retry cuando `candidate.gender_violations` |

**Contexto del consenso que el implementador debe respetar** (no re-litigar):
- El retry round re-pregunta ítems fallados del MISMO quiz — cero LLM, cero modelo. El score del Summary cuenta SOLO el pase principal.
- El tap es la señal primaria de dificultad; el logging pasivo (`elapsed_ms`) es respaldo. Nada de loops de recalibración en este plan (diferidos).
- El sesgo de vocab se enlaza OFFLINE: se elige QUÉ entry clonar; jamás se regenera al claim.
- El gate lingüístico sub-flagea a propósito: una violación debe ser PROBABLE desde el lexicón curado (falso negativo ok, falso positivo nunca).

---

### Task 1: Reducer puro de la sesión de quiz con retry round

**Files:**
- Create: `frontend/src/lib/quizSession.ts`
- Test: `frontend/src/lib/quizSession.test.ts`

**Interfaces:**
- Consumes: `QuizItem` de `../api/types` (union `mc|cloze|shadow|gender_cloze`, ya existe).
- Produces (Task 2 depende de estos nombres EXACTOS): `initQuizSession(items: QuizItem[]): QuizSessionState`, `quizSessionReducer(s, a)`, `currentItem(s): {item: QuizItem; index: number} | null`, `mainResults(s): QuizPassResult[]`, `MAX_RETRIES = 4`, tipos `QuizSessionState`, `QuizSessionAction`, `QuizPassResult`, `QuizPhase = "main" | "retry" | "done"`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/lib/quizSession.test.ts
import { describe, expect, it } from "vitest";
import type { QuizItem } from "../api/types";
import {
  currentItem,
  initQuizSession,
  mainResults,
  MAX_RETRIES,
  quizSessionReducer,
  type QuizSessionState,
} from "./quizSession";

const mc = (n: number): QuizItem => ({
  type: "mc",
  cap: `q${n}`,
  prompt: "p",
  options: ["a", "b"],
  correct: 0,
});

const items = [mc(0), mc(1), mc(2), mc(3)];

function play(s: QuizSessionState, correct: boolean): QuizSessionState {
  const answered = quizSessionReducer(s, { type: "answer", correct, revealed: false });
  return quizSessionReducer(answered, { type: "next" });
}

describe("quizSession", () => {
  it("all correct → done sin retry", () => {
    let s = initQuizSession(items);
    for (let i = 0; i < 4; i++) s = play(s, true);
    expect(s.phase).toBe("done");
    expect(mainResults(s)).toHaveLength(4);
  });

  it("fallos → retry round con SOLO los fallados, en orden", () => {
    let s = initQuizSession(items);
    s = play(s, true);   // 0 ok
    s = play(s, false);  // 1 fail
    s = play(s, true);   // 2 ok
    s = play(s, false);  // 3 fail
    expect(s.phase).toBe("retry");
    expect(s.order).toEqual([1, 3]);
    expect(currentItem(s)).toEqual({ item: items[1], index: 1 });
  });

  it("retry answers llevan phase retry; fallar en retry NO abre segunda ronda", () => {
    let s = initQuizSession(items);
    s = play(s, false);
    s = play(s, true);
    s = play(s, true);
    s = play(s, true);
    expect(s.phase).toBe("retry");
    s = play(s, false); // vuelve a fallar el ítem 0
    expect(s.phase).toBe("done");
    expect(s.answers.filter((a) => a.phase === "retry")).toHaveLength(1);
    // el score del pase principal no se contamina
    expect(mainResults(s)).toHaveLength(4);
    expect(mainResults(s).filter((r) => r.correct)).toHaveLength(3);
  });

  it("retry queue capada a MAX_RETRIES", () => {
    const six = [mc(0), mc(1), mc(2), mc(3), mc(4), mc(5)];
    let s = initQuizSession(six);
    for (let i = 0; i < 6; i++) s = play(s, false);
    expect(s.phase).toBe("retry");
    expect(s.order).toHaveLength(MAX_RETRIES);
  });

  it("doble answer en la misma posición se ignora", () => {
    let s = initQuizSession(items);
    s = quizSessionReducer(s, { type: "answer", correct: true, revealed: false });
    s = quizSessionReducer(s, { type: "answer", correct: false, revealed: false });
    expect(s.answers).toHaveLength(1);
    expect(s.answers[0].correct).toBe(true);
  });

  it("quiz vacío → done inmediato al next", () => {
    let s = initQuizSession([]);
    expect(currentItem(s)).toBeNull();
    s = quizSessionReducer(s, { type: "next" });
    expect(s.phase).toBe("done");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/quizSession.test.ts`
Expected: FAIL — `Cannot find module './quizSession'`

- [ ] **Step 3: Write the implementation**

```ts
// frontend/src/lib/quizSession.ts
import type { QuizItem } from "../api/types";

/**
 * Pure state machine for the Finish quiz with an adaptive retry round
 * (consenso 2026-07-13): after the main pass, failed items are re-asked
 * once (max MAX_RETRIES), then the session ends. The component drives this
 * via useReducer and owns all side effects (attempt POSTs, timing, TTS) —
 * same pattern as recallSession.ts.
 */
export type QuizPhase = "main" | "retry" | "done";

export interface QuizAnswer {
  index: number; // index into items (stable across passes)
  qType: QuizItem["type"];
  correct: boolean;
  revealed: boolean;
  phase: QuizPhase;
}

export interface QuizPassResult {
  index: number;
  qType: QuizItem["type"];
  correct: boolean;
  revealed: boolean;
}

export interface QuizSessionState {
  items: QuizItem[];
  order: number[]; // indices into items for the CURRENT pass
  pos: number; // position within order
  phase: QuizPhase;
  answers: QuizAnswer[];
}

// ponytail: one retry round, capped — a second round is a punishment loop,
// and the quiz is 4-5 items anyway.
export const MAX_RETRIES = 4;

export function initQuizSession(items: QuizItem[]): QuizSessionState {
  return { items, order: items.map((_, i) => i), pos: 0, phase: "main", answers: [] };
}

export function currentItem(
  s: QuizSessionState,
): { item: QuizItem; index: number } | null {
  if (s.phase === "done") return null;
  const index = s.order[s.pos];
  return index === undefined ? null : { item: s.items[index], index };
}

export type QuizSessionAction =
  | { type: "answer"; correct: boolean; revealed: boolean }
  | { type: "next" };

export function quizSessionReducer(
  s: QuizSessionState,
  a: QuizSessionAction,
): QuizSessionState {
  switch (a.type) {
    case "answer": {
      const cur = currentItem(s);
      if (cur === null) return s;
      // One answer per item per pass (children fire onAnswered exactly once,
      // but a stray double-fire must not corrupt the score).
      if (s.answers.some((x) => x.index === cur.index && x.phase === s.phase)) return s;
      return {
        ...s,
        answers: [
          ...s.answers,
          {
            index: cur.index,
            qType: cur.item.type,
            correct: a.correct,
            revealed: a.revealed,
            phase: s.phase,
          },
        ],
      };
    }
    case "next": {
      if (s.phase === "done") return s;
      const nextPos = s.pos + 1;
      if (nextPos < s.order.length) return { ...s, pos: nextPos };
      if (s.phase === "main") {
        const failed = s.answers
          .filter((x) => x.phase === "main" && !x.correct)
          .map((x) => x.index)
          .slice(0, MAX_RETRIES);
        if (failed.length > 0) return { ...s, order: failed, pos: 0, phase: "retry" };
      }
      return { ...s, phase: "done" };
    }
    default:
      return s;
  }
}

/** Results in the shape Summary consumes — main pass ONLY, so the retry
 * round never inflates the score. */
export function mainResults(s: QuizSessionState): QuizPassResult[] {
  return s.answers
    .filter((x) => x.phase === "main")
    .map(({ index, qType, correct, revealed }) => ({ index, qType, correct, revealed }));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/quizSession.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/quizSession.ts frontend/src/lib/quizSession.test.ts
git commit -m "feat(quiz): pure session reducer with adaptive retry round (max 4)"
```

---

### Task 2: Cablear retry round + instrumentación de tiempo en StoryFinish

**Files:**
- Modify: `frontend/src/components/StoryFinish.tsx:177-251` (componente `Quiz`) y `:253-276` (`QuizHero`)
- Modify: `frontend/src/api/types.ts:278-285` (`QuizAttemptIn`)
- Modify: `frontend/src/locales/es/common.json` (+ en, de, fr, ja, pt) — bloque `story.finish.quiz`

**Interfaces:**
- Consumes: todo lo exportado por Task 1 (`initQuizSession`, `quizSessionReducer`, `currentItem`, `mainResults`, `QuizSessionState`).
- Produces: attempts con `detail: { elapsed_ms: number; phase: "main" | "retry" }` fluyendo a `POST /stories/{id}/quiz/attempts` (el backend ya persiste `detail` JSONB — `models/attempts.py:76`, cero cambios backend).
- Contrato intocable con los hijos (`MCQuestion`, `ClozeQuestion`, `ShadowQuestion`, `GenderClozeQuestion`): reciben `onAnswered({correct, revealed})`, `onNext`, `isLast` — NO se modifican.

- [ ] **Step 1: Types — añadir `detail` a `QuizAttemptIn`**

En `frontend/src/api/types.ts`, dentro de `QuizAttemptIn` (línea ~278), añadir tras `was_revealed`:

```ts
export interface QuizAttemptIn {
  question_index: number;
  // No "gender_cloze": gender is graded server-side via recordGenderAttempt, not
  // through this client-trusted generic attempt. The Quiz dispatcher guards the
  // recordQuizAttempt call with `q.type !== "gender_cloze"`, which narrows q.type
  // to these three at the call site.
  question_type: "mc" | "cloze" | "shadow";
  was_correct: boolean;
  was_revealed: boolean;
  // Instrumentación (consenso 2026-07-13): elapsed desde que el ítem aparece
  // hasta que se responde, y en qué pase ocurrió. Va al slot JSONB
  // quiz_attempts.detail que ya existía sin uso.
  detail?: { elapsed_ms: number; phase: "main" | "retry" } | null;
}
```

- [ ] **Step 2: Reescribir el componente `Quiz` sobre el reducer**

Reemplazar el componente `Quiz` completo (`StoryFinish.tsx:177-251`) por:

```tsx
function Quiz({ items, story, onComplete }: QuizProps): JSX.Element {
  const [state, dispatch] = useReducer(quizSessionReducer, items, initQuizSession);

  // Timing per item (patrón #115 / RecallReviewSession): shownAt resets each
  // time a new item lands on screen.
  const shownAtRef = useRef(performance.now());
  useEffect(() => {
    shownAtRef.current = performance.now();
  }, [state.phase, state.pos]);

  // Deliberately not depending on onComplete (parent passes an inline
  // callback) — only the phase flipping to "done" should fire this.
  useEffect(() => {
    if (state.phase === "done") onComplete(mainResults(state));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase]);

  const cur = currentItem(state);
  if (cur === null) return <></>;
  const { item: q, index } = cur;

  // "toSummary" only when no retry round can follow: in retry, or in main
  // with a clean sheet so far (children render the label AFTER answering,
  // when the current answer is already in state.answers).
  const failedSoFar = state.answers.some((a) => a.phase === "main" && !a.correct);
  const isLast =
    state.pos === state.order.length - 1 && (state.phase === "retry" || !failedSoFar);

  const onAnswered = (r: Omit<QuizResult, "index" | "qType">) => {
    const elapsedMs = Math.max(0, Math.round(performance.now() - shownAtRef.current));
    dispatch({ type: "answer", correct: r.correct, revealed: r.revealed });
    // Best-effort persistence — failures don't block the UX. Gender items
    // record their own diadic evidence (recordGenderAttempt), so skip the
    // generic quiz-attempt record for them.
    if (q.type !== "gender_cloze") {
      void api
        .recordQuizAttempt(story.id, {
          question_index: index,
          question_type: q.type,
          was_correct: r.correct,
          was_revealed: r.revealed,
          detail: { elapsed_ms: elapsedMs, phase: state.phase === "retry" ? "retry" : "main" },
        })
        .catch(() => undefined);
    }
  };

  const onNext = () => dispatch({ type: "next" });

  return (
    <>
      <QuizHero
        idx={state.pos}
        total={state.order.length}
        retry={state.phase === "retry"}
      />
      <div
        className="qstage"
        key={`${state.phase}-${state.pos}` /* remount each q for clean state */}
      >
        {q.type === "mc" && (
          <MCQuestion q={q} story={story} onAnswered={onAnswered} onNext={onNext} isLast={isLast} />
        )}
        {q.type === "cloze" && (
          <ClozeQuestion q={q} story={story} onAnswered={onAnswered} onNext={onNext} isLast={isLast} />
        )}
        {q.type === "shadow" && (
          <ShadowQuestion q={q} story={story} onAnswered={onAnswered} onNext={onNext} isLast={isLast} />
        )}
        {q.type === "gender_cloze" && (
          <GenderClozeQuestion q={q} story={story} onAnswered={onAnswered} onNext={onNext} isLast={isLast} />
        )}
      </div>
    </>
  );
}
```

Y `QuizHero` (líneas 253-276) gana el prop `retry` — solo cambian la firma y las dos primeras líneas del header:

```tsx
function QuizHero({ idx, total, retry }: { idx: number; total: number; retry: boolean }): JSX.Element {
  const { t } = useTranslation();
  return (
    <header className="quiz-hero">
      <h1 className="quiz-hero__title">
        {retry ? t("story.finish.quiz.retry.cap") : t("story.finish.quiz.title")}
      </h1>
      <p className="quiz-hero__sub">
        {retry ? t("story.finish.quiz.retry.sub") : t("story.finish.quiz.sub")}
      </p>
      {/* ...el resto del header queda idéntico (prog/track/pips)... */}
```

(El viejo `Quiz` no usaba `useTranslation` y el nuevo tampoco — el hero es quien traduce.)

Imports nuevos al tope de `StoryFinish.tsx`: `useReducer` en el import de react, y:

```tsx
import {
  currentItem,
  initQuizSession,
  mainResults,
  quizSessionReducer,
} from "../lib/quizSession";
```

Nota: el estado local `results`/`idx` del viejo `Quiz` desaparece; `QuizResult` (interfaz local, `StoryFinish.tsx:62-67`) se queda — `mainResults` es estructuralmente compatible.

- [ ] **Step 3: i18n — añadir `story.finish.quiz.retry` a los 6 locales**

En cada `frontend/src/locales/<lng>/common.json`, dentro de `story.finish.quiz` (hermano de `title`/`sub`):

```jsonc
// es (source of truth):
"retry": { "cap": "Repaso rápido", "sub": "Las que se te escaparon, una vez más." }
// en:
"retry": { "cap": "Quick review", "sub": "The ones that got away — one more try." }
// de:
"retry": { "cap": "Kurzes Nachspiel", "sub": "Die, die dir entwischt sind — noch einmal." }
// fr:
"retry": { "cap": "Révision rapide", "sub": "Celles qui t'ont échappé — encore une fois." }
// ja:
"retry": { "cap": "クイックレビュー", "sub": "逃した問題をもう一度。" }
// pt:
"retry": { "cap": "Revisão rápida", "sub": "As que escaparam — mais uma vez." }
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npx vitest run`
Expected: typecheck limpio, i18n sin drift, tests PASS.

Verificación manual (si hay entorno): terminar un quiz fallando ≥1 ítem → aparece el pase "Repaso rápido" con solo los fallados; el Summary muestra el score del pase principal; en la pestaña Network cada attempt lleva `detail: {elapsed_ms, phase}`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StoryFinish.tsx frontend/src/api/types.ts frontend/src/locales
git commit -m "feat(quiz): adaptive retry round + per-item timing in attempt detail"
```

---

### Task 3: Tap de dificultad percibida en el Summary

**Files:**
- Create: `backend/alembic/versions/20260713_0015_story_perceived_difficulty.py`
- Modify: `backend/src/klara/models/story.py` (campo), `backend/src/klara/schemas/finish.py` (In/Out), `backend/src/klara/schemas/story.py` (`StoryOut`), `backend/src/klara/routers/stories.py` (endpoint + serializer)
- Test: `backend/tests/test_story_difficulty.py`
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/components/StoryFinish.tsx` (Summary), locales ×6

**Interfaces:**
- Produces: `POST /api/v1/stories/{story_id}/difficulty` body `{"value": "too_easy" | "right" | "too_hard"}` → 200 `{"value": ...}`; columna `stories.perceived_difficulty` (String(16), nullable); `StoryOut.perceived_difficulty`; client `api.setStoryDifficulty(storyId, value)`.
- El valor es last-write-wins (re-tap sobrescribe). Señal PRIMARIA de dificultad por consenso; ningún consumidor automático en este plan (el loop de recalibración está diferido).

- [ ] **Step 1: Migración**

```python
# backend/alembic/versions/20260713_0015_story_perceived_difficulty.py
"""stories.perceived_difficulty — señal de dificultad por tap (consenso 2026-07-13)

Revision ID: 20260713_0015
Revises: 20260703_0014
Create Date: 2026-07-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0015"
down_revision: str | None = "20260703_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Free-text-shaped but Literal-validated at the API layer; a pg enum for a
    # 3-value user tap is churn without payoff. ponytail: promote to enum if a
    # second writer ever appears.
    op.add_column(
        "stories", sa.Column("perceived_difficulty", sa.String(16), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("stories", "perceived_difficulty")
```

- [ ] **Step 2: Modelo — en `models/story.py`, tras `klara_note`**

```python
    # One-tap difficulty signal from the Finish summary (consenso 2026-07-13:
    # the user SAYS how the story felt — señal primaria; passive telemetry is
    # the backup). Last tap wins. Values: too_easy | right | too_hard.
    perceived_difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True)
```

- [ ] **Step 3: Schemas — en `schemas/finish.py`, tras `StoryFinishOut`**

```python
StoryDifficulty = Literal["too_easy", "right", "too_hard"]


class StoryDifficultyIn(BaseModel):
    value: StoryDifficulty


class StoryDifficultyOut(BaseModel):
    value: StoryDifficulty
```

Y en `schemas/story.py`, dentro de `StoryOut`, añadir el campo opcional (junto a los demás opcionales):

```python
    perceived_difficulty: str | None = None
```

- [ ] **Step 4: Write the failing test**

```python
# backend/tests/test_story_difficulty.py
"""POST /stories/{id}/difficulty: persiste el tap, last-write-wins, owner-gated, 422 en basura."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from klara.auth.users import current_active_user
from klara.dependencies import db_session as db_session_dep
from klara.main import create_app
from klara.models import Story, User
from klara.models.enums import CEFRLevel


async def _user(db):
    u = User(
        id=uuid.uuid4(),
        email=f"diff-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="D",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def _story(db, *, user):
    s = Story(
        id=uuid.uuid4(),
        user_id=user.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="t",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[],
    )
    db.add(s)
    await db.flush()
    return s


async def _post(db, user, story_id, body):
    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post(f"/api/v1/stories/{story_id}/difficulty", json=body)


@pytest.mark.asyncio
async def test_sets_persists_and_overwrites(db_session):
    u = await _user(db_session)
    s = await _story(db_session, user=u)
    await db_session.commit()

    resp = await _post(db_session, u, s.id, {"value": "too_hard"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"value": "too_hard"}
    await db_session.refresh(s)
    assert s.perceived_difficulty == "too_hard"

    # last-write-wins
    resp = await _post(db_session, u, s.id, {"value": "right"})
    assert resp.status_code == 200, resp.text
    await db_session.refresh(s)
    assert s.perceived_difficulty == "right"


@pytest.mark.asyncio
async def test_owner_gated_404(db_session):
    owner = await _user(db_session)
    other = await _user(db_session)
    s = await _story(db_session, user=owner)
    await db_session.commit()
    resp = await _post(db_session, other, s.id, {"value": "right"})
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_invalid_value_422(db_session):
    u = await _user(db_session)
    s = await _story(db_session, user=u)
    await db_session.commit()
    resp = await _post(db_session, u, s.id, {"value": "imposible"})
    assert resp.status_code == 422, resp.text
```

Run: `cd backend && uv run pytest tests/test_story_difficulty.py -v`
Expected: FAIL — 404/AttributeError (endpoint y columna no existen). Nota: la migración del Step 1 debe existir ANTES de correr (conftest hace `alembic upgrade head`).

- [ ] **Step 5: Endpoint — en `routers/stories.py`, tras `finish_story` (línea ~681)**

Añadir a los imports de `klara.schemas.finish`: `StoryDifficultyIn, StoryDifficultyOut`.

```python
@router.post("/{story_id}/difficulty", response_model=StoryDifficultyOut)
async def set_story_difficulty(
    story_id: UUID,
    payload: StoryDifficultyIn,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
) -> StoryDifficultyOut:
    """One-tap difficulty signal from the Finish summary (consenso 2026-07-13:
    the user says how the story felt instead of Klara inferring it from noisy
    n=1 telemetry). Last tap wins; future story selection/generation may read
    it — nothing consumes it automatically yet."""
    story = await _load_or_404(db, story_id, user.id, locale)
    story.perceived_difficulty = payload.value
    await db.commit()
    return StoryDifficultyOut(value=payload.value)
```

Y en `_serialize_story` (línea ~114), añadir al constructor de `StoryOut`:

```python
        perceived_difficulty=story.perceived_difficulty,
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_story_difficulty.py -v && uv run ruff check .`
Expected: PASS (3 tests), ruff limpio.

- [ ] **Step 7: Frontend — types, client, UI, i18n**

`frontend/src/api/types.ts` — añadir junto a los tipos de finish:

```ts
export type StoryDifficultyValue = "too_easy" | "right" | "too_hard";
```

y al interface `Story` (donde estén sus campos opcionales):

```ts
  perceived_difficulty?: StoryDifficultyValue | null;
```

`frontend/src/api/client.ts` — tras `recordGenderAttempt` (línea ~338):

```ts
  setStoryDifficulty: (storyId: string, value: StoryDifficultyValue) =>
    request<{ value: StoryDifficultyValue }>(`/stories/${storyId}/difficulty`, {
      method: "POST",
      body: JSON.stringify({ value }),
    }),
```

(import de `StoryDifficultyValue` en el bloque de types del client.)

`StoryFinish.tsx` — nuevo componente antes de `Summary`, y renderizarlo en `Summary` justo después de `</header>` del `fin-hero` (línea ~1144), antes del bloque `souvenir`:

```tsx
function DifficultyTap({ story }: { story: Story }): JSX.Element {
  const { t } = useTranslation();
  const [value, setValue] = useState<StoryDifficultyValue | null>(
    story.perceived_difficulty ?? null,
  );
  const pick = (v: StoryDifficultyValue) => {
    setValue(v);
    // Best-effort like every other Finish signal.
    void api.setStoryDifficulty(story.id, v).catch(() => undefined);
  };
  const opts: StoryDifficultyValue[] = ["too_easy", "right", "too_hard"];
  const labels: Record<StoryDifficultyValue, string> = {
    too_easy: t("story.finish.summary.difficulty.tooEasy"),
    right: t("story.finish.summary.difficulty.right"),
    too_hard: t("story.finish.summary.difficulty.tooHard"),
  };
  return (
    <section
      className="fin-difficulty"
      aria-label={t("story.finish.summary.difficulty.title")}
    >
      <span className="fin-cap">{t("story.finish.summary.difficulty.title")}</span>
      <div className="qcard__actions" style={{ marginTop: 8 }}>
        {opts.map((v) => (
          <button
            key={v}
            type="button"
            className={value === v ? "fin-btn fin-btn--primary" : "fin-btn fin-btn--ghost"}
            aria-pressed={value === v}
            onClick={() => pick(v)}
          >
            {labels[v]}
          </button>
        ))}
      </div>
    </section>
  );
}
```

En `Summary`, tras el `</header>`:

```tsx
      <DifficultyTap story={story} />
```

(import de `StoryDifficultyValue` en el bloque de types de `StoryFinish.tsx`.)

i18n ×6 — dentro de `story.finish.summary`:

```jsonc
// es: "difficulty": { "title": "¿Cómo se sintió esta historia?", "tooEasy": "Muy fácil", "right": "En su punto", "tooHard": "Muy difícil" }
// en: "difficulty": { "title": "How did this story feel?", "tooEasy": "Too easy", "right": "Just right", "tooHard": "Too hard" }
// de: "difficulty": { "title": "Wie war diese Geschichte für dich?", "tooEasy": "Zu leicht", "right": "Genau richtig", "tooHard": "Zu schwer" }
// fr: "difficulty": { "title": "Cette histoire, tu l'as trouvée comment ?", "tooEasy": "Trop facile", "right": "Juste bien", "tooHard": "Trop difficile" }
// ja: "difficulty": { "title": "この物語の難しさは？", "tooEasy": "簡単すぎた", "right": "ちょうどいい", "tooHard": "難しすぎた" }
// pt: "difficulty": { "title": "Como foi esta história?", "tooEasy": "Fácil demais", "right": "No ponto", "tooHard": "Difícil demais" }
```

- [ ] **Step 8: Verify frontend**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run build`
Expected: los tres limpios.

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/20260713_0015_story_perceived_difficulty.py \
  backend/src/klara/models/story.py backend/src/klara/schemas/finish.py \
  backend/src/klara/schemas/story.py backend/src/klara/routers/stories.py \
  backend/tests/test_story_difficulty.py \
  frontend/src/api/types.ts frontend/src/api/client.ts \
  frontend/src/components/StoryFinish.tsx frontend/src/locales
git commit -m "feat(finish): perceived-difficulty tap on the summary (señal primaria)"
```

---

### Task 4: Sesgo del claim hacia vocab SRS-due (`pick_library_entry`)

**Files:**
- Modify: `backend/src/klara/curriculum/library.py:39-54`
- Test: `backend/tests/test_library_service.py` (añadir 2 tests)

**Interfaces:**
- Consumes: `UserCard` (predicado due idéntico a `routers/srs.py:82-100`: `next_review_at IS NULL OR <= now(UTC)`).
- Produces: misma firma `pick_library_entry(db, *, user_id, module_id, native_language) -> StoryLibrary | None` — el call site (`routers/modules.py`) NO cambia. Orden nuevo: overlap due desc → times_served asc → created_at asc. Sin cards due, overlap=0 en todas → se reduce al orden viejo (el test existente `test_pick_prefers_least_served_and_skips_claimed` DEBE seguir verde tal cual).

- [ ] **Step 1: Write the failing tests — añadir a `test_library_service.py`**

Imports adicionales al tope del archivo: `from datetime import timedelta` (UTC y datetime ya están importados).

```python
@pytest.mark.asyncio
async def test_pick_prefers_due_vocab_overlap(db_session):
    """Sesgo offline (consenso 2026-07-13): la entry con más overlap con las
    cards due del usuario gana AUNQUE esté más servida — avanzar ya repasa."""
    user = await _user(db_session)
    module = await _module(db_session)
    v_due = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"due-{uuid.uuid4().hex[:6]}", pos=PartOfSpeech.NOUN
    )
    v_other = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"oth-{uuid.uuid4().hex[:6]}", pos=PartOfSpeech.NOUN
    )
    db_session.add_all([v_due, v_other])
    await db_session.flush()
    db_session.add(
        UserCard(
            user_id=user.id,
            vocab_item_id=v_due.id,
            next_review_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    fresh = _entry(module, served=0, hash_suffix="d")
    fresh.target_vocab_item_ids = [v_other.id]
    overlapping = _entry(module, served=5, hash_suffix="e")
    overlapping.target_vocab_item_ids = [v_due.id]
    db_session.add_all([fresh, overlapping])
    await db_session.commit()

    picked = await pick_library_entry(
        db_session, user_id=user.id, module_id=module.id, native_language="es"
    )
    assert picked is not None and picked.id == overlapping.id


@pytest.mark.asyncio
async def test_pick_falls_back_to_least_served_when_nothing_due(db_session):
    """Card programada al futuro → overlap 0 en todas → orden viejo."""
    user = await _user(db_session)
    module = await _module(db_session)
    v = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"fut-{uuid.uuid4().hex[:6]}", pos=PartOfSpeech.NOUN
    )
    db_session.add(v)
    await db_session.flush()
    db_session.add(
        UserCard(
            user_id=user.id,
            vocab_item_id=v.id,
            next_review_at=datetime.now(UTC) + timedelta(days=30),
        )
    )
    fresh = _entry(module, served=0, hash_suffix="f")
    worn = _entry(module, served=5, hash_suffix="9")
    worn.target_vocab_item_ids = [v.id]  # overlap solo si la card estuviera due
    db_session.add_all([fresh, worn])
    await db_session.commit()

    picked = await pick_library_entry(
        db_session, user_id=user.id, module_id=module.id, native_language="es"
    )
    assert picked is not None and picked.id == fresh.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_library_service.py::test_pick_prefers_due_vocab_overlap -v`
Expected: FAIL — hoy pick devuelve `fresh` (menos servida) e ignora el overlap.

- [ ] **Step 3: Implementación — reemplazar `pick_library_entry` en `library.py:39-54`**

Imports adicionales al tope de `library.py`: `from datetime import UTC, datetime` y `or_` en el import de sqlalchemy (`from sqlalchemy import func, or_, select`), y `UserCard` en el import de models.

```python
async def pick_library_entry(
    db: AsyncSession, *, user_id: UUID, module_id: UUID, native_language: str
) -> StoryLibrary | None:
    """Entry with the most overlap with the user's due SRS vocab wins
    (consenso 2026-07-13: avanzar ya repasa — the bias picks WHICH shared
    entry to clone; claim-time stays LLM-free); ties → least served, then
    oldest. Nothing due → every overlap is 0 → the old least-served order.
    ponytail: Python-side scoring — the pool is capped at 50 rows per pair."""
    entries = (
        (
            await db.execute(
                select(StoryLibrary).where(
                    StoryLibrary.module_id == module_id,
                    StoryLibrary.native_language == native_language,
                    StoryLibrary.is_active.is_(True),
                    StoryLibrary.id.not_in(_claimed_by_user(user_id)),
                )
            )
        )
        .scalars()
        .all()
    )
    if not entries:
        return None
    # Same "due" predicate as GET /srs/cards/due (routers/srs.py): NULL means
    # enrolled-but-never-reviewed, which also deserves surfacing.
    due_ids = set(
        (
            await db.execute(
                select(UserCard.vocab_item_id).where(
                    UserCard.user_id == user_id,
                    or_(
                        UserCard.next_review_at.is_(None),
                        UserCard.next_review_at <= datetime.now(UTC),
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    return min(
        entries,
        key=lambda e: (
            -len(due_ids & set(e.target_vocab_item_ids or [])),
            e.times_served,
            e.created_at,
        ),
    )
```

- [ ] **Step 4: Run the full library suite**

Run: `cd backend && uv run pytest tests/test_library_service.py tests/test_claim_story.py -v && uv run ruff check .`
Expected: PASS — incluidos los tests viejos de pick (fallback intacto).

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/curriculum/library.py backend/tests/test_library_service.py
git commit -m "feat(library): bias claim pick toward due SRS vocab overlap"
```

---

### Task 5: Gate lingüístico por reglas — `story_lint.py`

**Files:**
- Create: `backend/src/klara/services/story_lint.py`
- Test: `backend/tests/test_story_lint.py`

**Interfaces:**
- Consumes: `GenderLexicon` (oracle), `word_tokens_by_index` de `klara.services.tokens` (dict índice→token de palabra, ordenado, sin puntuación — mismo tokenizador que `verify_coverage`).
- Produces (Task 6 depende de estos nombres): `async def gender_article_violations(db, content: dict, *, language: str) -> list[str]` — strings estilo `"die Haus (oracle: das)"`, `[]` para no-alemán.
- **Decisión de diseño (del consenso, no negociable):** sub-flagear a propósito. Una violación debe ser PROBABLE: el artículo usado no aparece en NINGUNA casilla de la tabla de declinación del género oracle. `"der Frau"` (dativo femenino) NO es violación. El fallback de compuestos de `resolve_gender` NO se usa: en formas flexionadas da falsos positivos (`"Kinder"` sufijo-matchea `"Inder"` → der).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_story_lint.py
"""services.story_lint: flags ONLY provable gender-article errors (sub-flag by design)."""

import pytest

from klara.curriculum.gender_lex import GenderRow, load_gender_lexicon
from klara.services.story_lint import gender_article_violations


def _content(*targets: str) -> dict:
    return {
        "sentences": [{"target": t, "native": ""} for t in targets],
        "comprehension_questions": [],
    }


@pytest.fixture
async def lexicon(db_session):
    await load_gender_lexicon(
        db_session,
        rows=[
            GenderRow(lemma="Haus", pos="noun", gender="das"),
            GenderRow(lemma="Frau", pos="noun", gender="die"),
            GenderRow(lemma="Mann", pos="noun", gender="der"),
            # Trampa real del fallback de compuestos: "Kinder" termina en "Inder".
            GenderRow(lemma="Inder", pos="noun", gender="der"),
        ],
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_flags_impossible_article(db_session, lexicon):
    out = await gender_article_violations(
        db_session, _content("Ich sehe die Haus."), language="de"
    )
    assert out == ["die Haus (oracle: das)"]


@pytest.mark.asyncio
async def test_declined_forms_not_flagged(db_session, lexicon):
    # "der Frau" = dativo femenino (grammatical); "dem Mann" = dativo masculino.
    out = await gender_article_violations(
        db_session,
        _content("Ich gebe der Frau einen Apfel.", "Ich helfe dem Mann.", "Das Haus ist alt."),
        language="de",
    )
    assert out == []


@pytest.mark.asyncio
async def test_inflected_plural_not_flagged(db_session, lexicon):
    # "die Kinder" NO debe resolverse vía sufijo "Inder" (der) — exact/ci only.
    out = await gender_article_violations(
        db_session, _content("Die Kinder spielen."), language="de"
    )
    assert out == []


@pytest.mark.asyncio
async def test_unknown_noun_skipped_and_non_de_empty(db_session, lexicon):
    assert (
        await gender_article_violations(
            db_session, _content("Die Zettelwirtschaft wächst."), language="de"
        )
        == []
    )
    assert (
        await gender_article_violations(db_session, _content("die Haus"), language="es")
        == []
    )


@pytest.mark.asyncio
async def test_multiple_violations_reported_in_order(db_session, lexicon):
    out = await gender_article_violations(
        db_session, _content("Das Frau kocht.", "Der Haus brennt."), language="de"
    )
    assert out == ["Das Frau (oracle: die)", "Der Haus (oracle: das)"]
```

Run: `cd backend && uv run pytest tests/test_story_lint.py -v`
Expected: FAIL — módulo no existe.

- [ ] **Step 2: Implementación**

```python
# backend/src/klara/services/story_lint.py
"""Rule-based German lint gate for generated story content.

The single-user failure mode Duolingo's population catches and Klara can't
(consenso 2026-07-13): agrammatical German reaching the only user, with no
crowd to flag it. Deterministic rules over the curated oracle only — no LLM
judging LLM. Under-flagging is the designed failure mode: a violation must be
PROVABLE from the lexicon; a miss is fine, a false positive is not."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import GenderLexicon
from klara.services.tokens import word_tokens_by_index

# Definite-article surface forms that are grammatical SOMEWHERE in the
# declension table (nom/acc/dat/gen) of each oracle gender. An article is
# evidence of error only when it fits NO case of the oracle gender:
# "die Haus" can never be right; "der Frau" is dative feminine and fine.
_VALID_ARTICLES: dict[str, set[str]] = {
    "der": {"der", "den", "dem", "des"},
    "die": {"die", "der"},
    "das": {"das", "dem", "des"},
}
_DEFINITE_ARTICLES = {"der", "die", "das"}


async def _oracle_gender_exact(db: AsyncSession, noun: str) -> str | None:
    """Exact/case-insensitive lexicon hit ONLY. resolve_gender's compound
    fallback is deliberately not used here: on inflected forms it
    false-positives ("Kinder" suffix-matches "Inder" → der), and a gate must
    never flag grammatical text."""
    row = await db.get(GenderLexicon, noun)
    if row is not None:
        return row.gender
    return (
        await db.execute(
            select(GenderLexicon.gender)
            .where(func.lower(GenderLexicon.lemma) == noun.lower())
            .limit(1)
        )
    ).scalar_one_or_none()


async def gender_article_violations(
    db: AsyncSession, content: dict, *, language: str
) -> list[str]:
    """Article+noun bigrams whose article fits NO case of the noun's oracle
    gender. Returns human-readable violations ("die Haus (oracle: das)"),
    in reading order. Empty for non-German content."""
    if language != "de":
        return []
    violations: list[str] = []
    for sentence in content.get("sentences", []) or []:
        if not isinstance(sentence, dict):
            continue  # el JSON del LLM puede traer entradas malformadas
        tokens = list(word_tokens_by_index(sentence.get("target") or "").values())
        for art, noun in zip(tokens, tokens[1:]):
            a = art.lower()
            if a not in _DEFINITE_ARTICLES or not noun[:1].isupper():
                continue
            oracle = await _oracle_gender_exact(db, noun)
            if oracle is not None and a not in _VALID_ARTICLES[oracle]:
                violations.append(f"{art} {noun} (oracle: {oracle})")
    return violations
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_story_lint.py -v && uv run ruff check .`
Expected: PASS (5 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/src/klara/services/story_lint.py backend/tests/test_story_lint.py
git commit -m "feat(lint): rule-based gender-article gate for German stories"
```

---

### Task 6: Cablear el gate en draft → recycle → build

**Files:**
- Modify: `backend/src/klara/services/story_gen.py` (`StoryDraft`, `GeneratedStory`, `generate_story_draft`, `generate_story`)
- Modify: `backend/src/klara/curriculum/library.py` (`maybe_recycle_to_library`)
- Modify: `backend/src/klara/routers/stories.py:207-213` (call site del recycle)
- Modify: `backend/src/klara/scripts/build_story_library.py` (retry loop, línea ~184)
- Test: `backend/tests/test_story_lint.py` (wiring del draft con LLM fake) y `backend/tests/test_library_service.py` (gate en recycle)

**Interfaces:**
- Consumes: `gender_article_violations` (Task 5).
- Produces: `StoryDraft.gender_violations: list[str]`, `GeneratedStory.gender_violations: list[str]`, `maybe_recycle_to_library(..., gender_violations: list[str] | None = None)`.
- **Dónde vive el gate (del consenso, no negociable):** generación (medir), reciclaje (bloquear entrada al pool), build (retry). El on-demand `create_story` SIRVE la story igual aunque tenga violaciones (misma filosofía que `dropped_lemmas`: no bloquea servir, bloquea compartir); el claim no se toca.

- [ ] **Step 1: Write the failing tests**

Añadir a `backend/tests/test_story_lint.py`:

```python
import json

from klara.llm.base import LLMResponse
from klara.models.enums import CEFRLevel
from klara.services.story_gen import generate_story_draft


class _FakeLLM:
    """Devuelve un payload fijo; cumple el Protocol de complete()."""

    def __init__(self, payload: dict):
        self._payload = payload

    async def complete(self, **kwargs):
        return LLMResponse(content=json.dumps(self._payload), model="fake", provider="fake")

    async def stream(self, **kwargs):  # pragma: no cover — protocol completeness
        raise NotImplementedError


@pytest.mark.asyncio
async def test_draft_carries_gender_violations(db_session, lexicon):
    payload = {
        "title": "Die Haus",
        "sentences": [
            {"target": "Ich sehe die Haus.", "native": "Veo la casa.", "new_words": []}
        ],
        "comprehension_questions": [],
        "target_words": [
            {"lemma": "Haus", "pos": "noun", "gender": "das", "translation": "casa"}
        ],
    }
    draft = await generate_story_draft(
        db_session,
        _FakeLLM(payload),
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        learning_context=None,
        topic=None,
        model=None,
        target_lemmas=["Haus"],
        module_objective=None,
        avoid_lemmas=[],
    )
    assert draft.dropped_lemmas == []  # coverage OK: "Haus" aparece en el texto
    assert draft.gender_violations == ["die Haus (oracle: das)"]
```

Y en `test_library_service.py`, dentro de `test_pool_recycle_rules` (antes de la aserción "clean → accepted", línea ~276):

```python
    # gender violations → rejected: the lint gate guards POOL ENTRY (what gets
    # shared); serving the on-demand story itself is not blocked here.
    assert (
        await maybe_recycle_to_library(
            db_session,
            story=story,
            dropped_lemmas=[],
            topic=None,
            topic_origin="none",
            gender_violations=["die Haus (oracle: das)"],
        )
        is False
    )
```

Run: `cd backend && uv run pytest tests/test_story_lint.py::test_draft_carries_gender_violations tests/test_library_service.py::test_pool_recycle_rules -v`
Expected: FAIL — `StoryDraft` no tiene el campo; `maybe_recycle_to_library` no acepta el kwarg.

- [ ] **Step 2: `story_gen.py` — campo + lint en el draft**

Import al tope: `from klara.services.story_lint import gender_article_violations`.

En `GeneratedStory` (línea ~28) y `StoryDraft` (línea ~35), añadir el campo al final de cada dataclass:

```python
    gender_violations: list[str]
```

En `generate_story_draft`, tras el bloque de `story.curriculum.missed` (línea ~321) y antes del `return StoryDraft(...)`:

```python
    gender_violations = await gender_article_violations(
        db, content, language=target_language
    )
    if gender_violations:
        # Señal de calidad. NO bloquea servir la story on-demand; bloquea
        # compartirla (recycle/build la leen).
        log.info(
            "story.lint.gender_violations",
            violations=gender_violations,
            target_language=target_language,
        )
```

y en el constructor `StoryDraft(...)` añadir `gender_violations=gender_violations,`.

En `generate_story`, el `return` final (línea ~400) pasa el campo:

```python
    return GeneratedStory(
        story=story,
        target_words=draft.target_words,
        dropped_lemmas=draft.dropped_lemmas,
        gender_violations=draft.gender_violations,
    )
```

- [ ] **Step 3: `library.py` — gate en el recycle**

Firma de `maybe_recycle_to_library` (línea ~153): añadir kwarg tras `topic_origin`:

```python
    topic_origin: str,
    gender_violations: list[str] | None = None,
```

y la primera condición del cuerpo pasa de

```python
    if story.module_id is None or dropped_lemmas:
        return False
```

a

```python
    if story.module_id is None or dropped_lemmas or gender_violations:
        return False
```

(docstring: añadir `lint-clean only (no provable gender-article errors)` a la lista de reglas.)

- [ ] **Step 4: `routers/stories.py` — call site (línea ~207)**

```python
        await maybe_recycle_to_library(
            db,
            story=result.story,
            dropped_lemmas=result.dropped_lemmas,
            topic=payload.topic,
            topic_origin=payload.topic_origin,
            gender_violations=result.gender_violations,
        )
```

- [ ] **Step 5: `build_story_library.py` — retry del build (tras el check de `dropped_lemmas`, línea ~184)**

```python
                if candidate.dropped_lemmas:
                    log.info(
                        "library.build.coverage_retry",
                        topic=topic,
                        attempt=attempt,
                        dropped=candidate.dropped_lemmas,
                    )
                    continue
                if candidate.gender_violations:
                    log.info(
                        "library.build.lint_retry",
                        topic=topic,
                        attempt=attempt,
                        violations=candidate.gender_violations,
                    )
                    continue
```

(el primer bloque ya existe; se añade solo el segundo.)

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && uv run pytest tests/ -v && uv run ruff check . && uv run ruff format --check .`
Expected: TODO verde — en particular `test_create_story_module.py` y `test_build_library.py` (si algún test construye `StoryDraft`/`GeneratedStory` a mano, el dataclass nuevo exige el campo: añadir `gender_violations=[]` en esos constructores).

- [ ] **Step 7: Commit**

```bash
git add backend/src/klara/services/story_gen.py backend/src/klara/curriculum/library.py \
  backend/src/klara/routers/stories.py backend/src/klara/scripts/build_story_library.py \
  backend/tests/test_story_lint.py backend/tests/test_library_service.py
git commit -m "feat(lint): wire gender gate into pool recycle + library build"
```

---

## Cierre

- [ ] Suite completa: `cd backend && uv run pytest tests/ -v` y `cd frontend && npm run typecheck && npm run i18n:check && npx vitest run && npm run build`.
- [ ] Roundtrip de migración: `cd backend && uv run alembic downgrade base && uv run alembic upgrade head` (contra la DB de test).
- [ ] `/verify` sobre el flujo real si hay entorno: story → quiz con fallo → retry round → summary → tap de dificultad → claim siguiente story (sesgo).
- [ ] PR con squash-merge (el repo agrega `(#NNN)`): título sugerido `feat: consenso 2026-07-13 — adaptive quiz ending, difficulty tap, due-vocab claim bias, gender lint gate`.

**Lo que este plan deliberadamente NO hace** (diferido por consenso — no "completar"):
- Session Generator dinámico (defer hasta que los datos muestren que la sesión fija se queda corta).
- Loop de recalibración de dificultad (leer `perceived_difficulty`/`elapsed_ms` para ajustar generación) — solo se MIDE.
- Tocar `srs_engine.py`, `srsProjection.ts`, o foldear pronunciación en SM-2.
