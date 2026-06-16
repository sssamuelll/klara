"""Lazy backfill of quiz_items + insight for stories generated before
those fields existed (or where the LLM trimmed them).

Both are persisted on the Story so re-visits are free. The Finish flow
calls into these once per (user, story); the first call pays the LLM
latency, the rest are DB lookups.
"""

from __future__ import annotations

import json
import re

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from klara.i18n import language_label
from klara.llm.base import LLMClient, Message
from klara.models import Story, VocabItem
from klara.models.enums import PartOfSpeech

log = structlog.get_logger(__name__)


_QUIZ_PROMPT = """Eres Klara, profesora de {target_label}. El estudiante terminó esta historia y necesita un quiz de 4 preguntas interleaved para fijar lo aprendido.

Historia (en {target_label}):
{story_text}

Palabras nuevas marcadas en la historia:
{lemmas}

Genera el quiz siguiendo EXACTAMENTE este orden y esquema (los 4 items, en este orden):

item 0 = mc (comprensión inferencial — ¿por qué? ¿qué piensa el personaje?)
item 1 = cloze (frase real de la historia, una palabra clave en blanco)
item 2 = shadow (frase corta de la historia para repetir)
item 3 = cloze (otra frase distinta, otra palabra en blanco)

Las claves de los items deben estar en {native_label} EXCEPTO los textos en {target_label} (frases, opciones, answers).

Devuelve SOLO este JSON, sin markdown ni texto extra:
{{
  "quiz_items": [
    {{
      "type": "mc",
      "cap": "Comprensión",
      "prompt": "pregunta en {native_label}",
      "options": ["opción A en {target_label}", "opción B", "opción C"],
      "correct": 0,
      "after": "explicación corta en {native_label} de por qué es correcta"
    }},
    {{
      "type": "cloze",
      "cap": "Vocabulario · habla",
      "sentence_pre": "principio en {target_label}",
      "sentence_post": "final en {target_label} (puede ser vacío)",
      "answer": "palabra en {target_label}",
      "en": "frase completa traducida al {native_label}",
      "hint": "pista corta en {native_label}"
    }},
    {{
      "type": "shadow",
      "cap": "Repite con Klara",
      "sentence": "frase corta en {target_label}",
      "en": "traducción al {native_label}",
      "after": "una línea en {native_label} sobre qué se aprende"
    }},
    {{
      "type": "cloze",
      "cap": "Vocabulario · habla",
      "sentence_pre": "...",
      "sentence_post": "...",
      "answer": "...",
      "en": "...",
      "hint": "..."
    }}
  ]
}}"""


_NOTE_PROMPT = """Eres Klara, profesora editorial de {target_label}. El estudiante acaba de terminar esta lección. Escribe UNA línea breve, italic, como teaser de la próxima sesión.

Historia recién leída (en {target_label}):
{story_text}

Reglas:
- UNA sola línea, máximo 18 palabras, en {native_label}.
- NO reveles una historia específica de mañana (no hay ninguna en cola). El tono es vibe-set, no spoiler.
- Referencia tonalmente el nivel y temática de la actual: si fue cotidiana, sugiere algo cotidiano; si fue corta, sugiere que la siguiente puede ser más larga.
- Tono: columnista cálida, despedida breve. Sin "te veo mañana", sin emojis, sin signos de exclamación.
- Sin firma ni "— K" al final — eso lo añade el UI.

Ejemplos del estilo (en español, para inspirarte; ajusta al idioma del estudiante):
- "Mañana, otra. Tal vez con frases más largas."
- "La que sigue puede que pase en una panadería."
- "Mañana volvemos sobre «autobús». Y conocemos a alguien nuevo."

Devuelve SOLO este JSON, sin markdown:
{{
  "body": "tu línea en {native_label}"
}}"""


_INSIGHT_PROMPT = """Eres Klara, profesora de {target_label}. El estudiante acaba de terminar esta historia. Selecciona UN aspecto lingüístico concreto que aparezca en ella y escríbele una nota al margen (NO un libro de gramática).

Historia (en {target_label}):
{story_text}

Palabras nuevas:
{lemmas}

Reglas:
- El título es breve (máx 60 caracteres) en {native_label}, e.g. "La tilde de «autobús»", "Cuándo va «se»", "El género de «mano»".
- El cuerpo es UN párrafo de 60-90 palabras en {native_label}.
- Usa ejemplos EXTRAÍDOS LITERALMENTE de la historia.
- Tono: profesora cálida, no formal. Sin "en este post veremos...". Sin viñetas. Sin emojis.
- Foco UNO solo: una tilde, un caso, una conjugación, una preposición — no panorámico.

Devuelve SOLO este JSON, sin markdown ni texto extra:
{{
  "title": "título breve en {native_label}",
  "body": "párrafo en {native_label}"
}}"""


def _story_text_for_prompt(story: Story) -> str:
    sentences = (story.content or {}).get("sentences") or []
    return "\n".join(s.get("target", "") for s in sentences if s.get("target"))


def _lemmas_for_prompt(story: Story, lemmas: list[str]) -> str:
    if not lemmas:
        return "(ninguna marcada)"
    return ", ".join(lemmas)


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object in LLM response: {text[:200]}")
    return json.loads(text[start : end + 1])


def build_gender_cloze(words: list[VocabItem], *, native_language: str) -> dict | None:
    """Deterministically build a der/die/das cloze from the first story target
    noun whose gender comes from the oracle (authoritative). Returns the quiz
    item dict, or None when no oracle-gendered noun is available (e.g. the oracle
    isn't loaded yet) — in which case the quiz is served unchanged. The correct
    article is NOT included: grading is server-side (POST /gender/attempts).

    Restricted to German: the der/die/das picker and grading contract are
    German-specific, so a non-German oracle noun (a future fr/pt oracle) must not
    surface here. v1 is German-only per the spec."""
    for w in words:
        if (
            w.language == "de"
            and w.pos == PartOfSpeech.NOUN
            and w.gender_source == "oracle"
            and w.gender in {"der", "die", "das"}
        ):
            return {
                "type": "gender_cloze",
                "cap": "gender",  # frontend localizes the caption
                "lemma": w.lemma,
                "vocab_item_id": str(w.id),
                "en": (w.translations or {}).get(native_language),
            }
    return None


async def ensure_quiz_items(
    db: AsyncSession,
    story: Story,
    llm: LLMClient,
    *,
    lemmas: list[str],
) -> list[dict] | None:
    """Return the story's quiz_items, generating + persisting them once if missing."""
    if story.quiz_items:
        return story.quiz_items

    target_label = language_label(story.target_language)
    native_label = language_label(story.native_language)
    prompt = _QUIZ_PROMPT.format(
        target_label=target_label,
        native_label=native_label,
        story_text=_story_text_for_prompt(story),
        lemmas=_lemmas_for_prompt(story, lemmas),
    )

    try:
        resp = await llm.complete(
            messages=[Message(role="user", content=prompt)],
            max_tokens=1400,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        data = _extract_json(resp.content)
        items = data.get("quiz_items")
        if not isinstance(items, list) or not items:
            log.warning("finish.quiz.bad_shape", story_id=str(story.id))
            return None
    except Exception as e:
        log.warning("finish.quiz.gen_failed", story_id=str(story.id), error=str(e))
        return None

    story.quiz_items = items
    await db.commit()
    await db.refresh(story)
    return story.quiz_items


async def ensure_klara_note(
    db: AsyncSession,
    story: Story,
    llm: LLMClient,
) -> str | None:
    """Return the Klara teaser line, generating + persisting once if missing."""
    if story.klara_note:
        return story.klara_note

    target_label = language_label(story.target_language)
    native_label = language_label(story.native_language)
    prompt = _NOTE_PROMPT.format(
        target_label=target_label,
        native_label=native_label,
        story_text=_story_text_for_prompt(story),
    )

    try:
        resp = await llm.complete(
            messages=[Message(role="user", content=prompt)],
            max_tokens=200,
            temperature=0.85,
            response_format={"type": "json_object"},
        )
        data = _extract_json(resp.content)
        body = data.get("body")
        if not isinstance(body, str):
            log.warning("finish.note.bad_shape", story_id=str(story.id))
            return None
        body = body.strip().strip("«»\"'.").strip()[:400]
        if not body:
            return None
    except Exception as e:
        log.warning("finish.note.gen_failed", story_id=str(story.id), error=str(e))
        return None

    story.klara_note = body
    await db.commit()
    await db.refresh(story)
    return body


async def ensure_insight(
    db: AsyncSession,
    story: Story,
    llm: LLMClient,
    *,
    lemmas: list[str],
) -> tuple[str, str] | None:
    """Return (title, body), generating + persisting once if missing."""
    if story.insight_title and story.insight_body:
        return story.insight_title, story.insight_body

    target_label = language_label(story.target_language)
    native_label = language_label(story.native_language)
    prompt = _INSIGHT_PROMPT.format(
        target_label=target_label,
        native_label=native_label,
        story_text=_story_text_for_prompt(story),
        lemmas=_lemmas_for_prompt(story, lemmas),
    )

    try:
        resp = await llm.complete(
            messages=[Message(role="user", content=prompt)],
            max_tokens=600,
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        data = _extract_json(resp.content)
        title = data.get("title")
        body = data.get("body")
        if not isinstance(title, str) or not isinstance(body, str):
            log.warning("finish.insight.bad_shape", story_id=str(story.id))
            return None
        title = title.strip()[:200]
        body = body.strip()[:2000]
        if not title or not body:
            return None
    except Exception as e:
        log.warning("finish.insight.gen_failed", story_id=str(story.id), error=str(e))
        return None

    story.insight_title = title
    story.insight_body = body
    await db.commit()
    await db.refresh(story)
    return title, body
