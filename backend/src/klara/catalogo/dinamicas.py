"""Lo que el backend sabe de cada dinámica (spec §3): qué modos soporta, qué
facetas ejercita por tipo de ítem, cuánto tiempo es «lento» y cuánto suele
tardar. El contenido lo generan las funciones de `generar.py`, una por dinámica.

Los planes 2 y 3 agregan `articulo`, `par-minimo` y `sombra`, y amplían las
facetas de `eleccion`."""

from dataclasses import dataclass

# Cuántos repasos entran, como mucho, en la sesión de una línea (spec §4). Lo que
# sobra queda para mañana: FSRS aguanta el atraso.
CAP_REPASOS = 25


@dataclass(frozen=True)
class Dinamica:
    nombre: str
    modos: frozenset[str]
    # tipo de ítem → facetas que ejercita
    facetas: dict[str, frozenset[str]]
    # Un acierto más lento que esto vale `hard` (catalogo/nota.py).
    ms_lento: int
    # modo → segundos típicos por actividad. Hoy suma esto para prometer minutos.
    segundos: dict[str, int]


DINAMICAS: dict[str, Dinamica] = {
    "eleccion": Dinamica(
        nombre="eleccion",
        modos=frozenset({"practicar", "comprobar"}),
        facetas={"ja:kana": frozenset({"reconocer", "oir"})},
        ms_lento=8_000,
        segundos={"practicar": 6, "comprobar": 6},
    ),
    "trazo": Dinamica(
        nombre="trazo",
        modos=frozenset({"presentar", "practicar", "comprobar"}),
        facetas={"ja:kana": frozenset({"escribir"})},
        ms_lento=30_000,
        segundos={"presentar": 20, "practicar": 25, "comprobar": 20},
    ),
    "emparejar": Dinamica(
        nombre="emparejar",
        # Solo práctica: un juego contra el reloj es mala señal para FSRS (spec §3.2).
        modos=frozenset({"practicar"}),
        facetas={"ja:kana": frozenset({"reconocer"})},
        ms_lento=45_000,
        segundos={"practicar": 45},
    ),
}

# Por ahora cada faceta se repasa con una dinámica fija (spec §3; el #129 podrá elegir).
DINAMICA_DE_REPASO: dict[tuple[str, str], str] = {
    ("ja:kana", "reconocer"): "eleccion",
    ("ja:kana", "oir"): "eleccion",
    ("ja:kana", "escribir"): "trazo",
}


def ejercita(dinamica: Dinamica, tipo: str, faceta: str) -> bool:
    return faceta in dinamica.facetas.get(tipo, frozenset())
