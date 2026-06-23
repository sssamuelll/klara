# Runbook — activate the German gender axis in production

**Owner task.** The whole gender axis (oracle der/die/das, the in-story gender
cloze, the L1-transfer "trampas de género", and the `/gender` review queue)
ships **dormant** and stays dormant until the gender oracle is loaded in prod.
This runbook is the exact sequence to turn it on.

**Why dormant:** gender is oracle-gated. A noun only gets
`gender_source = 'oracle'` when story generation's `resolve_gender` finds it in
the loaded `gender_lexicon` **at generation time** (`services/story_gen.py`).
Until the lexicon is loaded, every noun falls back to `gender_source = 'llm'`,
and every oracle-gated surface degrades to empty with **no error**:
- the in-story gender cloze is not built (`build_gender_cloze` requires oracle),
- `GET /api/v1/gender/review` returns `[]` (no weak set),
- `POST /api/v1/gender/attempts` would 404 (oracle gate).

## Preconditions

1. **Acquire the dataset (not vendored).** The gender oracle comes from
   [gambolputty/german-nouns](https://github.com/gambolputty/german-nouns)
   (CC-BY-SA 4.0; attributed in repo-root `NOTICE`). Download the nouns CSV
   separately — it is **not** in the repo. `load_de_gender` parses it via
   `parse_gender_csv`. (Optional, for R1 frequency/CEFR: a Kelly/SUBTLEX-DE
   `freq.tsv` for `load_de_lexical` — also acquired separately; **not** needed
   for gender.)
2. **SSH access** to the prod host (EC2, klara.sdar.dev) and the running backend
   container.
3. Confirm the deploy is current (the gender code is on `main` and deployed):
   B1 (#85), B2a (#86), B2b (#87) merged.

## The loaders (all idempotent upserts — re-run safe)

| Script | Arg | Self-contained? | Role |
|---|---|---|---|
| `klara.scripts.load_de_modules` | — | yes | the 8 A1 modules (the vocab "heat source") |
| `klara.scripts.load_de_gender` | `<nouns.csv>` | no | **THE GATE** — the der/die/das oracle into `gender_lexicon` |
| `klara.scripts.load_de_l1_notes` | — | yes | the 20 curated ES→DE trap notes |
| `klara.scripts.load_de_lexical` | `<freq.tsv>` | no | (optional) R1 frequency/CEFR |

## Steps (run on the prod host)

The container exec pattern (match your actual compose file names):

```sh
# from the deploy directory on the prod host
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

# 1. Modules (if not already seeded). Self-contained.
$COMPOSE exec backend python -m klara.scripts.load_de_modules

# 2. THE GATE — the gender oracle. Copy the CSV into the container first.
docker cp ./nouns.csv "$($COMPOSE ps -q backend)":/tmp/nouns.csv
$COMPOSE exec backend python -m klara.scripts.load_de_gender /tmp/nouns.csv
#   → prints "Cargadas N entradas de género (de)."

# 3. The ES→DE trap notes. Self-contained.
$COMPOSE exec backend python -m klara.scripts.load_de_l1_notes

# 4. (optional) R1 frequency/CEFR.
# docker cp ./freq.tsv "$($COMPOSE ps -q backend)":/tmp/freq.tsv
# $COMPOSE exec backend python -m klara.scripts.load_de_lexical /tmp/freq.tsv
```

Order matters only in that `load_de_gender` is the gate; modules/l1-notes can run
before or after. The loaders are idempotent (upserts), so a re-run is safe.

## Verification

1. **Lexicon loaded:**
   ```sql
   SELECT count(*) FROM gender_lexicon;            -- > 0
   ```
2. **New stories get oracle genders.** Generate a fresh story for a German
   learner (the axis only lights up for stories generated AFTER the load —
   existing stories keep the genders resolved at their own generation time, so
   they will NOT retroactively become oracle). Then:
   ```sql
   SELECT lemma, gender, gender_source
   FROM vocab_items
   WHERE language='de' AND gender_source='oracle'
   ORDER BY updated_at DESC LIMIT 10;              -- der/die/das rows present
   ```
3. **In-story cloze appears:** finish that new story → the quiz includes a
   gender_cloze for its weakest eligible noun.
4. **Review queue lights up:** after a few graded attempts,
   `GET /api/v1/gender/review` returns weak nouns; the Home "Repaso de género"
   tile → `/gender` shows cards (empty "Aquí vuelven los géneros que fallas…"
   until there are weak nouns).

## Notes

- **Existing stories do not retroactively gain oracle genders.** The gate is at
  generation time. Activation is forward-looking; the axis fills in as learners
  generate and finish new stories.
- The loader scripts print only file-derived counts (`len(rows)`), never
  session-derived data — this is deliberate (avoids the CodeQL
  `clear-text-logging` false positive; see the DSN-hardening issue #81).
- Re-running any loader is safe (idempotent upserts).
- Nothing here changes module advancement — gender never gates it.
