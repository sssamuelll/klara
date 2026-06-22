"""Owner-only read path over the suppressed Case-B gender disagreements.

Case B = a GenderAttempt whose `detail` records a detected suffix rule that
CONTRADICTS the oracle and is NOT a curated exception (reconcile_rule with
agreement=False and is_exception=False). Stored as an audit signal, never shown
to the learner (stories.record_gender_attempt gates learner output on
agreement|is_exception). This module inverts that gate for offline triage.
Read-only; no commit.
"""

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
    oracle_gender: str  # der | die | das  (the authoritative truth)
    gender_source: str  # oracle | llm | user
    attempts: int
    users: int

    @property
    def cause_hint(self) -> str:
        # A hard suffix is ~100% reliable, so a hard disagreement is suspicious
        # (a detector false positive, or an oracle error) and worth investigating.
        # A tendency disagreement is expected noise.
        return "hard-disagreement" if self.suffix_class == "hard" else "tendency-miss"


async def gender_caseb_report(db: AsyncSession) -> list[CaseBRow]:
    """Aggregate suppressed Case-B disagreements by lemma, most frequent first.

    detail values are JSON booleans, so the predicate compares the ``->>`` text
    projection to the string ``'false'``.
    """
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
            # reconcile_rule always writes all 6 keys, so a present detail has a
            # suffix; this guard keeps CaseBRow.suffix honestly non-null even if a
            # malformed row ever slipped in, rather than projecting NULL -> "None".
            suffix.isnot(None),
            d["agreement"].astext == "false",
            d["is_exception"].astext == "false",
        )
        # Aggregation unit is the lemma — a lemma-level question ("which word's
        # rule disagrees with the oracle?"). gender_source is grouped so an
        # oracle/llm split never merges; in practice attempts are gated to oracle
        # de NOUNs (unique per lemma), so lemma collisions do not arise.
        .group_by(
            VocabItem.lemma,
            suffix,
            suffix_class,
            rule_gender,
            oracle_gender,
            VocabItem.gender_source,
        )
        .order_by(attempts.desc(), VocabItem.lemma.asc(), suffix.asc())
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
