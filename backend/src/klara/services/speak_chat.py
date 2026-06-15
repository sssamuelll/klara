"""LLM reply generation for Speak turns.

Klara's continuation is conversational steering ONLY — the correction shown to
the user comes from the Azure assessment (speak_analysis), never from the LLM
(handoff integration point 3). Best-effort: any LLM failure returns None and
the caller ships the assessment without a reply; a missing reply must never
cost the user their scored turn.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog

from klara.i18n import language_label
from klara.llm.base import LLMClient, Message
from klara.llm.prompts import (
    SPEAK_SYSTEM_PROMPT,
    SPEAK_TURN_PROMPT,
    build_speak_history_block,
)

log = structlog.get_logger(__name__)

# A user is staring at the "thinking" screen — the settings-level 60s x 2
# retries budget would outlive every proxy and every user's patience.
SPEAK_LLM_TIMEOUT_SECONDS = 25.0
SPEAK_LLM_RETRIES = 0


@dataclass
class SpeakReply:
    reply_target: str
    reply_native: str
    target_word_gloss: str | None
    target_word_sentence: str | None


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


async def generate_reply(
    llm: LLMClient,
    *,
    target_language: str,
    native_language: str,
    level: str,
    focus_sound: str,
    focus_examples: list[str],
    recognized_text: str,
    history: list[dict],
    focus_clear: bool,
    target_word: str | None,
    retry_word: str | None,
) -> SpeakReply | None:
    system = SPEAK_SYSTEM_PROMPT.format(
        target_label=language_label(target_language),
        native_label=language_label(native_language),
        level=level,
        focus_sound=focus_sound,
        focus_examples=", ".join(focus_examples) or "—",
    )

    if target_word:
        verdict = "claro" if focus_clear else "turbio"
        focus_block = (
            f"El sonido «{focus_sound}» apareció (palabra objetivo: «{target_word}») "
            f"y sonó {verdict}."
        )
    else:
        focus_block = f"El sonido «{focus_sound}» no apareció en este turno."

    retry_block = (
        f"OJO: el estudiante está repitiendo solo la palabra «{retry_word}» tras una "
        "corrección — reconócelo brevemente y retoma el tema anterior."
        if retry_word
        else ""
    )

    prompt = SPEAK_TURN_PROMPT.format(
        history_block=build_speak_history_block(history),
        recognized_text=recognized_text,
        focus_block=focus_block,
        retry_block=retry_block,
    )

    try:
        resp = await llm.complete(
            messages=[
                Message(role="system", content=system),
                Message(role="user", content=prompt),
            ],
            max_tokens=500,
            temperature=0.7,
            response_format={"type": "json_object"},
            timeout_seconds=SPEAK_LLM_TIMEOUT_SECONDS,
            num_retries=SPEAK_LLM_RETRIES,
        )
        data = _extract_json(resp.content)
        reply_target = (data.get("reply_target") or "").strip()
        reply_native = (data.get("reply_native") or "").strip()
        if not reply_target:
            log.warning("speak.reply.bad_shape", content=resp.content[:200])
            return None
        # Clamp to /speak/finish's validation caps (SpeakFinishWordIn): the
        # client round-trips these verbatim, and one over-long LLM sentence
        # must not 422 the whole session hand-off later.
        gloss = (data.get("target_word_gloss") or "").strip()[:120] or None
        sentence = (data.get("target_word_sentence") or "").strip()[:200] or None
        return SpeakReply(
            reply_target=reply_target,
            reply_native=reply_native,
            target_word_gloss=gloss,
            target_word_sentence=sentence,
        )
    except Exception as e:
        log.warning("speak.reply.gen_failed", error=str(e))
        return None
