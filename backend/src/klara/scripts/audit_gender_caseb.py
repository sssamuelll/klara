"""Owner-only offline audit: list suppressed Case-B gender disagreements
(a detected suffix rule contradicts the oracle and the lemma is not curated).
These are stored on GenderAttempt.detail but never shown to the learner; this
report surfaces them for triage — a detector false positive, an inapplicable
tendency, or a possible oracle error.

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
