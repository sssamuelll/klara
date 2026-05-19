"""LLM-backed phonetic stress hints for mispronounced words.

The pronunciation scoring endpoint tells us *which* words were bad (Azure
returns per-word accuracy), but not *why*. For each bad word we ask the
LLM to render a hyphenated stress hint in the target language — capitalized
on the stressed syllable — so the UI can surface a tip like
"au-to-BÚS" or "Bä-cke-REI".

This is a separate endpoint from /pronunciation/score because:
- It only fires when there's something to hint at (avoids LLM cost on perfect reads).
- Azure scoring is sync + critical; LLM hints are async + best-effort.
- Different cache lifetimes (scores are per-recording, hints are per-word).
"""

from __future__ import annotations

import json
import re

import structlog

from klara.i18n.languages import language_label
from klara.llm.base import LLMClient, Message

log = structlog.get_logger(__name__)


_SYSTEM_PROMPT = """You are a pronunciation coach generating compact stress hints.

For each word in `words`, produce a hyphenated breakdown in {target_label}'s natural script with the STRESSED syllable in ALL CAPS.

Examples:
- Spanish "autobús" → "au-to-BÚS"
- German "Bäckerei" → "Bä-cke-REI"
- French "université" → "u-ni-ver-si-TÉ"
- English "computer" → "com-PU-ter"
- Portuguese "saudade" → "sau-DA-de"
- Japanese (use romaji): "konnichiwa" → "kon-NI-chi-wa"

Rules:
- Use the natural script of {target_label} (Japanese gets romaji as a learner aid; everything else uses native script).
- Capitalize ONLY the stressed syllable. Leave punctuation, diacritics intact.
- If a word has no clear primary stress (monosyllable, particle), return it unchanged with no hyphens.
- Do NOT explain. Do NOT add IPA. Do NOT translate.

Return STRICT JSON only: {{"hints": {{"word1": "hint1", "word2": "hint2"}}}}
Use the exact spelling of each input word as the key."""


def _extract_json(content: str) -> dict:
    """LLMs sometimes wrap JSON in fences or chatty preambles — recover the object."""
    content = content.strip()
    # Strip ```json ... ``` fences if present
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", content, re.DOTALL)
    if fence:
        content = fence.group(1).strip()
    # Find the first { ... } block
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object in LLM response: {content[:200]}")
    return json.loads(content[start : end + 1])


async def generate_phonetic_hints(
    llm: LLMClient,
    *,
    words: list[str],
    language: str,
) -> dict[str, str]:
    """Return {word: hyphenated_stress_hint} for each input word.

    Words the LLM doesn't return are silently dropped from the response —
    the caller treats this as "no hint available, just name the word".
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in words:
        w = raw.strip()
        if not w:
            continue
        key = w.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(w)
    if not cleaned:
        return {}

    target_label = language_label(language)
    system = _SYSTEM_PROMPT.format(target_label=target_label)
    user_msg = f"Words to break down: {json.dumps(cleaned, ensure_ascii=False)}"

    resp = await llm.complete(
        messages=[Message(role="system", content=system), Message(role="user", content=user_msg)],
        max_tokens=256,
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    try:
        payload = _extract_json(resp.content)
    except (ValueError, json.JSONDecodeError) as e:
        log.warning("phonetic_hints.parse_failed", error=str(e), raw=resp.content[:300])
        return {}

    raw_hints = payload.get("hints", {})
    if not isinstance(raw_hints, dict):
        log.warning("phonetic_hints.bad_shape", payload=str(payload)[:200])
        return {}

    # Map LLM keys back to original word spellings (handle case mismatch).
    by_lower = {w.lower(): w for w in cleaned}
    out: dict[str, str] = {}
    for k, v in raw_hints.items():
        if not isinstance(v, str) or not v.strip():
            continue
        orig = by_lower.get(str(k).lower())
        if orig is not None:
            out[orig] = v.strip()
    return out
