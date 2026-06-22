# Gender Case-B audit read-path — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans.

**Goal:** An owner-run CLI report listing the suppressed Case-B gender disagreements stored on `GenderAttempt.detail`.

**Architecture:** Read-only. Aggregation logic in `curriculum/gender_audit.py`, thin CLI in `scripts/audit_gender_caseb.py`. Mirrors the `load_de_*` loader split. No migration, no index, no HTTP.

**Tech Stack:** SQLAlchemy async + Postgres JSONB. Backend pytest. ruff (E,F,I,B,UP,RUF).

---

## Task 1: Aggregation function + dataclass (TDD)

**Files:**
- Create: `backend/src/klara/curriculum/gender_audit.py`
- Test: `backend/tests/test_gender_audit.py`

- [ ] **Step 1: Write failing tests** — isolate Case-B; aggregate + order; empty; cause_hint. (Full code in Task 1 of this plan.)
- [ ] **Step 2: Run, expect ImportError/fail.** `cd backend && uv run pytest tests/test_gender_audit.py -q`
- [ ] **Step 3: Implement `gender_caseb_report` + `CaseBRow`.**
- [ ] **Step 4: Run, expect PASS.**

```python
# backend/src/klara/curriculum/gender_audit.py
"""Owner-only read path over the suppressed Case-B gender disagreements.

Case B = a GenderAttempt whose `detail` records a detected suffix rule that
CONTRADICTS the oracle and is NOT a curated exception (reconcile_rule with
agreement=False and is_exception=False). Stored as an audit signal, never shown
to the learner (stories.record_gender_attempt gates learner output on
agreement|is_exception). This inverts that gate for offline triage. Read-only."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import GenderAttempt, VocabItem


@dataclass(frozen=True, slots=True)
class CaseBRow:
    lemma: str
    suffix: str
    suffix_class: str  # hard | tendency
    rule_gender: str  # der | die | das  (what the rule predicted)
    oracle_gender: str  # der | die | das  (authoritative truth)
    gender_source: str  # oracle | llm | user
    attempts: int
    users: int

    @property
    def cause_hint(self) -> str:
        # A hard suffix is ~100% reliable, so a hard disagreement is suspicious
        # (detector false positive or an oracle error) and worth investigating.
        # A tendency disagreement is expected noise.
        return "hard-disagreement" if self.suffix_class == "hard" else "tendency-miss"


async def gender_caseb_report(db: AsyncSession) -> list[CaseBRow]:
    """Aggregate suppressed Case-B disagreements, most frequent first. detail
    values are JSON booleans, so the predicate compares the ->> text projection
    to the string 'false'."""
    d = GenderAttempt.detail
    suffix = d["suffix"].astext
    suffix_class = d["suffix_class"].astext
    rule_gender = d["rule_gender"].astext
    oracle_gender = d["oracle_gender"].astext
    attempts = func.count(GenderAttempt.id)
    users = func.count(func.distinct(GenderAttempt.user_id))
    stmt = (
        select(
            VocabItem.lemma,
            suffix.label("suffix"),
            suffix_class.label("suffix_class"),
            rule_gender.label("rule_gender"),
            oracle_gender.label("oracle_gender"),
            VocabItem.gender_source,
            attempts.label("attempts"),
            users.label("users"),
        )
        .join(VocabItem, VocabItem.id == GenderAttempt.vocab_item_id)
        .where(
            d.isnot(None),
            d["agreement"].astext == "false",
            d["is_exception"].astext == "false",
        )
        .group_by(
            VocabItem.lemma,
            suffix,
            suffix_class,
            rule_gender,
            oracle_gender,
            VocabItem.gender_source,
        )
        .order_by(attempts.desc(), VocabItem.lemma.asc())
    )
    result = await db.execute(stmt)
    return [
        CaseBRow(
            lemma=r.lemma,
            suffix=r.suffix,
            suffix_class=r.suffix_class,
            rule_gender=r.rule_gender,
            oracle_gender=r.oracle_gender,
            gender_source=r.gender_source,
            attempts=r.attempts,
            users=r.users,
        )
        for r in result
    ]
```

---

## Task 2: Thin CLI wrapper

**Files:**
- Create: `backend/src/klara/scripts/audit_gender_caseb.py`

- [ ] **Step 1: Implement** (mirrors `load_de_gender.py` shape; no commit).
- [ ] **Step 2: Smoke** — `uv run python -m klara.scripts.audit_gender_caseb` against the test DB prints the no-rows line without error.

```python
# backend/src/klara/scripts/audit_gender_caseb.py
"""Owner-only offline audit: list suppressed Case-B gender disagreements
(a detected suffix rule contradicts the oracle and the lemma is not curated).
Stored on GenderAttempt.detail but never shown to the learner; this surfaces
them for triage — detector false positive, inapplicable tendency, or oracle error.

Usage:
    uv run python -m klara.scripts.audit_gender_caseb

Read-only: no writes, no commit.
"""

from __future__ import annotations

import asyncio

from klara.config import get_settings
from klara.curriculum.gender_audit import gender_caseb_report
from klara.db import dispose_engine, get_sessionmaker, init_engine


async def _run() -> None:
    settings = get_settings()
    init_engine(settings)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            rows = await gender_caseb_report(db)
        if not rows:
            print("Sin discrepancias Caso-B: el detector y el oraculo coinciden.")
            return
        total = sum(r.attempts for r in rows)
        print(f"Discrepancias Caso-B: {len(rows)} lemas, {total} intentos.\n")
        header = (
            f"{'lema':<22}{'sufijo':<10}{'clase':<10}"
            f"{'regla->oraculo':<16}{'#int':>5}{'#usr':>6}  causa"
        )
        print(header)
        print("-" * len(header))
        for r in rows:
            arrow = f"{r.rule_gender}->{r.oracle_gender}"
            print(
                f"{r.lemma:<22}-{r.suffix:<9}{r.suffix_class:<10}"
                f"{arrow:<16}{r.attempts:>5}{r.users:>6}  {r.cause_hint}"
            )
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

---

## Task 3: Verify

- [ ] `cd backend && uv run pytest tests/test_gender_audit.py -q` — PASS.
- [ ] `cd backend && uv run ruff check --fix src tests && uv run ruff format src tests` — clean.
- [ ] Full suite green; commit; PR; merge on green (explicit prod-deploy authorization).
