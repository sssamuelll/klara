"""Síntesis del Perfil de Aprendizaje (F1.5).

`facts` y `synthesis` son derivados de `answers` y salen del mismo paso, así
que comparten una sola marca de frescura: `derived_for_version`.

La mitad de los facts NO necesita LLM: el paquete de diseño volvió enumerables
los textos libres (triage y chips), así que `metodo_sirve`, `metodo_no_sirve` y
`restriccion` salen de las opciones marcadas. El LLM queda para la prosa y para
los pocos átomos que solo viven en texto libre.

Procedencia (regla del prompt): lo anclado en conducta reportada va primero;
la autoevaluación va después de una línea en blanco, y la UI la pinta al margen.
La literatura metacognitiva dice que el segundo tipo es el juicio menos
calibrado — la síntesis no lo presenta como hecho.
"""

from __future__ import annotations

import json
from uuid import UUID

import structlog

from klara.db import get_sessionmaker
from klara.llm import LLMClient, Message
from klara.models import LearnerProfile

log = structlog.get_logger(__name__)

#: allow-list cerrada de claves de facts (corrección de la enmienda): si el
#: LLM inventa una clave, el servidor la descarta — el JSONB debe seguir
#: consultable a los tres meses.
FACT_KEYS = (
    "aprendio_bien_como",
    "abandono_por",
    "metodo_sirve",
    "metodo_no_sirve",
    "dominio_previo",
    "restriccion",
    "motivacion",
    "evitar",
)

#: `Nada especial` es la negación de `libre`, no una restricción.
_LIBRE_NEGACION = "Nada especial"
_OTRA = "Otra cosa"


def filter_facts(raw: dict) -> dict:
    """Mantiene solo las claves de la allow-list; descarta el resto."""
    return {k: v for k, v in raw.items() if k in FACT_KEYS}


def facts_from_answers(answers: dict) -> dict:
    """Deriva los facts enumerables de las opciones marcadas, sin LLM."""
    facts: dict = {}

    triage = answers.get("hist_metodos")
    if isinstance(triage, dict):
        sirve = [m for m, v in triage.items() if v == "sirve"]
        no = [m for m, v in triage.items() if v == "no"]
        if sirve:
            facts["metodo_sirve"] = sirve
        if no:
            facts["metodo_no_sirve"] = no

    libre = answers.get("libre")
    if isinstance(libre, list):
        restriccion = [x for x in libre if x != _LIBRE_NEGACION]
        if restriccion:
            facts["restriccion"] = restriccion

    if "hist_exito" in answers:
        val = answers["hist_exito"]
        if val == _OTRA:
            val = answers.get("hist_exito_otra")
        if val:
            facts["aprendio_bien_como"] = val

    if "hist_abandono" in answers:
        val = answers["hist_abandono"]
        if val == _OTRA:
            val = answers.get("hist_abandono_otra")
        if val:
            facts["abandono_por"] = val

    return facts


_PROMPT = """Eres Klara. Te doy las respuestas de un usuario a un cuestionario \
sobre cómo aprende. Escribe una devolución breve, en {locale}, hablándole de tú.

Estructura EXACTA, dos bloques separados por una línea en blanco:
1) Lo anclado en lo que HIZO (su historial): afirmalo con naturalidad.
2) Lo que DICE de sí mismo (sus preferencias declaradas): márcalo como dicho \
("dices que…", "según tú…"), nunca como hecho comprobado.

Si no hay material para alguno de los dos bloques, omítelo (y con él su línea \
en blanco). Entre 4 y 8 líneas en total. Sin listas, sin títulos, sin emoji, \
sin prometer resultados. No inventes nada que no esté en las respuestas.

Devuelve SOLO un JSON: {{"prosa": "...", "facts": {{...}}}}
En `facts`, únicamente estas claves y solo si el texto libre las respalda: \
dominio_previo (lista), motivacion (string), evitar (lista). Omite las vacías.

Respuestas:
{answers}"""


async def generate_synthesis(
    llm: LLMClient, answers: dict, *, locale: str = "es"
) -> tuple[str | None, dict]:
    """Devuelve (prosa, facts). Best-effort: ante cualquier fallo devuelve
    (None, facts_deterministas) — guardar el cuestionario JAMÁS depende de esto.

    Los facts deterministas siempre ganan sobre los del LLM: salen de opciones
    marcadas, no de interpretación.
    """
    deterministic = facts_from_answers(answers)
    payload = json.dumps(
        {k: v for k, v in answers.items() if v not in (None, [], {})},
        ensure_ascii=False,
        indent=1,
    )
    try:
        res = await llm.complete(
            messages=[Message(role="user", content=_PROMPT.format(locale=locale, answers=payload))],
            max_tokens=700,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        data = json.loads(res.content)
        prosa = data.get("prosa") or None
        llm_facts = filter_facts(data.get("facts") or {})
    except Exception as exc:
        # Solo el tipo de fallo. Ni las respuestas ni el prompt entran al log:
        # son datos sensibles y esta app ya tuvo alertas de clear-text-logging.
        log.warning("learner_synthesis.failed", error=type(exc).__name__)
        return None, deterministic

    return prosa, {**llm_facts, **deterministic}


async def refresh_derived(
    *, user_id: UUID, version: int, answers: dict, llm: LLMClient, locale: str = "es"
) -> None:
    """Regenera facts+synthesis para UNA versión concreta de answers.

    Corre después de cerrar la respuesta, así que abre sesión propia. Si el
    usuario volvió a guardar mientras esto corría, la fila ya va por una
    versión mayor y el resultado se descarta: una síntesis vieja jamás se
    estampa como fresca (esa es toda la razón de `derived_for_version`).
    """
    prosa, facts = await generate_synthesis(llm, answers, locale=locale)

    async with get_sessionmaker()() as session:
        row = await session.get(LearnerProfile, user_id)
        if row is None or row.version != version:
            return  # llegó tarde: hay respuestas más nuevas
        row.synthesis = prosa
        row.facts = facts
        row.derived_for_version = version
        await session.commit()
    log.info("learner_synthesis.done", user_id=str(user_id), version=version, ok=prosa is not None)
