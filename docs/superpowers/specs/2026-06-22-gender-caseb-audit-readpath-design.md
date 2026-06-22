# Gender Case-B audit read-path — Design

**Slice C of the gender-curriculum backlog.** Owner-only observability over the suppressed Case-B disagreements.

## Problem

`reconcile_rule` (backend/src/klara/curriculum/gender_rules.py) persists a 6-key `GenderRuleDetail` on every `GenderAttempt.detail` where a suffix was detected — **including Case B**: the detected rule contradicts the oracle and the lemma is not a curated exception (`agreement=False AND is_exception=False`). These rows are suppressed from the learner (the output gate at `routers/stories.py` shows a rule only on `agreement || is_exception`) but stored as an audit signal. There is **no read-path** to surface them. Case B conflates three root causes worth triaging:

1. **Detector false positive** — a hard suffix matched a non-productive ending (e.g. *der Schwung* matches `-ung`).
2. **Inapplicable tendency** — a tendency suffix that this noun breaks (e.g. *die Mutter* vs `-er→der`).
3. **Possible oracle error** — the lexicon itself is wrong (rare; a hard disagreement is the suspicious signal).

## Decision

A **read-only CLI report**, not an HTTP endpoint. It is an owner tool run over SSH (mirrors the existing `load_de_*` loaders): zero new attack surface, no frontend/i18n, no auth plumbing. The unindexed JSONB scan is acceptable for an offline one-off.

## Architecture

Mirrors the loader split (logic in `curriculum/`, thin script in `scripts/`):

- **`backend/src/klara/curriculum/gender_audit.py`** — `gender_caseb_report(db) -> list[CaseBRow]` (testable, read-only). Query: `GenderAttempt JOIN VocabItem`, `WHERE detail IS NOT NULL AND detail->>'agreement'='false' AND detail->>'is_exception'='false'` (inverts the learner show-gate). Aggregates by `(lemma, suffix, suffix_class, rule_gender, oracle_gender, gender_source)` with `COUNT(*)` attempts and `COUNT(DISTINCT user_id)` users, ordered by attempts desc then lemma asc — systematic problems rise, one-off noise sinks.
- **`CaseBRow`** frozen dataclass: `lemma, suffix, suffix_class, rule_gender, oracle_gender, gender_source, attempts, users`, plus a `cause_hint` property: `"hard-disagreement"` (suffix_class hard → detector FP or oracle error, investigate) vs `"tendency-miss"` (tendency → expected). Makes the output actionable, not a bare count.
- **`backend/src/klara/scripts/audit_gender_caseb.py`** — thin CLI: `get_settings → init_engine → get_sessionmaker → gender_caseb_report → print (Spanish summary table) → dispose_engine`. **No commit** (read-only). Run: `uv run python -m klara.scripts.audit_gender_caseb`.

`detail` values are JSON booleans, so the predicate compares the `->>` text projection to the string `'false'`.

## Out of scope (v1 limits, documented)

- No JSONB GIN/expression index (full scan fine for offline owner use; revisit on volume).
- No write-side cause tagging — cause is inferred from `suffix_class` + the existing 6 keys.
- No cross-check against `GenderLexicon` (the `oracle_gender` in `detail` already IS the lexicon gender at record time).
- No HTTP endpoint, no frontend, no i18n.

## Testing

Backend pytest against the test DB. `gender_caseb_report` is the unit under test:
- isolates Case-B (excludes Case-A agreement, Case-C exception, and no-detail rows);
- aggregates by lemma with correct attempts + distinct-user counts, ordered by frequency;
- returns `[]` when there are no disagreements;
- `cause_hint` is `hard-disagreement` for hard, `tendency-miss` for tendency.
