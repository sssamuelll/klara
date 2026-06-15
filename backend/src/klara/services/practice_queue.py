"""Builds the Practice ("Pronunciar") queue: struggled lines + SRS-due review.

The queue mixes two signals into one pronunciation set:

  * STRUGGLED — sentences the learner recently mispronounced, origin resolved
    cleanly from the source story (story_id + sentence_index →
    Story.content["sentences"][i]). The worst token is the focus word.

  * REVIEW — SRS-due vocab (UserCard due, same clause as routers/srs.py
    due_cards), surfaced as a line to say aloud. The origin sentence is
    resolved as "the last story where the lemma appeared"; if the lemma
    never surfaces in a breakdown (inflected forms etc.), we fall back to the
    vocab item's own `example_target` sentence.

Dedup (decision on file): when a word is BOTH struggled AND SRS-due it appears
ONCE, as reason "struggled" — the more urgent signal, it avoids burning two
queue slots, and practising the struggled sentence already exercises the word.
Matching is by focus_text.casefold() against the review lemma (we do NOT
introduce a text→vocab_item resolution just for dedup).

Ordering: struggled first, then review, capped at `limit`. The frontend only
counts chips per reason, so any stable order is valid; struggled-first keeps
the more urgent signal at the top of the set.

Two deliberate deferrals, decided up front so the contract stays stable:

  * `variants` (variety-by-level alternatives) is deferred — every item here
    returns `variants=[]`, identical to the mock the frontend currently ships.
    Variety arrives with its own LLM path in a later PR.

  * Persisting attempts FROM Practice (so practising feeds back into the
    struggled signal) is deferred too: it needs widening the PracticeItem
    contract with storyId/sentenceIndex and per-item persist in the hook.
    Pending (PR #3b).

A known data fragility, documented not "fixed" here: VocabItem.language
defaults to "de". Old lemmas seeded before the column was populated correctly
carry "de" regardless of their true language, so the `language ==
target_language` filter on review items can silently empty the review set for
a non-German learner. This is a data-hygiene issue, not a query bug — do not
paper over it by relaxing the filter (that would leak foreign-language lines
into the queue). Fix the data, not the predicate.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import PronunciationAttempt, Story, UserCard, VocabItem
from klara.schemas.practice import (
    PracticeItemOut,
    PracticeQueueOut,
    PracticeSentenceOut,
)
from klara.services.tokens import BAND_RANK as _BAND_RANK
from klara.services.tokens import word_tokens_by_index as _word_tokens_by_index

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


async def _build_struggled_items(
    db: AsyncSession,
    *,
    user_id: UUID,
    target_language: str,
    limit: int,
) -> tuple[list[PracticeItemOut], set[str]]:
    """Build struggled items, returning (items, distinct source titles).

    Algorithm:
      1. Pull recent (< window) attempts that scored below the struggle
         threshold, newest first.
      2. Group by (story_id, sentence_index), keeping the FIRST seen per group
         — which, given the newest-first order, is the most-recent attempt for
         that sentence. (Most-recent is also the most-relevant struggle.)
      3. Resolve each group's origin sentence from Story.content, pick the
         worst-scored token as the focus word + its clean translation.
      4. Cap at `limit`.

    `source_titles` is collected so the caller can decide the queue-level
    sourceTitle (single story → its title; mixed → blank).
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
        return [], set()

    # Batch-load the stories referenced, to resolve clean origin sentences.
    story_ids = {sid for (sid, _) in latest_by_sentence}
    story_rows = (await db.execute(select(Story).where(Story.id.in_(story_ids)))).scalars().all()
    stories_by_id = {s.id: s for s in story_rows}

    items: list[PracticeItemOut] = []
    # Collect the distinct source titles actually emitted, for the caller's
    # queue-level sourceTitle decision (single story → title; mixed → blank).
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
                # Origin is resolved cleanly: this line IS Story.content[
                # sentence_index], so a Practice attempt on it persists against
                # the same (story_id, sentence_index) the struggle came from.
                story_id=str(story_id),
                sentence_index=sentence_index,
            )
        )
        if len(items) >= limit:
            break

    return items, source_titles


def _resolve_review_sentence(
    story: Story | None, lemma: str
) -> tuple[PracticeSentenceOut, int] | None:
    """Find the first sentence of `story` whose breakdown contains `lemma`.

    Match is casefold against breakdown `word` entries, mirroring
    `_focus_translation`. Returns (sentence, sentence_index) where the index is
    the position INTO Story.content["sentences"] — the same index a Practice
    attempt must persist against (PR #3b) so it lands on the right struggled
    grouping. Returns None when the lemma surfaces in no breakdown — the caller
    then degrades to the vocab item's own example (which has no story index).
    """
    if story is None:
        return None
    sentences = (story.content or {}).get("sentences") or []
    target_norm = lemma.casefold()
    for index, sentence in enumerate(sentences):
        if not isinstance(sentence, dict):
            continue
        breakdown = sentence.get("breakdown")
        if not isinstance(breakdown, list):
            continue
        for entry in breakdown:
            if not isinstance(entry, dict):
                continue
            word = entry.get("word")
            if isinstance(word, str) and word.casefold() == target_norm:
                target = sentence.get("target") or ""
                if not target:
                    continue
                resolved = PracticeSentenceOut(target=target, native=sentence.get("native") or "")
                return resolved, index
    return None


async def build_review_items(
    db: AsyncSession,
    *,
    user_id: UUID,
    target_language: str,
    native_language: str,
    limit: int,
) -> list[PracticeItemOut]:
    """Build SRS-due review items as pronunciation lines.

    Algorithm:
      1. Load due UserCards (same clause + order as routers/srs.py due_cards:
         next_review_at IS NULL OR <= now, ordered next_review_at ASC
         nullsfirst), joined to VocabItem, filtered to the user's current
         target_language. The language filter keeps the queue single-language;
         see the module docstring on the VocabItem.language data fragility.
         We do NOT pre-limit the query: a due card can fail to yield an item
         (no story line AND no `example_target`), so capping the SQL at `limit`
         would let unusable cards crowd out usable ones further down the
         due-order and under-fill the queue. Due cards per user are bounded by
         the vocabulary size, so loading them all is harmless; the in-memory
         guard below is the single cut, and the next_review_at ASC order makes
         it cut by soonest-due.
      2. For each due lemma, find its most-recent story (Story.created_at DESC)
         whose target_vocab_item_ids contains the vocab id, then the first
         sentence in that story whose breakdown contains the lemma.
      3. If no such sentence exists (inflected form, or lemma absent from every
         breakdown), fall back to the vocab item's own `example_target`.
      4. Cap at `limit` in memory (the only cut), after filtering unusable cards.
    """
    now = datetime.now(UTC)
    stmt = (
        select(UserCard, VocabItem)
        .join(VocabItem, VocabItem.id == UserCard.vocab_item_id)
        .where(
            UserCard.user_id == user_id,
            VocabItem.language == target_language,
            or_(UserCard.next_review_at.is_(None), UserCard.next_review_at <= now),
        )
        .order_by(UserCard.next_review_at.asc().nullsfirst())
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    items: list[PracticeItemOut] = []
    for _card, vocab in rows:
        lemma = vocab.lemma
        # Most-recent story where this lemma is a target vocab item.
        story = (
            await db.execute(
                select(Story)
                .where(
                    Story.user_id == user_id,
                    Story.target_vocab_item_ids.any(vocab.id),
                )
                .order_by(Story.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        resolved = _resolve_review_sentence(story, lemma)
        # Capture provenance BEFORE the fallback reassigns `sentence`: the line
        # is story-sourced only when it was resolved FROM the story breakdown.
        # A line that comes from `example_target` must never be attributed to a
        # story that merely matched the lemma but doesn't contain that sentence.
        from_story = resolved is not None and story is not None
        # The sentence and its index INTO the origin story, when story-sourced.
        # A fallback (example_target) item has neither → (storyId, sentenceIndex)
        # stay None and that item is NOT persisted from Practice.
        sentence = resolved[0] if resolved is not None else None
        story_sentence_index = resolved[1] if resolved is not None else None
        # Clean per-word gloss for the focus lemma, when the resolved sentence
        # came from a story breakdown; else the vocab translation.
        focus_tx = vocab.translations.get(native_language) if vocab.translations else None
        if sentence is not None and story is not None:
            # Prefer the story-breakdown gloss to stay consistent with struggled
            # items; the breakdown lives on the RESOLVED sentence. Index DIRECTLY
            # with story_sentence_index — re-scanning for the first sentence whose
            # target matches grabs the wrong one when a story repeats an identical
            # target. Degrade safely if the index is somehow out of range.
            sentences = (story.content or {}).get("sentences") or []
            if story_sentence_index is not None and 0 <= story_sentence_index < len(sentences):
                s = sentences[story_sentence_index]
                if isinstance(s, dict):
                    tx = _focus_translation(s, lemma)
                    if tx:
                        focus_tx = tx
        else:
            # Fallback: the vocab item's own canonical example.
            # `example_target` gives the TARGET line, but VocabItem carries no
            # native translation OF THE FULL SENTENCE — only per-lemma
            # translations. We use translations[native_language] as the native
            # gloss (the lemma's meaning), which is honest about what it is (a
            # word gloss, not a sentence translation) rather than fabricating a
            # full-sentence translation we don't have. "" when even that is
            # missing — never invent text.
            if not vocab.example_target:
                # No story line AND no example to say aloud → nothing to drill.
                continue
            sentence = PracticeSentenceOut(
                target=vocab.example_target,
                native=focus_tx or "",
            )

        items.append(
            PracticeItemOut(
                sentence=sentence,
                variants=[],
                source=story.title if (story is not None and from_story) else "",
                focus_text=lemma,
                focus_tx=focus_tx or "",
                reason="review",
                # Persist provenance only for story-sourced review lines. The
                # decision on file: a review item backed by a REAL story sentence
                # persists its attempt against that (storyId, sentenceIndex),
                # feeding the same struggled pipeline. A fallback example_target
                # line has no real story sentence → None, None → not persisted.
                story_id=str(story.id) if from_story and story is not None else None,
                sentence_index=story_sentence_index if from_story else None,
            )
        )
        if len(items) >= limit:
            break

    return items


async def build_practice_queue(
    db: AsyncSession,
    *,
    user_id: UUID,
    target_language: str,
    native_language: str,
    limit: int = DEFAULT_QUEUE_LIMIT,
) -> PracticeQueueOut:
    """Assemble the combined struggled + review practice queue.

    Struggled items come first, then review items, deduped so a word that is
    both struggled and SRS-due appears once (as struggled). Dedup is by
    focus_text.casefold() against the review lemma — no text→vocab resolution.
    The whole set is capped at `limit`.
    """
    struggled_items, source_titles = await _build_struggled_items(
        db, user_id=user_id, target_language=target_language, limit=limit
    )

    items: list[PracticeItemOut] = list(struggled_items[:limit])
    struggled_focus = {it.focus_text.casefold() for it in items}

    remaining = limit - len(items)
    if remaining > 0:
        # Pull a few extra review candidates beyond `remaining`, since some may
        # be dropped by dedup; cap the over-fetch so it stays cheap.
        review_items = await build_review_items(
            db,
            user_id=user_id,
            target_language=target_language,
            native_language=native_language,
            limit=remaining + len(struggled_focus),
        )
        for it in review_items:
            if it.focus_text.casefold() in struggled_focus:
                continue  # struggled ∩ review → keep the struggled item only
            items.append(it)
            if len(items) >= limit:
                break

    # Queue-level sourceTitle only makes sense for a homogeneous single-story
    # queue. It stays set only when every emitted item is struggled AND from
    # one story; the moment a review item lands (each carrying its own
    # per-item `source`) or stories mix, blank it so the frontend omits the
    # now-ambiguous "from <story>" signature.
    any_review = any(it.reason == "review" for it in items)
    source_title = next(iter(source_titles)) if len(source_titles) == 1 and not any_review else ""

    return PracticeQueueOut(
        items=items,
        target_language=target_language,
        source_title=source_title,
    )
