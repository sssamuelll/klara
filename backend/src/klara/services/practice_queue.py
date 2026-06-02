"""Builds the Practice ("Pronunciar") queue from recent pronunciation attempts.

Scope (this PR): STRUGGLED-ONLY. The queue carries sentences the learner
recently mispronounced, where the origin sentence is resolved cleanly from
the source story (story_id + sentence_index → Story.content["sentences"][i]).

Two deliberate deferrals, decided up front so the contract stays stable:

  * `review` (SRS-due) items are OUT of this PR. They enter once we settle a
    clean origin-sentence resolution for an SRS lemma (likely "the last story
    where the lemma appeared"). Until then, mixing a synthetic sentence in
    would dilute the "say the line you actually read" model. Pending.

  * struggled ∩ review dedup is therefore N/A here (no review items exist).
    Decision already taken for the PR that introduces review items: when a
    word is BOTH struggled AND SRS-due, it appears ONCE with reason
    "struggled" — the more urgent signal, it avoids burning two queue slots,
    and practising the struggled sentence already exercises the word. Not
    implemented now; documented so the future PR doesn't relitigate it.

  * `variants` (variety-by-level alternatives) is also deferred — every item
    here returns `variants=[]`, identical to the mock the frontend currently
    ships. Variety arrives with its own LLM path in a later PR.

  * Persisting attempts FROM Practice (so practising feeds back into the
    struggled signal) is deferred too: it needs widening the PracticeItem
    contract with storyId/sentenceIndex and per-item persist in the hook.
    Pending.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import PronunciationAttempt, Story
from klara.schemas.practice import (
    PracticeItemOut,
    PracticeQueueOut,
    PracticeSentenceOut,
)

# --- Tunable thresholds ----------------------------------------------------
# Product knobs, deliberately named and kept next to the logic they govern so
# they're trivial to adjust. (They're not env Settings: they're behavioural
# tuning, not deployment config, and live where the reasoning about them is.)

# How far back to look for "recent" struggle. Older attempts are stale signal.
RECENT_ATTEMPTS_WINDOW_DAYS = 14
# An attempt scores as "struggled" when its overall score is below this.
# Mirrors the frontend band cut (>=70 = "good"): below 70 is not yet solid.
STRUGGLED_SCORE_THRESHOLD = 70.0
# Default queue length when the caller doesn't pass ?limit=.
DEFAULT_QUEUE_LIMIT = 6

# Token band ranking, worst → best. Used to pick the single worst token of a
# sentence as the focus word. `bad` < `ok` < `good`; unknown bands sort safe.
_BAND_RANK = {"bad": 0, "ok": 1, "good": 2}

# Tokenizer mirrors frontend `wordTokenIndices` (lib/pronunciation.ts) EXACTLY:
# whitespace / punctuation / word, advancing a global token counter and
# emitting an index only for word tokens. word_bands is keyed by that global
# index, so the backend must tokenize identically to map index → token text.
_TOKEN_RE = re.compile(r"(\s+)|([.,!?;:„“”»«()¡¿—–\-]+)|([^\s.,!?;:„“”»«()¡¿—–\-]+)")


def _word_tokens_by_index(text: str) -> dict[int, str]:
    """Return {global_token_index: word_text} for word tokens only.

    The global index counts every token (space, punctuation, word) so it lines
    up with the keys in `word_bands` produced by the frontend's
    `bandsByTokenIndex`.
    """
    out: dict[int, str] = {}
    i = 0
    for m in _TOKEN_RE.finditer(text):
        if m.group(3):  # word token
            out[i] = m.group(3)
        i += 1
    return out


def _worst_token(reference_text: str, word_bands: dict) -> str | None:
    """Pick the worst-scored word token of a sentence.

    Ranks tokens by band (bad < ok < good); among equal bands, the
    earliest-appearing token wins (stable, deterministic). Returns None when
    there are no usable word/band pairs (caller degrades gracefully).
    """
    tokens = _word_tokens_by_index(reference_text)
    if not tokens or not word_bands:
        return None
    best: tuple[int, int, str] | None = None  # (band_rank, token_index, text)
    for key, band in word_bands.items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        token = tokens.get(idx)
        if token is None:
            continue
        rank = _BAND_RANK.get(band, 99)
        candidate = (rank, idx, token)
        if best is None or candidate < best:
            best = candidate
    return best[2] if best is not None else None


def _focus_translation(sentence: dict, focus_text: str) -> str:
    """Find the clean per-word translation for the focus token.

    Source of truth is the story sentence's `breakdown` (word→translation map
    produced at generation time). Degradation, documented: when there's no
    breakdown, or the focus token isn't in it, return "" — the frontend type
    requires a string, and an empty gloss is better than a wrong one.
    """
    breakdown = sentence.get("breakdown")
    if not isinstance(breakdown, list):
        return ""
    target_norm = focus_text.casefold()
    for entry in breakdown:
        if not isinstance(entry, dict):
            continue
        word = entry.get("word")
        if isinstance(word, str) and word.casefold() == target_norm:
            tx = entry.get("translation")
            return tx if isinstance(tx, str) else ""
    return ""


async def build_struggled_queue(
    db: AsyncSession,
    *,
    user_id: UUID,
    target_language: str,
    limit: int = DEFAULT_QUEUE_LIMIT,
) -> PracticeQueueOut:
    """Assemble today's struggled-only practice queue for a user.

    Algorithm:
      1. Pull recent (< window) attempts that scored below the struggle
         threshold, newest first.
      2. Group by (story_id, sentence_index), keeping the FIRST seen per group
         — which, given the newest-first order, is the most-recent attempt for
         that sentence. (Most-recent is also the most-relevant struggle.)
      3. Resolve each group's origin sentence from Story.content, pick the
         worst-scored token as the focus word + its clean translation.
      4. Cap at `limit`.
    """
    cutoff = datetime.now(UTC) - timedelta(days=RECENT_ATTEMPTS_WINDOW_DAYS)
    stmt = (
        select(PronunciationAttempt)
        .where(
            PronunciationAttempt.user_id == user_id,
            PronunciationAttempt.overall_score < STRUGGLED_SCORE_THRESHOLD,
            PronunciationAttempt.attempted_at >= cutoff,
        )
        .order_by(PronunciationAttempt.attempted_at.desc())
    )
    attempts = (await db.execute(stmt)).scalars().all()

    # Most-recent attempt per (story, sentence). dict preserves insertion
    # order, and we iterate newest-first, so setdefault keeps the newest.
    latest_by_sentence: dict[tuple[UUID, int], PronunciationAttempt] = {}
    for a in attempts:
        latest_by_sentence.setdefault((a.story_id, a.sentence_index), a)

    if not latest_by_sentence:
        return PracticeQueueOut(items=[], target_language=target_language, source_title="")

    # Batch-load the stories referenced, to resolve clean origin sentences.
    story_ids = {sid for (sid, _) in latest_by_sentence}
    story_rows = (await db.execute(select(Story).where(Story.id.in_(story_ids)))).scalars().all()
    stories_by_id = {s.id: s for s in story_rows}

    items: list[PracticeItemOut] = []
    # Collect the distinct source titles actually emitted. A queue-level
    # source_title only makes sense when every item comes from ONE story;
    # the moment we mix stories, a single title mislabels the set, so we
    # leave it blank and the frontend omits the "from <story>" signature.
    source_titles: set[str] = set()
    for (story_id, sentence_index), attempt in latest_by_sentence.items():
        story = stories_by_id.get(story_id)
        if story is None:
            continue
        # The queue advertises the user's CURRENT target_language. A user who
        # switched learning languages can still have recent attempts on stories
        # in an older language; emitting those would produce a mixed-language
        # queue under a single top-level targetLanguage. Skip foreign-language
        # stories so the queue stays consistent with its advertised metadata.
        if story.target_language != target_language:
            continue
        sentences = (story.content or {}).get("sentences") or []
        if not (0 <= sentence_index < len(sentences)):
            continue
        sentence = sentences[sentence_index]
        target = sentence.get("target") or ""
        native = sentence.get("native") or ""
        if not target:
            continue

        # Focus token: worst-scored word of the sentence. Fall back to the
        # recorded reference_text tokenization if the stored band map and the
        # current story text line up; if no worst token can be derived, skip
        # the item rather than guess.
        focus = _worst_token(attempt.reference_text, attempt.word_bands or {})
        if focus is None:
            continue
        focus_tx = _focus_translation(sentence, focus)

        source_titles.add(story.title)

        items.append(
            PracticeItemOut(
                sentence=PracticeSentenceOut(target=target, native=native),
                variants=[],
                source=story.title,
                focus_text=focus,
                focus_tx=focus_tx,
                reason="struggled",
            )
        )
        if len(items) >= limit:
            break

    return PracticeQueueOut(
        items=items,
        target_language=target_language,
        # Single story → its title; mixed (or none) → blank, the front omits it.
        source_title=next(iter(source_titles)) if len(source_titles) == 1 else "",
    )
