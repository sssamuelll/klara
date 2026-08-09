"""Perfil de Aprendizaje — esquemas HTTP (F1.5).

LearnerProfileIn valida contra el catálogo canónico (learner_catalog) en vez
de duplicar la spec: cardinalidad por control, exclusivas y textos
condicionales viven en UNA fuente, la misma que genera el frontend. El 422 es
la señal de "cliente desactualizado": el servidor no confía en la UI.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from klara.models import LearnerProfile
from klara.schemas.learner_catalog import (
    CONDITIONAL_TEXT,
    CONSUMPTION,
    CONTROLS,
    EXCLUSIVE,
    FREE_TEXT,
    OPTIONS,
    TIMING_CAP_MS,
    TRIAGE_METHODS,
    TRIAGE_VERDICTS,
)

#: claves de texto extra: no son preguntas (no viven en OPTIONS) pero entran
#: en `answers`, habilitadas por CONDITIONAL_TEXT / FREE_TEXT.
_TEXT_KEYS = frozenset(text_key for _, text_key, _ in CONDITIONAL_TEXT.values()) | frozenset(
    FREE_TEXT
)


class LearnerProfileIn(BaseModel):
    answers: dict[str, Any]
    timings: dict[str, Any]

    @model_validator(mode="after")
    def _validate_catalog(self) -> "LearnerProfileIn":
        answers = self.answers
        unknown_answers = set(answers) - (set(OPTIONS) | _TEXT_KEYS)
        # timings solo mide preguntas: las claves de texto no son preguntas.
        unknown_timings = set(self.timings) - set(OPTIONS)
        if unknown_answers or unknown_timings:
            raise ValueError(
                f"question ids desconocidos: {sorted(unknown_answers | unknown_timings)}"
            )

        for qid, value in answers.items():
            if qid not in OPTIONS:
                continue  # claves de texto: se validan abajo, contra su disparador
            control = CONTROLS[qid]
            if value is None:
                continue  # la vio y la saltó: es dato, no ausencia
            if control == "radio":
                if not isinstance(value, str) or value not in OPTIONS[qid]:
                    raise ValueError(f"{qid}: valor fuera de OPTIONS")
            elif control in ("check", "chips"):
                if not isinstance(value, list):
                    raise ValueError(f"{qid}: espera una lista de opciones")
                if len(set(value)) != len(value):
                    raise ValueError(f"{qid}: opciones duplicadas")
                if any(v not in OPTIONS[qid] for v in value):
                    raise ValueError(f"{qid}: valor fuera de OPTIONS")
                if qid in EXCLUSIVE and EXCLUSIVE[qid] in value and len(value) > 1:
                    raise ValueError(f"{qid}: la opción exclusiva no coexiste con otras")
            elif control == "triage":
                if not isinstance(value, dict):
                    raise ValueError(f"{qid}: triage espera un dict de veredictos")
                methods = TRIAGE_METHODS.get(qid, ())
                if any(m not in methods for m in value):
                    raise ValueError(f"{qid}: método de triage desconocido")
                if any(v not in TRIAGE_VERDICTS for v in value.values()):
                    raise ValueError(f"{qid}: veredicto de triage desconocido")

        for qid, (trigger, text_key, maxlen) in CONDITIONAL_TEXT.items():
            if text_key in answers:
                if answers.get(qid) != trigger:
                    raise ValueError(f"{text_key} solo es válida si {qid} == {trigger!r}")
                val = answers[text_key]
                if val is not None and (not isinstance(val, str) or len(val) > maxlen):
                    raise ValueError(f"{text_key}: máx {maxlen} caracteres")

        for key, maxlen in FREE_TEXT.items():
            if key in answers:
                val = answers[key]
                if val is not None and (not isinstance(val, str) or len(val) > maxlen):
                    raise ValueError(f"{key}: máx {maxlen} caracteres")

        # timings: entero, 0..TIMING_CAP_MS. Por encima del tope es ruido, no
        # señal; un negativo es un reloj que arrancó mal, no un dato.
        timings: dict[str, int] = {}
        for qid, raw in self.timings.items():
            try:
                n = int(raw)
            except (TypeError, ValueError):
                raise ValueError(f"timings[{qid}]: no es un entero") from None
            timings[qid] = max(0, min(n, TIMING_CAP_MS))
        self.timings = timings
        return self


class LearnerProfileOut(BaseModel):
    answers: dict[str, Any]
    timings: dict[str, Any]
    facts: dict[str, Any] | None
    synthesis: str | None
    version: int
    derived_for_version: int | None
    updated_at: datetime
    status: Literal["completo", "a_medias"]
    stale: bool

    @classmethod
    def from_row(cls, row: LearnerProfile) -> "LearnerProfileOut":
        # «Completo» se ata a las 8 de consumo, no a 23/23: contar saltos
        # convertiría la fila en un reproche (D-A, sin guilt).
        complete = all(
            row.answers.get(qid) is not None and row.answers.get(qid) != [] for qid in CONSUMPTION
        )
        return cls(
            answers=row.answers,
            timings=row.timings,
            facts=row.facts,
            synthesis=row.synthesis,
            version=row.version,
            derived_for_version=row.derived_for_version,
            updated_at=row.updated_at,
            status="completo" if complete else "a_medias",
            stale=row.derived_for_version is not None and row.derived_for_version < row.version,
        )
