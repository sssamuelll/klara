# Spec — Onboarding de Perfil de Aprendizaje (capa declarada, v1)

> **Estado: listo para implementar.** El gate pre-implementación quedó cerrado el 2026-08-09 (11 contratos, ver «Gate pre-implementación — CERRADO»). La siguiente fuente útil de información es uso real, no más review del documento.
>
> **Enmienda 2026-08-09** (deep-read del research de #138, ver «Base de evidencia» al final): auditoría de cobertura contra el instrumento validado PLSI (+4 preguntas, −1 observable), extracción de átomos estructurados del texto libre, procedencia por afirmación en la síntesis, y telemetría por pregunta para la poda futura (#138 v2a). La selección adaptativa de preguntas queda diferida a #138 a propósito: toda técnica adaptativa del corpus exige datos de población que no existen con un usuario.

**Qué es:** un cuestionario dentro del app que define cómo aprende cada usuario. Klara lo usa para armar las herramientas de cada tema que se plantee. Es la capa **declarada** del Perfil de Aprendizaje (plan maestro v4, sección "El eje que ordena todo", decisión D-K).

**Dónde vive:**
1. **Primer arranque** — usuario sin perfil guardado entra al cuestionario después del login (reemplaza el rol del onboarding global actual; los pasos de idioma/nivel quedan para el flujo del curso de idioma).
2. **Perfil → fila "Cómo aprendes"** — reabre el cuestionario con las respuestas guardadas, editable siempre. Estado de la fila: `Completo · <fecha>` o `Sin llenar`.

**Forma:** una pregunta por pantalla (patrón cero-scroll de v4), con los primitives existentes de `frontend/src/onboarding/` (`ObPrompt`, `ObField`, `ObInlineSelect`, `ObNav`). Toda pregunta se puede saltar. Al final, Klara genera una síntesis y la muestra.

**Duración objetivo:** ~10 minutos. 23 preguntas en 6 bloques.

---

## Pantalla de entrada

- **H1:** `Cómo aprendes tú.`
- **Cuerpo:** `Klara arma cada tema a tu medida. Para eso necesita conocerte: unas veinte preguntas, unos diez minutos, sin respuestas correctas. Puedes cambiar cualquier respuesta cuando quieras, desde Perfil.`
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
| `ses_lugar` | checkbox | `¿Dónde?` | `En casa` · `En transporte o en la calle` · `En pausas del trabajo` — *nota de sistema: define si el micrófono es viable por defecto* |
| `ses_propuesta` | radio | `Al abrir el app, ¿qué prefieres?` | `Que Klara proponga una sola cosa` · `Un menú corto para elegir` · `Según el día` |

## Bloque 3 — Cómo entra un tema nuevo

| id | control | label | opciones |
|---|---|---|---|
| `entrada_arranque` | radio | `Frente a un tema nuevo, ¿por dónde arrancas mejor?` | `Un ejemplo concreto, la teoría después` · `La teoría mínima primero` · `Una historia que lo use` · `Haciéndolo directamente` |
| `entrada_interes` | radio | `¿Qué te engancha de un tema nuevo?` | `Que me sirva ya para algo` · `Que me dé curiosidad por sí mismo` · `Que me rete` · `Depende del tema` — *nota de sistema: ángulo/selección de temas en la generación de historias y planes (F4)* |
| `entrada_reto` | radio | `¿Cómo arrancamos de dificultad?` | `Fácil, y que suba` · `Rétame de una vez` · `Que Klara calibre sola` — *nota de sistema: default de dificultad día 1; el tap de dificultad (#116) la observa después* |
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
| `error_atasco` | radio | `Cuando algo no te entra a la primera:` | `Explícamelo distinto` · `Dame un ejemplo concreto` · `Sigue, y vuelve después` — *nota de sistema: política del tutor cuando el usuario no entiende* |
| `error_pista` | radio | `Atascado en un ejercicio:` | `Déjame pelear un rato antes de la pista` · `Pista temprana, no me dejes trancado` · `Depende del día` — *nota de sistema: política de pistas del tutor; conecta con pretesting (#141)* |
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
- **Procedencia por afirmación (regla del prompt de síntesis):** la síntesis distingue lo anclado en conducta reportada (Bloque 1: `de tu historia con Docker…`) de lo que es autoevaluación (Bloques 3-4: `dices que el audio te fija — Klara lo va a contrastar con el uso`). La literatura metacognitiva muestra que el segundo tipo es el menos confiable; la síntesis no lo presenta como hecho.
- **Extracción de átomos (misma llamada):** además de la prosa, la llamada devuelve `facts` — átomos máquina-legibles extraídos de los 4 textareas (`hist_*`, `libre`). Best-effort: si el JSON no parsea, `facts` queda `NULL` y la prosa se guarda igual (no hay retry propio; se regenera con el próximo guardado).
- **Línea al pie:** `Klara va a afinar esto con el uso. Puedes leerlo y corregirlo cuando quieras, desde Perfil.`
- **Botones:** `Entendido` (primario) · `Corregir una respuesta` (ghost, vuelve al cuestionario).

### Allow-list de `facts` (cerrada)

El paper del que viene esta técnica (TAI) logra su precisión con **slot schema cerrado**, no con extracción libre. Sin allow-list, cada generación inventa claves (`abandona_por` / `razon_abandono` / `quit_reason`) y a los tres meses el JSONB es inconsultable. El prompt recibe estas claves y **toda clave fuera de la lista se descarta al guardar** (validación de servidor, no confianza en el LLM):

| clave | tipo | de dónde sale | para qué la usa F4 |
|---|---|---|---|
| `aprendio_bien_como` | string | `hist_exito` | replicar el método que ya le funcionó |
| `abandono_por` | string | `hist_abandono` | evitar la forma que lo sacó |
| `metodo_sirve` | string[] | `hist_metodos` | priorizar formatos |
| `metodo_no_sirve` | string[] | `hist_metodos` | descartar formatos |
| `dominio_previo` | string[] | `hist_exito`, `libre` | analogías desde lo que ya sabe |
| `restriccion` | string[] | `libre` | límites prácticos (ruido, equipo, horario) |
| `motivacion` | string | `libre`, `hist_exito` | para qué lo quiere — enmarca el plan |
| `evitar` | string[] | `libre` | lo que pidió explícitamente no hacer |

- Valores: strings cortos (≤120 chars) en el idioma en que el usuario escribió. Clave sin evidencia en el texto → **ausente**, nunca `null` ni inventada.
- `facts` es derivado, no fuente: la verdad primaria son los textareas de `answers`. Un cambio de allow-list se re-deriva regenerando, no migrando.

### Mientras la síntesis se genera

El guardado y la síntesis son cosas distintas y la pantalla lo refleja: **guardar nunca falla por culpa de la síntesis.**

- Guardado OK, síntesis en curso → misma pantalla con el cuerpo en estado de espera (`Klara está leyendo tus respuestas…`) y `Entendido` ya habilitado. Salir no cancela nada.
- Guardado OK, síntesis lista → se pinta la prosa.
- Guardado OK, síntesis falló o el usuario salió antes → la fila de Perfil dice `Respuestas guardadas · síntesis pendiente`; se reintenta en el próximo guardado. Sin bloquear nada, sin error rojo.

El mecanismo (background task de FastAPI —el patrón que ya usa `stories.py` para `precache_story`— vs. cualquier otro) es decisión de implementación: el contrato es la experiencia observable de arriba y las reglas de versión de la sección siguiente.

---

## Contrato de datos

```sql
-- migración independiente del dominio Course (no espera a F3)
CREATE TABLE learner_profile (
  user_id              UUID PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
  answers              JSONB NOT NULL DEFAULT '{}',  -- {question_id: valor | [valores] | null}
  timings              JSONB NOT NULL DEFAULT '{}',  -- {question_id: elapsed_ms} medido en cliente
  facts                JSONB,                        -- átomos (allow-list); NULL = pendiente/fallo
  synthesis            TEXT,                         -- prosa LLM; NULL = pendiente
  derived_for_version  INTEGER,                      -- versión de answers que produjo facts+synthesis
  version              INTEGER NOT NULL DEFAULT 1,   -- sube en cada guardado
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Frescura de los derivados.** `facts` y `synthesis` salen de la misma llamada, así que comparten una sola marca. `derived_for_version < version` significa **stale** (hay respuestas más nuevas que la síntesis mostrada) y la UI lo dice: `Respuestas guardadas · síntesis pendiente`. La generación lee la versión que va a sintetizar y escribe `derived_for_version` con ESE número, nunca con el `version` actual leído después — dos guardados seguidos no pueden hacer que una síntesis vieja se declare fresca.

**Medición de `timings`** (importa porque es lo único irreparable de esta tabla: un dato mal medido hoy no se arregla después, y la poda de #138 v2a se entrena con esto):

- Arranca cuando la pregunta se **renderiza visible**; para en `Siguiente`, `Saltar esta` o `Guardar mi perfil`.
- **Se descuenta el tiempo con `document.hidden`** — el usuario que se va a hacer café y vuelve a los 7 minutos no convierte una pregunta barata en "carísima".
- Volver atrás y re-responder **acumula** (el costo total de la pregunta es lo que se quiere medir, no el último tramo).
- Tope duro de 300000 ms por pregunta; por encima es ruido y se guarda el tope.
- El skip no necesita columna: ya es `null` en `answers`, y su `elapsed_ms` es justamente el costo de haberla leído para saltarla.

**Endpoints** — bajo el router `/me` existente (`backend/src/klara/routers/users.py`), misma auth de cookie y misma dependencia `CurrentUser` que el resto de `/me`:

- `GET /me/learning-profile` → `{answers, timings, synthesis, facts, version, derived_for_version, updated_at}`. **404 si nunca se guardó** — "no existe" no se disfraza de "existe vacío"; los defaults viven en la generación (sección siguiente), no en el read path. `facts` se devuelve: es del usuario y alimenta la fila de Perfil; nada ahí es secreto de sistema.
- `PUT /me/learning-profile` ← `{answers, timings, expected_version}`. Guarda, sube `version`, toca `updated_at` en el UPDATE (no solo el default del INSERT) y dispara la regeneración de derivados.
- **`PUT` es reemplazo completo, no merge**, tanto de `answers` como de `timings`: el cliente manda siempre el mapa entero del cuestionario. Así "borrar una respuesta" es expresable (mandar la clave en `null`) y no hace falta un DELETE por pregunta.
- **Concurrencia:** `expected_version` es obligatorio salvo en la creación (perfil inexistente). Si no coincide con `version` → **409** con el estado actual en el cuerpo, para que el cliente muestre el conflicto en vez de pisar en silencio.
- Versiones anteriores: se conservan en `profile_events` cuando esa tabla exista (F3); v1 solo pisa y sube `version`.
- **i18n por defecto (constraint global del plan):** todo el cuestionario — labels, opciones, placeholders, botones, pantalla de síntesis, estados de la fila en Perfil — entra por claves `perfil.aprendizaje.*` en las 6 locales (es/en/de/fr/ja/pt), pobladas en el mismo PR; `check-i18n.mjs` como gate. Copy master: este documento, en es.
- La **síntesis LLM se genera en el idioma de UI del usuario** (el prompt de síntesis recibe el locale); si el usuario cambia de idioma de UI, la síntesis se regenera en el próximo guardado, no en caliente.
- Las *respuestas* del usuario quedan en el idioma en que las escribió — son datos, no UI; no se traducen.

## Esquema canónico de respuestas

Allow-list cerrada. El servidor valida contra ella (modelo Pydantic) y **rechaza claves desconocidas con 422** — no las ignora en silencio, porque una clave desconocida es un cliente desactualizado o un bug, no una preferencia.

| `question_id` | control | cardinalidad | valores |
|---|---|---|---|
| `hist_exito`, `hist_abandono`, `hist_metodos` | textarea | 0-1 | string ≤1000 chars |
| `ses_duracion` | radio | 0-1 | 1 de 4 |
| `ses_lugar` | checkbox | 0-3 | subconjunto de 3 |
| `ses_propuesta` | radio | 0-1 | 1 de 3 |
| `entrada_arranque` | radio | 0-1 | 1 de 4 |
| `entrada_interes`, `entrada_reto` | radio | 0-1 | 1 de 3-4 |
| `entrada_audio`, `entrada_hablar` | radio | 0-1 | 1 de 3 |
| `fija_fichas` | checkbox | 0-4 | subconjunto de 4 — **con exclusión, ver abajo** |
| `fija_feynman` | radio | 0-1 | 1 de 4 |
| `fija_repeticion` | radio | 0-1 | 1 de 3 |
| `fija_prueba` | checkbox | 0-4 | subconjunto de 4 |
| `error_correccion`, `error_atasco`, `error_pista` | radio | 0-1 | 1 de 3 |
| `error_memoria` | radio | 0-1 | 1 de 3 |
| `ritmo_deadline` | radio | 0-1 | 1 de 3 |
| `ritmo_abandono` | checkbox | 0-5 | subconjunto de 5 |
| `ritmo_abandono_otra` | string | 0-1 | ≤200 chars; **solo válida si `ritmo_abandono` incluye `Otra cosa`** |
| `ritmo_regreso` | radio | 0-1 | 1 de 3 |
| `libre` | textarea | 0-1 | string ≤1000 chars |

**Semántica de ausencia** — tres cosas distintas que no se confunden:

- **clave ausente** → no llegó al cliente (versión vieja, pregunta nueva). El servidor no la inventa.
- **`null`** → el usuario la vio y la saltó. Es dato: distingue "no le interesó" de "no se la preguntamos".
- **`[]`** → checkbox que el usuario abrió y dejó vacío. Equivale a `null` para el consumo, pero se guarda distinto porque su `elapsed_ms` sí cuenta.

**Exclusión mutua.** `fija_fichas` es el único checkbox con opción de negación: `Las fichas no me funcionan` **no puede coexistir** con ninguna de las otras tres. Se bloquea en dos capas — en la UI (marcarla deselecciona las demás y viceversa) y en la validación de servidor (422). Regla general para cualquier opción de negación futura: si una opción niega el eje entero, es exclusiva y se declara acá.

## Estados del perfil

La fila `Cómo aprendes` de Perfil tiene tres estados, y **`Completo` no significa 23 de 23**. Saltar es legítimo por diseño; un contador de saltos convertiría la fila en un reproche, que es exactamente lo que la constitución del plan prohíbe (D-A, sin guilt). El estado se ata a lo que de verdad cambia el comportamiento de Klara — las 8 preguntas de consumo:

`ses_duracion` · `ses_lugar` · `fija_fichas` · `error_correccion` · `entrada_interes` · `entrada_reto` · `error_atasco` · `error_pista`

| estado | condición | copy |
|---|---|---|
| Sin llenar | no hay fila (404) | `Sin llenar` |
| A medias | fila guardada, falta alguna de las 8 | `A medias · <fecha>` |
| Completo | las 8 respondidas (el resto puede estar saltado) | `Completo · <fecha>` |

Tocar `A medias` entra al cuestionario **en la primera de las 8 sin responder**, no al principio. Es ayuda, no penitencia.

## Defaults sin perfil

`GET` devuelve 404 y la generación usa estos valores. Contrato de producto: **el default se usa y se declara** — el plan propuesto dice `Klara todavía no te conoce: asumí sesiones de 10 minutos`, y esa frase es la que empuja a llenar el cuestionario, no un bloqueo.

| pregunta | default | por qué |
|---|---|---|
| `ses_duracion` | `10 minutos` | el medio; ni castiga ni infla |
| `ses_lugar` | mic viable | el permiso del navegador ya es el gate real |
| `fija_fichas` | las 3 formas activas | sin evidencia, no se recorta el repertorio |
| `error_correccion` | `Suave y con contexto` | el menos invasivo con un desconocido |
| `entrada_interes` | `Depende del tema` | se resuelve por tema en F4 |
| `entrada_reto` | `Que Klara calibre sola` | delega a la señal observada |
| `error_atasco` | `Explícamelo distinto` | el más barato y reversible |
| `error_pista` | `Depende del día` | ni frustra ni regala |

**Proyección `ses_lugar` → micrófono** (regla determinista): mic viable **salvo que la única selección sea `En transporte o en la calle`**. `null`, `[]` y cualquier combinación que incluya casa o trabajo → viable. Un default demasiado tímido acá mataría la mitad del producto; el permiso del navegador y el medidor de nivel (#120) son la defensa real.

## Privacidad

- **Qué sale del sistema:** las respuestas del cuestionario van al proveedor LLM vía LiteLLM para generar `synthesis` y `facts`. Nada más viaja: ni email, ni nombre, ni identificadores — el prompt recibe respuestas y locale.
- **Las respuestas NUNCA se loguean.** Ni en `structlog`, ni en errores, ni en trazas del job de síntesis: se registra `user_id` y el resultado (ok/fallo), jamás el contenido. Klara tiene historial de alertas de clear-text-logging; esta tabla es exactamente el tipo de dato que las dispara.
- **Retención propia:** una sola fila viva por usuario. Sin copias, sin snapshots (las versiones anteriores llegan con `profile_events` en F3, y esa tabla traerá su propia política).
- **Borrado:** hoy **no existe endpoint de borrado de cuenta** en el backend — verificado, no hay ninguno. El `ON DELETE CASCADE` deja la tabla lista para cuando exista; cuando se construya, `learner_profile` no necesita trabajo extra. Declarado acá para que no se descubra tarde.

## Consumo

- **F4 (generación de cursos):** `synthesis` + `facts` + respuestas duras (`ses_duracion`, `ses_lugar`→mic, `fija_fichas`, `error_correccion`, `entrada_interes`, `entrada_reto`, `error_atasco`, `error_pista`) entran al prompt de `COURSE_PLAN_PROMPT`. El plan propuesto dice qué eligió y por qué.
- **Overlay por tema:** al plantear un tema nuevo, NuevoTema pregunta solo lo local (meta, fecha, contexto) — máximo 3 preguntas. Este cuestionario NO se repite por tema.
- **Capa observada/sintetizada:** fuera de este spec; llegan con F3 (D-K).

## Gate pre-implementación — CERRADO 2026-08-09

Los 7 puntos del review externo (CodeRabbit, PR #117) más los 4 que levantó el review de la enmienda. Dónde quedó cada uno:

| # | Contrato | Cerrado en |
|---|---|---|
| 1 | Defaults sin perfil + qué responde el GET | «Defaults sin perfil» (tabla de 8) · GET = 404 |
| 2 | Esquema canónico: allow-list, cardinalidad, `null`/`[]`/ausente, `ritmo_abandono_otra`, límites | «Esquema canónico de respuestas» |
| 3 | Proyección `ses_lugar` → mic, incluido el caso `null` | «Defaults sin perfil», regla determinista |
| 4 | Síntesis: estados, retry, qué versión de answers leyó | `derived_for_version` + «Mientras la síntesis se genera» |
| 5 | Privacidad: retención, borrado, logging | «Privacidad» |
| 6 | Auth explícita | `/me/learning-profile` bajo `CurrentUser`, router `/me` existente |
| 7 | Concurrencia: `expected_version`, 409, `updated_at` en UPDATE | «Endpoints» |
| 8 | Medición de `timings` (el irreparable) | «Medición de `timings`» — descuenta `document.hidden`, acumula, tope 300s |
| 9 | Exclusión mutua en `fija_fichas` | «Esquema canónico» — dos capas, UI + 422 |
| 10 | Definición de `Completo` | «Estados del perfil» — atado a las 8 de consumo, no a 23/23 |
| 11 | Qué se ve mientras la síntesis genera | «Mientras la síntesis se genera» |

Dos correcciones propias de la enmienda del 2026-08-09, del mismo tirón:

- **`facts` no tenía esquema de claves.** La técnica viene de un paper cuyo resultado depende de un slot schema cerrado; portarla sin él producía un JSONB inconsultable a los tres meses. Cerrado con allow-list de 8 claves y descarte de lo demás en el servidor.
- **Las líneas de `GET`/`PUT` no mencionaban `timings` ni `facts`** — inconsistencia introducida al agregar las columnas. Cerrada.

**Regla de alcance aplicada en esta pasada:** el spec fija *qué debe ocurrir* y lo irreversible (semánticas de datos, estados observables, contratos de validación). El *cómo* —background task vs. otra cosa, forma de los modelos Pydantic, estructura de los componentes React— es del diseño técnico. Lo único que se trató como spec pese a sonar técnico fue la medición de `timings`, porque a los datos ya recogidos no se les retrofitea correctitud.

**Siguiente fuente útil de información: uso real, no más review del documento.** Otra ronda sobre el modelo del cuestionario no agrega señal.

## Fuera de alcance (v1)

Test adaptativo, tipos de aprendiz con etiqueta ("visual", "auditivo" — sin evidencia, no se usan), pesos numéricos del perfil, edición de la síntesis en línea (v1: se corrige re-respondiendo), notificaciones.

- **Selección/orden adaptativo de preguntas** (entropía, árboles de entrevista, bandits): diferido a #138 con causa — toda variante del corpus exige datos de población; con N=1 degenera a orden aleatorio (lo dicen los propios papers). `timings` + `answers` de v1 son su materia prima.
- **Síntesis negociable por claim** (OLM, Bull & Kay): cada afirmación de la síntesis con affordance de disputa en vez de re-abrir el wizard. La pieza más "SOTA educativo" del corpus, ~1-2 días. **Pendiente de decisión del dueño** — no entra sin OK explícito porque amplía la exclusión "edición de la síntesis en línea".
- **Elicitación conversacional** (el tutor pregunta en diálogo): viable con N=1 (TAI lo demuestra con datos sintéticos), pero reemplaza el build del wizard; queda en #138 v3. La extracción de `facts` da la mitad del valor al 5% del costo.

## Base de evidencia de la enmienda 2026-08-09

Deep-read completo (reasonix, 8 papers) sobre las fuentes de #138 + instrumento UDL. Lo que cada decisión le debe a qué fuente:

- **Auditoría de cobertura y las 4 preguntas nuevas** (`entrada_interes`←CRG, `entrada_reto`←SLV-23, `error_atasco`←TPM-12, `error_pista`←EL-19): `docs/research/Universal Design for Learning frente a clasificación de usuarios/Measuring personalized learning through the Lens of UDL Development and content validation of a student self-report instrument.pdf` — PLSI, 25 ítems, validez de contenido I-CVI 0.86–1.00, S-CVI 0.97, legibilidad grado 5. Único instrumento validado del corpus; sirve como checklist de constructos (CRG/FMM/TPM/SLV/EL), no se copian ítems (framing escolar).
- **Poda de `ses_momento`**: `docs/research/Cold start y onboarding/User preference elicitation, rating sparsity and cold start.pdf` — no preguntar lo que se observa; el momento del día sale gratis de los timestamps de uso (capa observada).
- **Formato elección (ya cumplido por la spec, validado)**: `docs/research/Cold start y onboarding/Improving the User Experience during Cold Start through Choice-Based Preference Elicitation.pdf` — elección vs escala: 280s vs 388s, t(102)=6.024, p<.001, más satisfacción.
- **Extracción de `facts`**: `docs/research/Cold start y onboarding/Learning Personalized User Preference from Cold Start in Multi-turn Conversations.pdf` (slot-filling de preferencias enseñadas en lenguaje natural, 91.22% turn-level, arranca con cero usuarios) + `docs/research/Cold start y onboarding/Ontology-based E-learning Content Recommender System for Addressing the Pure Cold-start Problem.pdf` (el perfil máquina-legible mapea por reglas a atributos de contenido; su hallazgo negativo — estilos FSLSM solos agrupan al 46.9% — revalida nuestra exclusión de "estilos").
- **Procedencia por afirmación en la síntesis**: corpus `docs/research/Precisión metacognitiva/` (ilusiones metacognitivas: la autoevaluación de métodos es el juicio menos calibrado; la conducta pasada, el más honesto — por eso Bloque 1 ancla y Bloques 3-4 se marcan como impresión).
- **Diferir lo adaptativo (con números)**: `docs/research/Cold start y onboarding/Learning Preferences of New Users in Recommender Systems An Information Theoretic Approach.pdf` (entropía por pregunta se computa sobre población), `docs/research/Cold start y onboarding/Functional Matrix Factorizations for Cold-Start Recommendation.pdf` (árbol de entrevista entrenado con 6k–480k usuarios, solo offline), `docs/research/Cold start y onboarding/Seamlessly Unifying Attributes and Items Conversational Recommendation for Cold-start Users.pdf` (ConTS: sin población la selección es "somehow random"; sus autores lo llaman técnica de fase cold-start).
