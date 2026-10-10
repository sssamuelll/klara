"""Facetas por tipo de ítem (spec §1): las únicas válidas. El cargador rechaza
cualquier otra, y también el endpoint de evidencias."""

FACETAS_POR_TIPO: dict[str, frozenset[str]] = {
    "ja:kana": frozenset({"reconocer", "oir", "escribir"}),
    "de:sustantivo": frozenset({"genero", "reconocer"}),
    "de:caso": frozenset({"aplicar"}),
    "en:contraste": frozenset({"oir", "pronunciar"}),
}

MODOS: tuple[str, ...] = ("presentar", "practicar", "comprobar")


def partes(item: str) -> tuple[str, str, str]:
    """`ja:kana:あ` → ("ja", "kana", "あ"). ValueError si no son tres partes llenas."""
    trozos = item.split(":", 2)
    if len(trozos) != 3 or not all(trozos):
        raise ValueError(f"clave de ítem inválida: {item!r}")
    return trozos[0], trozos[1], trozos[2]


def tipo_de(item: str) -> str:
    idioma, tipo, _ = partes(item)
    return f"{idioma}:{tipo}"


def idioma_de(item: str) -> str:
    return partes(item)[0]


def faceta_valida(item: str, faceta: str) -> bool:
    try:
        return faceta in FACETAS_POR_TIPO.get(tipo_de(item), frozenset())
    except ValueError:
        return False
