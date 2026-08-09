"""Catálogo canónico del Perfil de Aprendizaje (F1.5) — GENERADO.

Fuente: el paquete de diseño «Onboarding v5», extraído mecánicamente de su
data file para que backend, frontend y diseño no puedan divergir por un typo.
NO editar a mano: cambiar el cuestionario es cambiar la spec y regenerar.

El valor guardado es el string en español: es un ID estable e independiente
del idioma de UI (un usuario alemán y uno venezolano quedan comparables).
La UI lo traduce con claves i18n; nunca guarda la traducción.
"""

from typing import Literal

Control = Literal["radio", "check", "triage", "chips"]

#: question_id -> opciones válidas, en orden de pantalla.
OPTIONS: dict[str, tuple[str, ...]] = {
    "hist_exito": (
        "Rompiendo algo hasta que funcionó",
        "Copiando a alguien que ya sabía",
        "Un curso con fechas y entregas",
        "Leyendo primero, probando después",
        "Explicándoselo a otro",
        "Un rato corto, todos los días",
        "Otra cosa",
    ),
    "hist_abandono": (
        "Se puso aburrido",
        "Perdí el hilo tras faltar unos días",
        "Era demasiado largo",
        "No veía para qué me servía",
        "Se puso difícil de golpe",
        "Me quedé sin tiempo",
        "Otra cosa",
    ),
    "hist_metodos": (
        "Fichas de repaso",
        "Videos largos",
        "Cursos con fechas",
        "Apps de idiomas",
        "Leer libros o manuales",
        "Practicar con alguien",
    ),
    "ses_duracion": (
        "3 minutos",
        "10 minutos",
        "20 minutos o más",
        "Depende del tema",
    ),
    "ses_lugar": (
        "En casa",
        "En transporte o en la calle",
        "En pausas del trabajo",
    ),
    "ses_propuesta": (
        "Que Klara proponga una sola cosa",
        "Un menú corto para elegir",
        "Según el día",
    ),
    "entrada_arranque": (
        "Un ejemplo concreto, la teoría después",
        "La teoría mínima primero",
        "Una historia que lo use",
        "Haciéndolo directamente",
    ),
    "entrada_interes": (
        "Que me sirva ya para algo",
        "Que me dé curiosidad por sí mismo",
        "Que me rete",
        "Depende del tema",
    ),
    "entrada_reto": (
        "Fácil, y que suba",
        "Rétame de una vez",
        "Que Klara calibre sola",
    ),
    "entrada_audio": (
        "Me fija las cosas",
        "Acompaña, pero no es lo central",
        "Me dispersa",
    ),
    "entrada_hablar": (
        "Me fija las cosas",
        "A veces",
        "No me aporta",
    ),
    "fija_fichas": (
        "Término y significado",
        "Un ejemplo y su concepto",
        "Completar la frase que falta",
        "Las fichas no me funcionan",
    ),
    "fija_feynman": (
        "Es mi mejor prueba",
        "Me sirve a veces",
        "Me incomoda, pero quiero intentarlo",
        "No es para mí",
    ),
    "fija_repeticion": (
        "Me lo fija",
        "Me aburre y abandono",
        "Depende: repetir poco, variar el resto",
    ),
    "fija_prueba": (
        "Explicarlo sin apuntes",
        "Usarlo en algo real",
        "Aprobar un quiz",
        "Que no se me caiga en el repaso",
    ),
    "error_correccion": (
        "Directa y al momento",
        "Al final de la sesión",
        "Suave y con contexto",
    ),
    "error_atasco": (
        "Explícamelo distinto",
        "Dame un ejemplo concreto",
        "Sigue, y vuelve después",
    ),
    "error_pista": (
        "Déjame pelear un rato antes de la pista",
        "Pista temprana, no me dejes trancado",
        "Depende del día",
    ),
    "error_memoria": (
        "Me sirve",
        "Me da igual",
        "No lo quiero",
    ),
    "ritmo_deadline": (
        "Me activa",
        "Me paraliza",
        "Depende del tema",
    ),
    "ritmo_abandono": (
        "Sesiones largas",
        "Mucha teoría seguida",
        "No ver para qué sirve",
        "Perder el hilo tras faltar unos días",
        "Otra cosa",
    ),
    "ritmo_regreso": (
        "Muéstrame dónde iba",
        "Un repaso corto antes de seguir",
        "Sigue como si nada",
    ),
    "libre": (
        "Estudio de noche",
        "Poco tiempo entre semana",
        "Casi siempre sin audio",
        "Me distraigo fácil",
        "Odio los videos largos",
        "Prefiero leer que escuchar",
        "Trabajo mejor con presión",
        "Aprendo en un idioma que no es el mío",
        "Nada especial",
    ),
}

#: question_id -> tipo de control (decide la cardinalidad válida).
CONTROLS: dict[str, Control] = {
    "hist_exito": "radio",
    "hist_abandono": "radio",
    "hist_metodos": "triage",
    "ses_duracion": "radio",
    "ses_lugar": "check",
    "ses_propuesta": "radio",
    "entrada_arranque": "radio",
    "entrada_interes": "radio",
    "entrada_reto": "radio",
    "entrada_audio": "radio",
    "entrada_hablar": "radio",
    "fija_fichas": "check",
    "fija_feynman": "radio",
    "fija_repeticion": "radio",
    "fija_prueba": "check",
    "error_correccion": "radio",
    "error_atasco": "radio",
    "error_pista": "radio",
    "error_memoria": "radio",
    "ritmo_deadline": "radio",
    "ritmo_abandono": "check",
    "ritmo_regreso": "radio",
    "libre": "chips",
}

#: question_id -> la opción de negación, que no coexiste con ninguna otra.
EXCLUSIVE: dict[str, str] = {
    "fija_fichas": "Las fichas no me funcionan",
    "libre": "Nada especial",
}

#: question_id -> (opción que la habilita, clave de texto, largo máx).
CONDITIONAL_TEXT: dict[str, tuple[str, str, int]] = {
    "hist_exito": ("Otra cosa", "hist_exito_otra", 200),
    "hist_abandono": ("Otra cosa", "hist_abandono_otra", 200),
    "ritmo_abandono": ("Otra cosa", "ritmo_abandono_otra", 200),
}

#: clave de escape libre de la nube de chips.
FREE_TEXT: dict[str, int] = {"libre_texto": 1000}

#: los métodos del triage y sus veredictos posibles.
TRIAGE_METHODS: dict[str, tuple[str, ...]] = {
    "hist_metodos": (
        "Fichas de repaso",
        "Videos largos",
        "Cursos con fechas",
        "Apps de idiomas",
        "Leer libros o manuales",
        "Practicar con alguien",
    ),
}

TRIAGE_VERDICTS: tuple[str, ...] = ("sirve", "no")

#: las 8 que deciden el estado «Completo» — NO son las 23 (D-A, sin guilt).
CONSUMPTION: tuple[str, ...] = (
    "ses_duracion",
    "ses_lugar",
    "entrada_interes",
    "entrada_reto",
    "fija_fichas",
    "error_correccion",
    "error_atasco",
    "error_pista",
)

#: tope duro por pregunta; por encima es ruido, no señal.
TIMING_CAP_MS = 300_000
