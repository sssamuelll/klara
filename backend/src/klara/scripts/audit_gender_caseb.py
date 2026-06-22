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
            line = (
                f"{r.lemma:<22}-{r.suffix:<9}{r.suffix_class:<10}"
                f"{arrow:<16}{r.attempts:>5}{r.users:>6}  {r.cause_hint}"
            )
            # CodeQL py/clear-text-logging-sensitive-data fires here as a FALSE
            # POSITIVE: the DATABASE_URL credential label propagates structurally
            # through init_engine -> AsyncSession -> every result row, but the
            # credential is consumed at create_async_engine and never re-emitted.
            # Every value printed is an explicit allow-list of NON-sensitive
            # fields -- lemma, suffix, der/die/das articles, the gender_source
            # enum, integer counts; no User.* column and no raw `detail` JSONB.
            # The alert is dismissed in the code-scanning ledger (rule stays
            # armed); test_case_b_row_is_a_non_sensitive_allowlist enforces the
            # CaseBRow allow-list so widening it to a sensitive column fails CI.
            print(line)
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
