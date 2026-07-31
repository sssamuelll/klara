# Spec — Onboarding de Perfil de Aprendizaje (capa declarada, v1)

**Qué es:** un cuestionario dentro del app que define cómo aprende cada usuario. Klara lo usa para armar las herramientas de cada tema que se plantee. Es la capa **declarada** del Perfil de Aprendizaje (plan maestro v4, sección "El eje que ordena todo", decisión D-K).

**Dónde vive:**
1. **Primer arranque** — usuario sin perfil guardado entra al cuestionario después del login (reemplaza el rol del onboarding global actual; los pasos de idioma/nivel quedan para el flujo del curso de idioma).
2. **Perfil → fila "Cómo aprendes"** — reabre el cuestionario con las respuestas guardadas, editable siempre. Estado de la fila: `Completo · <fecha>` o `Sin llenar`.

**Forma:** una pregunta por pantalla (patrón cero-scroll de v4), con los primitives existentes de `frontend/src/onboarding/` (`ObPrompt`, `ObField`, `ObInlineSelect`, `ObNav`). Toda pregunta se puede saltar. Al final, Klara genera una síntesis y la muestra.

**Duración objetivo:** ~10 minutos. 20 preguntas en 6 bloques.

---

## Pantalla de entrada

- **H1:** `Cómo aprendes tú.`
- **Cuerpo:** `Klara arma cada tema a tu medida. Para eso necesita conocerte: veinte preguntas, unos diez minutos, sin respuestas correctas. Puedes cambiar cualquier respuesta cuando quieras, desde Perfil.`
- **Botón:** `Empezar` (7 chars)
- **Link secundario (solo si viene de primer arranque):** `Más tarde` — el perfil queda `Sin llenar`; Klara usa defaults conservadores y lo dice cuando proponga un plan.

## Navegación

- Botón avanzar: `Siguiente` — última pregunta: `Guardar mi perfil` (17 chars).
- Link por pregunta: `Saltar esta` — guarda `null`, no bloquea.
- Progreso: segmentos arriba (patrón `m3-prog`), sin porcentaje.

---

## Bloque 1 — Historial

La señal más honesta: comportamiento pasado, no autodiagnóstico.

| id | control | label | detalle |
|---|---|---|---|
| `hist_exito` | textarea | `Lo último que aprendiste bien de verdad. ¿Qué era y cómo lo hiciste?` | placeholder: `Aprendí a usar Docker viendo un proyecto real y rompiéndolo…` |
| `hist_abandono` | textarea | `Algo que intentaste aprender y dejaste. ¿Qué te sacó?` | placeholder: `Un curso de 40 horas de video. Al tercer día ya no volví…` |
| `hist_metodos` | textarea | `De apps o métodos que has usado para estudiar: ¿qué te sirvió y qué no?` | placeholder: `Las fichas me funcionan si son pocas. Los videos largos no…` |

## Bloque 2 — La sesión

| id | control | label | opciones |
|---|---|---|---|
| `ses_duracion` | radio | `¿Cuánto tiempo real sostienes al día, sin forzarte?` | `3 minutos` · `10 minutos` · `20 minutos o más` · `Depende del tema` |
| `ses_momento` | checkbox | `¿Cuándo sueles estudiar?` | `Por la mañana` · `Al mediodía` · `Por la noche` · `Sin patrón fijo` |
| `ses_lugar` | checkbox | `¿Dónde?` | `En casa` · `En transporte o en la calle` · `En pausas del trabajo` — *nota de sistema: define si el micrófono es viable por defecto* |
| `ses_propuesta` | radio | `Al abrir el app, ¿qué prefieres?` | `Que Klara proponga una sola cosa` · `Un menú corto para elegir` · `Según el día` |

## Bloque 3 — Cómo entra un tema nuevo

| id | control | label | opciones |
|---|---|---|---|
| `entrada_arranque` | radio | `Frente a un tema nuevo, ¿por dónde arrancas mejor?` | `Un ejemplo concreto, la teoría después` · `La teoría mínima primero` · `Una historia que lo use` · `Haciéndolo directamente` |
| `entrada_audio` | radio | `Escuchar la lección en voz alta:` | `Me fija las cosas` · `Acompaña, pero no es lo central` · `Me dispersa` |
| `entrada_hablar` | radio | `Decir las cosas en voz alta:` | `Me fija las cosas` · `A veces` · `No me aporta` |

## Bloque 4 — Cómo se queda

| id | control | label | opciones |
|---|---|---|---|
| `fija_fichas` | checkbox | `Fichas de repaso: ¿cuáles te funcionan?` | `Término y significado` · `Un ejemplo y su concepto` · `Completar la frase que falta` · `Las fichas no me funcionan` |
| `fija_feynman` | radio | `Explicar algo con tus palabras, sin apuntes:` | `Es mi mejor prueba` · `Me sirve a veces` · `Me incomoda, pero quiero intentarlo` · `No es para mí` |
| `fija_repeticion` | radio | `Repetir lo mismo varios días:` | `Me lo fija` · `Me aburre y abandono` · `Depende: repetir poco, variar el resto` |
| `fija_prueba` | checkbox | `¿Qué te convence de que ya lo sabes?` | `Explicarlo sin apuntes` · `Usarlo en algo real` · `Aprobar un quiz` · `Que no se me caiga en el repaso` |

## Bloque 5 — Error y ritmo

| id | control | label | opciones |
|---|---|---|---|
| `error_correccion` | radio | `Cuando te equivocas, ¿cómo quieres la corrección?` | `Directa y al momento` · `Al final de la sesión` · `Suave y con contexto` |
| `error_memoria` | radio | `Que Klara recuerde tus errores de días pasados ("igual que ayer"):` | `Me sirve` · `Me da igual` · `No lo quiero` |
| `ritmo_deadline` | radio | `Una fecha real en el calendario (una entrevista, un examen):` | `Me activa` · `Me paraliza` · `Depende del tema` |
| `ritmo_abandono` | checkbox | `¿Qué te hace abandonar un tema?` | `Sesiones largas` · `Mucha teoría seguida` · `No ver para qué sirve` · `Perder el hilo tras faltar unos días` · `Otra cosa` (+ campo de texto si se marca) |
| `ritmo_regreso` | radio | `Cuando vuelves tras varios días sin entrar:` | `Muéstrame dónde iba` · `Un repaso corto antes de seguir` · `Sigue como si nada` |

## Bloque 6 — Cierre

| id | control | label | detalle |
|---|---|---|---|
| `libre` | textarea | `Algo más que Klara deba saber de cómo aprendes tú.` | placeholder: `Lo que sea: manías, horarios, cosas que odias de otras apps…` — botón: `Guardar mi perfil` |

---

## Pantalla de síntesis

Tras guardar, Klara genera la síntesis (una llamada LLM sobre las respuestas; misma infra `litellm`) y la muestra:

- **H1:** `Así aprendes tú, según tú.`
- **Cuerpo:** la síntesis (prosa, 4-8 líneas, primera persona de Klara hacia el usuario: `Retienes hablando. Las sesiones largas te sacan…`).
- **Línea al pie:** `Klara va a afinar esto con el uso. Puedes leerlo y corregirlo cuando quieras, desde Perfil.`
- **Botones:** `Entendido` (primario) · `Corregir una respuesta` (ghost, vuelve al cuestionario).

Si la generación de síntesis falla: se guarda el cuestionario igual, la síntesis queda pendiente y la fila de Perfil dice `Respuestas guardadas · síntesis pendiente`. Sin bloquear nada.

---

## Contrato de datos

```sql
-- migración independiente del dominio Course (no espera a F3)
CREATE TABLE learner_profile (
  user_id     UUID PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
  answers     JSONB NOT NULL DEFAULT '{}',   -- {question_id: valor | [valores] | null}
  synthesis   TEXT,                          -- generada por LLM; NULL = pendiente
  version     INTEGER NOT NULL DEFAULT 1,    -- se incrementa en cada guardado
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- `GET /profile/learning` → `{answers, synthesis, version, updated_at}` (404 si nunca llenado).
- `PUT /profile/learning` → guarda `answers`, dispara regeneración de síntesis (async, best-effort).
- Versiones anteriores: se conservan en `profile_events` cuando esa tabla exista (F3); v1 solo pisa y sube `version`.
- **i18n por defecto (constraint global del plan):** todo el cuestionario — labels, opciones, placeholders, botones, pantalla de síntesis, estados de la fila en Perfil — entra por claves `perfil.aprendizaje.*` en las 6 locales (es/en/de/fr/ja/pt), pobladas en el mismo PR; `check-i18n.mjs` como gate. Copy master: este documento, en es.
- La **síntesis LLM se genera en el idioma de UI del usuario** (el prompt de síntesis recibe el locale); si el usuario cambia de idioma de UI, la síntesis se regenera en el próximo guardado, no en caliente.
- Las *respuestas* del usuario quedan en el idioma en que las escribió — son datos, no UI; no se traducen.

## Consumo

- **F4 (generación de cursos):** `synthesis` + respuestas duras (`ses_duracion`, `ses_lugar`→mic, `fija_fichas`, `error_correccion`) entran al prompt de `COURSE_PLAN_PROMPT`. El plan propuesto dice qué eligió y por qué.
- **Overlay por tema:** al plantear un tema nuevo, NuevoTema pregunta solo lo local (meta, fecha, contexto) — máximo 3 preguntas. Este cuestionario NO se repite por tema.
- **Capa observada/sintetizada:** fuera de este spec; llegan con F3 (D-K).

## Fuera de alcance (v1)

Test adaptativo, tipos de aprendiz con etiqueta ("visual", "auditivo" — sin evidencia, no se usan), pesos numéricos del perfil, edición de la síntesis en línea (v1: se corrige re-respondiendo), notificaciones.
