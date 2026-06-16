# Curriculum Foundation — PR-B: advancement gate + A1 module sequence

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the curriculum loop's last link: when a user masters the active module's vocab (via SRS reviews), advance them to the next module — forward-only. And author the full German A1 module sequence so the loop has somewhere to go.

**Architecture:** PR-A built the Module entity, module-driven generation, auto-enroll, and the two progress signals. PR-B adds (1) `advance_module_if_mastered`, called from `submit_review` (the only place mastery changes) — a no-op unless the reviewed card belongs to the active module and that module's `mastered/total ≥ mastery_threshold`, in which case `current_module_id` moves to the next `sequence_order`; (2) the authored A1 sequence (modules 2–8, appended after the already-seeded "En el café" at order 1). Gamification/mastery-map remains out of scope (a later slice). Rebanada 3 (gender-with-correction) builds on this.

**Tech Stack:** FastAPI, SQLAlchemy async, Postgres, Alembic, pytest. No new dependencies. No migration (PR-A's schema already supports everything).

---

## Design decisions (settled — read before implementing)

1. **Advancement is forward-only and lives in `submit_review`.** Mastery only changes when a recall review updates a card's state/interval; that's the single trigger. The pronunciation-maintenance channel (`review-batch`) deliberately freezes state, so it never advances — correct.
2. **No-op guard:** the gate does nothing unless the just-reviewed card's `vocab_item_id` is in the active module's `module_vocab`. This keeps `submit_review` cheap for off-module reviews (two indexed lookups, no progress recompute).
3. **Mastery condition:** `module_progress` → `mastered / total ≥ module.mastery_threshold` (0.85). `total == 0` → never advances.
4. **Last module:** if there is no module with a greater `sequence_order` in the user's language, the pointer stays (the user keeps practicing the final module). No completion table in this slice.
5. **Module ordering:** "En el café" stays at `sequence_order = 1` (already seeded in prod). PR-B appends orders 2–8. We do NOT reorder an in-prod module.
6. **Idempotent re-seed safety:** `load_modules` is extended to REPLACE a module's vocab links on conflict (delete existing `module_vocab` rows for that module, then re-insert). Today it only adds links, so editing/reordering a module's vocab list would leave stale links. Deleting links never orphans `UserCard`s (those reference `vocab_items` directly).

---

## File Structure

**Backend (modify):**
- `backend/src/klara/curriculum/modules.py` — add `advance_module_if_mastered`; make `load_modules` replace vocab links on re-seed.
- `backend/src/klara/routers/srs.py` — call the gate in `submit_review`.
- `backend/src/klara/scripts/load_de_modules.py` — append modules 2–8 to `MODULES`.
- `backend/tests/test_modules.py` — tests for the gate + the link-replace + the full seed.

No schema/migration changes. No frontend changes (the Home panel already shows the active module + progress; advancement just changes which module it shows).

---

## Task 1: `load_modules` replaces vocab links on re-seed

**Files:**
- Modify: `backend/src/klara/curriculum/modules.py`
- Test: `backend/tests/test_modules.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_modules.py`:

```python
@pytest.mark.asyncio
async def test_load_modules_replaces_vocab_links_on_reseed(db_session):
    # First seed: module has {Apfel, Birne}.
    spec_v1 = [{
        "sequence_order": 1, "title": "Obst", "cefr_level": "A1",
        "can_dos": ["x"], "grammatical_focus": ["y"],
        "vocab": [
            {"lemma": "Apfel", "pos": "noun", "gender": "der", "translations": {"es": "manzana"}},
            {"lemma": "Birne", "pos": "noun", "gender": "die", "translations": {"es": "pera"}},
        ],
    }]
    await load_modules(db_session, language="modt9", modules=spec_v1)
    await db_session.commit()
    # Re-seed same module with a DIFFERENT vocab set {Apfel, Traube} — Birne dropped.
    spec_v2 = [{
        "sequence_order": 1, "title": "Obst", "cefr_level": "A1",
        "can_dos": ["x"], "grammatical_focus": ["y"],
        "vocab": [
            {"lemma": "Apfel", "pos": "noun", "gender": "der", "translations": {"es": "manzana"}},
            {"lemma": "Traube", "pos": "noun", "gender": "die", "translations": {"es": "uva"}},
        ],
    }]
    await load_modules(db_session, language="modt9", modules=spec_v2)
    await db_session.commit()

    from sqlalchemy import select as _select

    from klara.models import Module
    m = (
        await db_session.execute(
            _select(Module).where(Module.language == "modt9", Module.sequence_order == 1)
        )
    ).scalar_one()
    # Links reflect ONLY the v2 set — no stale Birne link.
    assert {v.lemma for v in m.vocab_items} == {"Apfel", "Traube"}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "replaces_vocab_links"`
Expected: FAIL — assertion shows `{"Apfel", "Birne", "Traube"}` (stale Birne link remains).

- [ ] **Step 3: Implement**

In `backend/src/klara/curriculum/modules.py`, add `delete` to the sqlalchemy import:

```python
from sqlalchemy import delete, select
```

In `load_modules`, immediately after `module_id = (await db.execute(mod_stmt)).scalar_one()` and BEFORE the `for w in spec["vocab"]:` loop, clear existing links so the seed is a true replace:

```python
        # Replace the module's vocab links (idempotent re-seed must not leave
        # stale links when the curated list changes). Safe: UserCards reference
        # vocab_items directly, not these association rows.
        await db.execute(delete(module_vocab).where(module_vocab.c.module_id == module_id))
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "replaces_vocab_links"`
Expected: PASS. Also run `uv run pytest tests/test_modules.py -q` — all module tests still pass (the existing idempotency test re-seeds identical data, so replacing then re-adding the same links is a no-op net effect).

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/curriculum/modules.py backend/tests/test_modules.py
git commit -m "feat(curriculum): load_modules replaces vocab links on re-seed"
```

---

## Task 2: `advance_module_if_mastered` helper

**Files:**
- Modify: `backend/src/klara/curriculum/modules.py`
- Test: `backend/tests/test_modules.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_modules.py`:

```python
from klara.curriculum.modules import advance_module_if_mastered


async def _mastered_card(db, user_id, vocab_item_id):
    db.add(
        UserCard(
            id=uuid.uuid4(), user_id=user_id, vocab_item_id=vocab_item_id,
            state=CardState.REVIEWING, interval_days=30.0,
        )
    )


@pytest.mark.asyncio
async def test_advance_moves_pointer_when_module_mastered(db_session):
    v1 = await _vocab(db_session, lemma="Tag", language="modtA")
    v2 = await _vocab(db_session, lemma="Nacht", language="modtA")
    m1 = await _module(db_session, language="modtA", order=1, title="Uno", vocab=[v1, v2])
    m2 = await _module(db_session, language="modtA", order=2, title="Dos", vocab=[v1])
    u = await _user(db_session)
    u.target_language = "modtA"
    u.current_module_id = m1.id
    # Both m1 words mastered → 2/2 ≥ 0.85.
    await _mastered_card(db_session, u.id, v1.id)
    await _mastered_card(db_session, u.id, v2.id)
    await db_session.commit()

    advanced = await advance_module_if_mastered(db_session, user=u, reviewed_vocab_item_id=v1.id)
    assert advanced is True
    assert u.current_module_id == m2.id


@pytest.mark.asyncio
async def test_advance_noop_when_reviewed_card_not_in_active_module(db_session):
    v_in = await _vocab(db_session, lemma="Haus", language="modtB")
    v_out = await _vocab(db_session, lemma="Auto", language="modtB")
    m1 = await _module(db_session, language="modtB", order=1, title="Uno", vocab=[v_in])
    await _module(db_session, language="modtB", order=2, title="Dos", vocab=[v_in])
    u = await _user(db_session)
    u.target_language = "modtB"
    u.current_module_id = m1.id
    await _mastered_card(db_session, u.id, v_in.id)  # module IS mastered (1/1)
    await db_session.commit()

    # Reviewed an OFF-module card → no-op even though the module is mastered.
    advanced = await advance_module_if_mastered(
        db_session, user=u, reviewed_vocab_item_id=v_out.id
    )
    assert advanced is False
    assert u.current_module_id == m1.id


@pytest.mark.asyncio
async def test_advance_noop_when_not_yet_mastered(db_session):
    v1 = await _vocab(db_session, lemma="Brot", language="modtC")
    v2 = await _vocab(db_session, lemma="Milch", language="modtC")
    m1 = await _module(db_session, language="modtC", order=1, title="Uno", vocab=[v1, v2])
    await _module(db_session, language="modtC", order=2, title="Dos", vocab=[v1])
    u = await _user(db_session)
    u.target_language = "modtC"
    u.current_module_id = m1.id
    await _mastered_card(db_session, u.id, v1.id)  # only 1/2 mastered → 0.5 < 0.85
    db_session.add(UserCard(id=uuid.uuid4(), user_id=u.id, vocab_item_id=v2.id, state=CardState.NEW))
    await db_session.commit()

    advanced = await advance_module_if_mastered(db_session, user=u, reviewed_vocab_item_id=v1.id)
    assert advanced is False
    assert u.current_module_id == m1.id


@pytest.mark.asyncio
async def test_advance_noop_on_last_module(db_session):
    v1 = await _vocab(db_session, lemma="Stadt", language="modtD")
    m1 = await _module(db_session, language="modtD", order=1, title="Único", vocab=[v1])
    u = await _user(db_session)
    u.target_language = "modtD"
    u.current_module_id = m1.id
    await _mastered_card(db_session, u.id, v1.id)  # mastered, but no next module
    await db_session.commit()

    advanced = await advance_module_if_mastered(db_session, user=u, reviewed_vocab_item_id=v1.id)
    assert advanced is False
    assert u.current_module_id == m1.id  # stays on the last module
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "advance"`
Expected: FAIL — `cannot import name 'advance_module_if_mastered'`.

- [ ] **Step 3: Implement**

In `backend/src/klara/curriculum/modules.py`, add the import of `module_progress` (from the competence module — no circular import: `competence` does not import `modules`):

```python
from klara.curriculum.competence import module_progress
```

Append the helper:

```python
async def advance_module_if_mastered(
    db: AsyncSession, *, user: User, reviewed_vocab_item_id: UUID
) -> bool:
    """Forward-only module advancement, called from submit_review after a review
    changes a card's state. No-op unless the reviewed card belongs to the active
    module AND that module's mastery ≥ its threshold. Returns True if the pointer
    advanced. Caller commits."""
    if user.current_module_id is None:
        return False
    module = await db.get(Module, user.current_module_id)
    if module is None or module.language != user.target_language:
        return False
    # No-op guard: only react to reviews of cards in the active module.
    in_module = (
        await db.execute(
            select(module_vocab.c.vocab_item_id).where(
                module_vocab.c.module_id == module.id,
                module_vocab.c.vocab_item_id == reviewed_vocab_item_id,
            )
        )
    ).first()
    if in_module is None:
        return False
    _, mastered, total = await module_progress(db, user_id=user.id, module_id=module.id)
    if total == 0 or mastered / total < module.mastery_threshold:
        return False
    nxt = (
        await db.execute(
            select(Module)
            .where(
                Module.language == user.target_language,
                Module.sequence_order > module.sequence_order,
            )
            .order_by(Module.sequence_order.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if nxt is None:
        return False  # last module — stay
    user.current_module_id = nxt.id
    await db.flush()
    return True
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "advance"`
Expected: 4 PASS. Then `uv run ruff check src/klara/curriculum/modules.py` (clean — `module_progress` import is used).

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/curriculum/modules.py backend/tests/test_modules.py
git commit -m "feat(curriculum): advance_module_if_mastered (forward-only gate)"
```

---

## Task 3: Wire the gate into `submit_review`

**Files:**
- Modify: `backend/src/klara/routers/srs.py`
- Test: `backend/tests/test_modules.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_modules.py`:

```python
@pytest.mark.asyncio
async def test_submit_review_advances_module_on_mastery(db_session):
    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    # Active module m1 with one word; mastering it should advance to m2.
    v = await _vocab(db_session, lemma="Wort", language="modtE")
    m1 = await _module(db_session, language="modtE", order=1, title="Uno", vocab=[v])
    m2 = await _module(db_session, language="modtE", order=2, title="Dos", vocab=[v])
    u = await _user(db_session)
    u.target_language = "modtE"
    u.current_module_id = m1.id
    # A card already near mastery (REVIEWING, interval 20) so one GOOD pushes it ≥21d.
    card = UserCard(
        id=uuid.uuid4(), user_id=u.id, vocab_item_id=v.id,
        state=CardState.REVIEWING, interval_days=20.0, ease=2.5, repetitions=3,
    )
    db_session.add(card)
    await db_session.commit()

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(f"/api/v1/srs/cards/{card.id}/review", json={"rating": "good"})
    assert resp.status_code == 200, resp.text
    # GOOD on a 20d REVIEWING card → interval *= ease (≈50d) ≥ 21 → mastered → advance.
    reloaded = await db_session.get(type(u), u.id)
    assert reloaded.current_module_id == m2.id
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "submit_review_advances"`
Expected: FAIL — pointer still `m1` (gate not wired).

- [ ] **Step 3: Implement**

In `backend/src/klara/routers/srs.py`, add the import:

```python
from klara.curriculum.modules import advance_module_if_mastered
```

In `submit_review`, after the card fields are updated and the `review` is added, BEFORE `await db.commit()`, call the gate (the card's vocab drives it). The existing tail is:

```python
    db.add(review)
    await db.commit()
    await db.refresh(review)
```

Change to:

```python
    db.add(review)
    await advance_module_if_mastered(db, user=user, reviewed_vocab_item_id=card.vocab_item_id)
    await db.commit()
    await db.refresh(review)
```

(The gate flushes the pointer change if it advances; the existing commit persists it atomically with the review.)

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "submit_review_advances"`
Expected: PASS. Then `uv run pytest -q` (FULL suite — existing SRS/review tests must stay green; the gate is a no-op for users with no active module or off-module cards). Then `uv run ruff check src/klara/routers/srs.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/routers/srs.py backend/tests/test_modules.py
git commit -m "feat(srs): advance the curriculum module when its vocab is mastered"
```

---

## Task 4: Author the A1 module sequence (orders 2–8)

**Files:**
- Modify: `backend/src/klara/scripts/load_de_modules.py`
- Test: `backend/tests/test_modules.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_modules.py`:

```python
def test_de_module_sequence_is_well_formed():
    from klara.scripts.load_de_modules import MODULES

    # 8 contiguous A1 modules, unique titles, each with can-dos + focus + vocab.
    assert len(MODULES) == 8
    orders = sorted(m["sequence_order"] for m in MODULES)
    assert orders == [1, 2, 3, 4, 5, 6, 7, 8]
    assert len({m["title"] for m in MODULES}) == 8
    for m in MODULES:
        assert m["cefr_level"] == "A1"
        assert m["can_dos"] and m["grammatical_focus"] and m["vocab"]
        for w in m["vocab"]:
            assert w["lemma"] and w["pos"] in {"noun", "verb", "adjective", "adverb"}
            # Every German noun must carry a gender (der/die/das).
            if w["pos"] == "noun":
                assert w.get("gender") in {"der", "die", "das"}, (m["title"], w["lemma"])
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "module_sequence_is_well_formed"`
Expected: FAIL — `len(MODULES) == 1` (only "En el café" so far).

- [ ] **Step 3: Implement — replace `MODULES` in `load_de_modules.py`**

Replace the `MODULES` list in `backend/src/klara/scripts/load_de_modules.py` with the full A1 sequence below. Keep "En el café" as order 1 (unchanged from PR-A). Genders verified against standard German.

```python
MODULES: list[dict] = [
    {
        "sequence_order": 1,
        "title": "En el café",
        "cefr_level": "A1",
        "can_dos": ["puedo pedir una bebida o un dulce en un café"],
        "grammatical_focus": ["género de sustantivos de comida y bebida (der/die/das)"],
        "vocab": [
            {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translations": {"es": "café"}},
            {"lemma": "Tee", "pos": "noun", "gender": "der", "translations": {"es": "té"}},
            {"lemma": "Wasser", "pos": "noun", "gender": "das", "translations": {"es": "agua"}},
            {"lemma": "Milch", "pos": "noun", "gender": "die", "translations": {"es": "leche"}},
            {"lemma": "Tasse", "pos": "noun", "gender": "die", "translations": {"es": "taza"}},
            {"lemma": "Kuchen", "pos": "noun", "gender": "der", "translations": {"es": "pastel"}},
            {"lemma": "Brot", "pos": "noun", "gender": "das", "translations": {"es": "pan"}},
            {"lemma": "Zucker", "pos": "noun", "gender": "der", "translations": {"es": "azúcar"}},
            {"lemma": "bestellen", "pos": "verb", "translations": {"es": "pedir/ordenar"}},
            {"lemma": "trinken", "pos": "verb", "translations": {"es": "beber"}},
        ],
    },
    {
        "sequence_order": 2,
        "title": "Saludos y presentarse",
        "cefr_level": "A1",
        "can_dos": ["puedo saludar y despedirme", "puedo decir mi nombre y de dónde soy"],
        "grammatical_focus": ["verbos sein y heißen", "pronombres ich/du/Sie"],
        "vocab": [
            {"lemma": "Name", "pos": "noun", "gender": "der", "translations": {"es": "nombre"}},
            {"lemma": "Sprache", "pos": "noun", "gender": "die", "translations": {"es": "idioma"}},
            {"lemma": "Land", "pos": "noun", "gender": "das", "translations": {"es": "país"}},
            {"lemma": "Stadt", "pos": "noun", "gender": "die", "translations": {"es": "ciudad"}},
            {"lemma": "Freund", "pos": "noun", "gender": "der", "translations": {"es": "amigo"}},
            {"lemma": "heißen", "pos": "verb", "translations": {"es": "llamarse"}},
            {"lemma": "kommen", "pos": "verb", "translations": {"es": "venir"}},
            {"lemma": "wohnen", "pos": "verb", "translations": {"es": "vivir/residir"}},
            {"lemma": "sprechen", "pos": "verb", "translations": {"es": "hablar"}},
        ],
    },
    {
        "sequence_order": 3,
        "title": "La familia",
        "cefr_level": "A1",
        "can_dos": ["puedo hablar de mi familia", "puedo decir quién es quién"],
        "grammatical_focus": ["género de los miembros de la familia", "posesivos mein/dein"],
        "vocab": [
            {"lemma": "Vater", "pos": "noun", "gender": "der", "translations": {"es": "padre"}},
            {"lemma": "Mutter", "pos": "noun", "gender": "die", "translations": {"es": "madre"}},
            {"lemma": "Kind", "pos": "noun", "gender": "das", "translations": {"es": "niño/a"}},
            {"lemma": "Bruder", "pos": "noun", "gender": "der", "translations": {"es": "hermano"}},
            {"lemma": "Schwester", "pos": "noun", "gender": "die", "translations": {"es": "hermana"}},
            {"lemma": "Familie", "pos": "noun", "gender": "die", "translations": {"es": "familia"}},
            {"lemma": "Sohn", "pos": "noun", "gender": "der", "translations": {"es": "hijo"}},
            {"lemma": "Tochter", "pos": "noun", "gender": "die", "translations": {"es": "hija"}},
        ],
    },
    {
        "sequence_order": 4,
        "title": "Números y la hora",
        "cefr_level": "A1",
        "can_dos": ["puedo contar y usar números", "puedo preguntar y decir la hora"],
        "grammatical_focus": ["números cardinales", "decir la hora (Wie spät ist es?)"],
        "vocab": [
            {"lemma": "Uhr", "pos": "noun", "gender": "die", "translations": {"es": "reloj/hora"}},
            {"lemma": "Stunde", "pos": "noun", "gender": "die", "translations": {"es": "hora"}},
            {"lemma": "Minute", "pos": "noun", "gender": "die", "translations": {"es": "minuto"}},
            {"lemma": "Tag", "pos": "noun", "gender": "der", "translations": {"es": "día"}},
            {"lemma": "Woche", "pos": "noun", "gender": "die", "translations": {"es": "semana"}},
            {"lemma": "Monat", "pos": "noun", "gender": "der", "translations": {"es": "mes"}},
            {"lemma": "Jahr", "pos": "noun", "gender": "das", "translations": {"es": "año"}},
            {"lemma": "Zahl", "pos": "noun", "gender": "die", "translations": {"es": "número"}},
        ],
    },
    {
        "sequence_order": 5,
        "title": "De compras",
        "cefr_level": "A1",
        "can_dos": ["puedo comprar comida y cosas básicas", "puedo preguntar el precio"],
        "grammatical_focus": ["género de productos comunes", "plural de sustantivos"],
        "vocab": [
            {"lemma": "Markt", "pos": "noun", "gender": "der", "translations": {"es": "mercado"}},
            {"lemma": "Geschäft", "pos": "noun", "gender": "das", "translations": {"es": "tienda"}},
            {"lemma": "Tasche", "pos": "noun", "gender": "die", "translations": {"es": "bolsa"}},
            {"lemma": "Geld", "pos": "noun", "gender": "das", "translations": {"es": "dinero"}},
            {"lemma": "Preis", "pos": "noun", "gender": "der", "translations": {"es": "precio"}},
            {"lemma": "Apfel", "pos": "noun", "gender": "der", "translations": {"es": "manzana"}},
            {"lemma": "kaufen", "pos": "verb", "translations": {"es": "comprar"}},
            {"lemma": "bezahlen", "pos": "verb", "translations": {"es": "pagar"}},
        ],
    },
    {
        "sequence_order": 6,
        "title": "La casa",
        "cefr_level": "A1",
        "can_dos": ["puedo nombrar las habitaciones de la casa", "puedo decir dónde están las cosas"],
        "grammatical_focus": ["género de objetos del hogar", "preposiciones de lugar (in/auf/unter)"],
        "vocab": [
            {"lemma": "Haus", "pos": "noun", "gender": "das", "translations": {"es": "casa"}},
            {"lemma": "Wohnung", "pos": "noun", "gender": "die", "translations": {"es": "piso/apartamento"}},
            {"lemma": "Zimmer", "pos": "noun", "gender": "das", "translations": {"es": "habitación"}},
            {"lemma": "Küche", "pos": "noun", "gender": "die", "translations": {"es": "cocina"}},
            {"lemma": "Tisch", "pos": "noun", "gender": "der", "translations": {"es": "mesa"}},
            {"lemma": "Stuhl", "pos": "noun", "gender": "der", "translations": {"es": "silla"}},
            {"lemma": "Bett", "pos": "noun", "gender": "das", "translations": {"es": "cama"}},
            {"lemma": "Tür", "pos": "noun", "gender": "die", "translations": {"es": "puerta"}},
            {"lemma": "Fenster", "pos": "noun", "gender": "das", "translations": {"es": "ventana"}},
        ],
    },
    {
        "sequence_order": 7,
        "title": "La rutina diaria",
        "cefr_level": "A1",
        "can_dos": ["puedo describir mi rutina diaria", "puedo decir qué hago cada día"],
        "grammatical_focus": ["verbos separables (aufstehen)", "partes del día"],
        "vocab": [
            {"lemma": "Morgen", "pos": "noun", "gender": "der", "translations": {"es": "mañana"}},
            {"lemma": "Abend", "pos": "noun", "gender": "der", "translations": {"es": "tarde/noche"}},
            {"lemma": "Nacht", "pos": "noun", "gender": "die", "translations": {"es": "noche"}},
            {"lemma": "aufstehen", "pos": "verb", "translations": {"es": "levantarse"}},
            {"lemma": "frühstücken", "pos": "verb", "translations": {"es": "desayunar"}},
            {"lemma": "arbeiten", "pos": "verb", "translations": {"es": "trabajar"}},
            {"lemma": "schlafen", "pos": "verb", "translations": {"es": "dormir"}},
            {"lemma": "essen", "pos": "verb", "translations": {"es": "comer"}},
        ],
    },
    {
        "sequence_order": 8,
        "title": "Moverse por la ciudad",
        "cefr_level": "A1",
        "can_dos": ["puedo moverme por la ciudad", "puedo preguntar cómo llegar a un lugar"],
        "grammatical_focus": ["género de transportes y lugares", "dativo con mit (mit dem Bus)"],
        "vocab": [
            {"lemma": "Bus", "pos": "noun", "gender": "der", "translations": {"es": "autobús"}},
            {"lemma": "Bahn", "pos": "noun", "gender": "die", "translations": {"es": "tren/tranvía"}},
            {"lemma": "Auto", "pos": "noun", "gender": "das", "translations": {"es": "coche"}},
            {"lemma": "Straße", "pos": "noun", "gender": "die", "translations": {"es": "calle"}},
            {"lemma": "Bahnhof", "pos": "noun", "gender": "der", "translations": {"es": "estación"}},
            {"lemma": "Weg", "pos": "noun", "gender": "der", "translations": {"es": "camino"}},
            {"lemma": "Fahrrad", "pos": "noun", "gender": "das", "translations": {"es": "bicicleta"}},
            {"lemma": "fahren", "pos": "verb", "translations": {"es": "ir/conducir"}},
        ],
    },
]
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "module_sequence_is_well_formed"`
Expected: PASS. Then `uv run ruff check src/klara/scripts/load_de_modules.py` and `uv run ruff format --check src/klara/scripts/load_de_modules.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/scripts/load_de_modules.py backend/tests/test_modules.py
git commit -m "feat(curriculum): author the German A1 module sequence (8 modules)"
```

---

## Task 5: Full verification

- [ ] **Step 1: Backend — tests, lint, format**

Run (from `backend/`):
```bash
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
```
Expected: all pass; ruff clean; format clean. Fix and re-run if needed.

- [ ] **Step 2: Migration round-trip (no schema change, but confirm)**

Run (from `backend/`): `uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head`
Expected: success (PR-B adds no migration; this just confirms nothing drifted).

- [ ] **Step 3: Commit any fixups** (skip if none).

```bash
git add -A && git commit -m "chore(curriculum): fixups from full verification"
```

---

## Notes for the implementer

- **Test isolation:** keep using unique fake `language` codes per test (`modt9`, `modtA`–`modtE`) — `vocab_items` is not truncated between tests; `modules`/`module_vocab` are.
- **No frontend changes:** the Home panel from PR-A already renders `GET /modules/current`; advancing the pointer just changes which module/progress it returns.
- **Deploy:** after merge, re-run `uv run python -m klara.scripts.load_de_modules` in prod to seed modules 2–8 (it's idempotent; module 1 stays, 2–8 are added, and the link-replace keeps it clean on reruns).
- **Out of scope (later slice):** gamification / mastery map UI; Rebanada 3 (gender-with-correction + Wiktionary oracle) builds on this foundation.
