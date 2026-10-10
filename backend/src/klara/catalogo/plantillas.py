"""Plantillas de lección (spec §2.1, §6): convierten los ítems de una lección en
actividades. Cada plantilla comprueba todo lo que practica; el cargador lo
verifica igual."""

from collections.abc import Callable

from klara.catalogo.modelo import Actividad


def _a(dinamica: str, modo: str, items, faceta: str) -> Actividad:
    return Actividad(dinamica=dinamica, modo=modo, items=tuple(items), faceta=faceta)


def kana(items: tuple[str, ...]) -> tuple[Actividad, ...]:
    """Una fila de kana (spec §6.1): presentar y practicar el trazo de cada uno,
    elegir (reconocer y oír), el tablero, y la prueba."""
    acts: list[Actividad] = []
    for k in items:
        acts.append(_a("trazo", "presentar", [k], "escribir"))
        acts.append(_a("trazo", "practicar", [k], "escribir"))
    acts += [_a("eleccion", "practicar", [k], "reconocer") for k in items]
    acts += [_a("eleccion", "practicar", [k], "oir") for k in reversed(items)]
    if len(items) > 1:
        acts.append(_a("emparejar", "practicar", items, "reconocer"))
    acts += [_a("trazo", "comprobar", [k], "escribir") for k in items]
    acts += [_a("eleccion", "comprobar", [k], "reconocer") for k in reversed(items)]
    acts += [_a("eleccion", "comprobar", [k], "oir") for k in items]
    return tuple(acts)


PLANTILLAS: dict[str, Callable[[tuple[str, ...]], tuple[Actividad, ...]]] = {"kana": kana}
