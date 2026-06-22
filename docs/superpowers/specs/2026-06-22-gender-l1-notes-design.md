# Curated ES→DE gender L1-transfer notes — Design

**Slice A of the gender-curriculum backlog.** Hand-curated notes for L1 gender-transfer traps — German nouns whose gender clashes with the Spanish translation's gender (*el coche* → **das** Auto; *la mesa* → **der** Tisch).

> Revised twice: (1) after a spec roster review (oracle-gated gender, case-insensitive join, L1-key rationale); (2) after a **scope** roster review that reframed the whole lens — see Problem and A5/A8.

## Problem

Spanish L1 speakers carry gender from their native language onto German nouns. Where the two disagree, the learner is systematically biased toward the wrong article. These notes are **hand-authored curated content** — a human asserts the trap and writes the explanation.

**Why curated — the real reason (corrected after scope review).** NOT because Spanish gender is unknowable: Spanish grammatical gender given a lemma (*mesa*, f.) is a hard linguistic fact, as authoritative as German gender. The reason is **modality**. A trap is not a claim about a Spanish word's gender in isolation — it is a claim about a **translation edge**: which Spanish word *Auto* maps to (*coche*? *carro*? *máquina*?). That edge lives in `VocabItem.translations`, an LLM-written gloss with no provenance gate. A trap is a composite claim `mismatch( oracle_de(N), es_gender( gloss_de→es(N) ) )`; its authority is the **minimum** of its links, and the gloss link is soft. The system may therefore **generate** trap candidates from two oracles but may not **assert** one off a soft edge — a human ratifies the edge. **Edges are curated by ontology, not by scarcity of Spanish data.** This is the same modality discipline PR-C applied to suffix rules (suppress unless the oracle agrees). The old "no trusted Spanish-gender source" justification was wrong about the fact layer and is retired.

This also honors **Axiom-0** correctly: the composite trap claim must outrank the learner, and it only does so when a human has ratified its weakest link.

## Decisions (locked)

- **A1 — Storage:** a new lemma-keyed table `gender_l1_notes`, mirroring `GenderLexicon`'s authoritative / never-LLM design. Isolated from `VocabItem`, so curated prose is never clobbered.
- **A2 — Localization:** keyed by `(lemma, l1_language)`. v1 authors `es` only; the schema is ready for `fr`/`pt`/etc. A non-Spanish learner gets no notes (graceful empty), never Spanish prose.
- **A3 — Surface:** a "trampas de género" section in the `StoryFinish` **summary**, listing the story's target words that have a curated note in the story's L1. Broader coverage than the gender-cloze and reuses the finish UI.
- **A4 — Trigger:** shown for **every** story target word that has a curated note (regardless of quiz performance) — it is teaching.
- **A5 — Scope: corpus-complete over A1, NOT a sample, NOT the universe.** v1 = the mechanism + a seed covering the genuine ES↔DE clashes among the ~54 gendered nouns in `load_de_modules.py` (20 clashes, §Seed). The ES-contrast is an **L1-debiasing nudge, not a coverage layer** — der/die/das is already covered comprehensively by the German oracle + suffix engine + cloze. "Cover the universe" is the wrong goal here; "cover the real A1 corpus the learner meets" is the honest denominator. 17 was an arbitrary sample (too small); the whole noun-inventory auto-derive is wrong (see A8). Growth is additive (idempotent upsert) as the German corpus grows.
- **A6 — Copy:** the section heading microcopy (6 locales) and the seed note prose go through solace-wren. The heading is on the critical path; note prose ships as a correct first draft.
- **A7 — L1 key = `story.native_language` (snapshot), by design.** The notes deliberately differ from cloze/insight (which use live `user.native_language`): a curated note is a fixed-language artifact and must be in the language the learner is actually reading on that screen (the story's glosses are already in `story.native_language`). `String(8) NOT NULL`, safe to read.
- **A8 — Auto-derive is DEFERRED and explicitly BLOCKED, not killed.** Auto-deriving traps for the whole noun inventory and serving them is forbidden today — it runs a hard Spanish-gender lexicon over a SOFT LLM gloss and ships confident-but-wrong traps at scale (the exact "LLM guess certified as truth" failure the `gender_source` gate prevents), failing worst on polysemous nouns (*die See* → *el mar*/*la laguna*). It is **not** blocked on finding a Spanish dictionary (buildable, e.g. Wiktionary CC-BY-SA). It is blocked on **giving `VocabItem.translations` its own provenance gate** (mirroring `gender_source`). Until a gloss can be marked oracle-grade, auto-assertion violates Axiom-0. The legitimate middle step (later): a Spanish-gender lexicon used **offline as a candidate generator** — emit a frequency-ranked worklist of probable mismatches for a human curator to ratify. The machine proposes; the human asserts; the lookup never writes a learner-facing claim. Tracked as issue #83.

## Data model

```python
class GenderL1Note(Base):
    __tablename__ = "gender_l1_notes"
    lemma: Mapped[str] = mapped_column(String(120), primary_key=True)        # German lemma, e.g. "Auto"
    l1_language: Mapped[str] = mapped_column(String(8), primary_key=True)    # learner L1, canonical lowercase, e.g. "es"
    note: Mapped[str] = mapped_column(String(400), nullable=False)           # curated prose in the L1
```

Composite PK `(lemma, l1_language)`. Authoritative, never written by the LLM. Alembic migration `0012_gender_l1_notes`. **The DE gender is NOT stored here** — resolved authoritatively from the oracle at serve time.

## Seed / authoring

`backend/src/klara/scripts/load_de_l1_notes.py` — inline `(lemma, l1_language, note)` seeds (mirrors `load_de_modules.py`), loaded via idempotent upsert in `curriculum/`:

- **Upsert:** `on_conflict_do_update(index_elements=["lemma", "l1_language"], set_={"note": ...})` — re-seeding edited prose updates the row (mirrors `load_gender_lexicon`).
- **Validation at load:** reject empty/whitespace notes; length ≤ 400; canonicalize `l1_language` to lowercase.
- **The 20 v1 `es` seeds** (corpus-complete over A1; DE article shown by the frontend, note prose by solace-wren):
  - **der (vs ES fem):** Tisch (la mesa), Stuhl (la silla), Apfel (la manzana), Bahnhof (la estación)
  - **das (vs ES masc/fem):** Auto (el coche), Geld (el dinero), Jahr (el año), Brot (el pan), Land (el país), Haus (la casa), Bett (la cama), Fenster (la ventana), Zimmer (la habitación), Geschäft (la tienda), Fahrrad (la bicicleta)
  - **die (vs ES masc):** Minute (el minuto), Sprache (el idioma), Wohnung (el piso), Zahl (el número), Bahn (el tren)
- **Excluded as ambiguous** (the roster's "edges break loudest on ambiguity" rule): Wasser (*el agua* euphonic-fem), Zucker (*el/la azúcar*), Kind (*niño/a*, natural gender), Uhr (*reloj/hora* mixed), Morgen (*mañana* = morning/tomorrow polysemy), Abend (*Abend* ≈ evening ≠ *tarde* strictly). Do not author notes for two-gendered homographs.

Run: `uv run python -m klara.scripts.load_de_l1_notes`.

## Serving

`GET /stories/{story_id}/gender/l1-notes` → `GenderL1NotesOut { notes: list[{ lemma, gender, note }] }`. Owner-gated via `_load_or_404(db, story_id, user.id, locale)`; mirrors `GET /{story_id}/insight`.

1. Short-circuit empty `target_vocab_item_ids` → `{notes: []}`.
2. Load target `VocabItem`s, restricted to `language == "de"` and `pos == NOUN`.
3. **Oracle-gated gender:** displayed `gender` guarded by `gender_source == "oracle" AND gender IN {der,die,das}` (mirrors `build_gender_cloze`). A word without an authoritative gender is **dropped**. Response contract: `gender` is always `der|die|das`, never null.
4. **Case-insensitive lemma join:** `lower(GenderL1Note.lemma) == lower(VocabItem.lemma)`, filtering `l1_language == lower(story.native_language)`. Exact lemma only — no compound-head fallback.
5. **Dedup by lemma:** one line per lemma; gender is the oracle-resolved (deterministic) value.

Returns only words with a note; empty when none / non-seeded L1 / no oracle gender.

## Frontend

`StoryFinish` Summary fetches the notes async (like insight); renders a section: a localized heading plus one line per note — `«{gender} {lemma}»` (e.g. «das Auto») then the curated note, **plain text** (no markup). The `«{gender} {lemma}»` prefix is authored not to be redundant with the prose. Section hidden when empty. Heading is i18n chrome (6 locales); the note **body** is curated L1 content from the DB, not i18n'd.

## i18n

`story.finish.summary.l1Notes.title` (+ `.hint`) in all 6 locales (`es` source; `i18n:check` parity). solace-wren copy.

## Out of scope / explicitly NOT doing

- Auto-DERIVING traps and serving them to the learner (A8 — blocked on a translation provenance gate, not on a Spanish dictionary).
- "Cover the universe" as the goal for this slice (the German oracle already does; this is a debiasing nudge).
- A `target_language` column (DE-only enforced at the query, `language == "de"`).
- An admin/editing UI (in-repo seed script).
- Notes for two-gendered / ambiguous nouns (excluded at authoring).
- Compound-head matching for note selection (exact lemma only).

## Testing

- Model + idempotent upsert: seeding twice stable; re-seeding edited prose updates; uniqueness holds; empty/over-length rejected at load.
- Endpoint: returns oracle-resolved notes for an `es` story; a `gender_source=="llm"` word + matching seed is NOT returned; a seed `"Auto"` matches a VocabItem `"auto"` (case-insensitive); empty for non-seeded L1 / no trap words / empty target list; non-canonical `native_language == "ES"` still matches `es`; owner-gated 404; **integration:** a stock A1 `es` story returns a non-empty list.
- Alembic migration roundtrip; add `gender_l1_notes` to the conftest truncate list; re-seed in-fixture per endpoint test.
- Frontend `typecheck` + `build` + `i18n:check`.
