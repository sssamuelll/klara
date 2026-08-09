# Spec F2 — Reskin de sesiones al design system v4

**Fecha:** 2026-08-09 · **Fase:** F2 del plan maestro v4 (`docs/superpowers/plans/2026-07-31-rediseno-v4-biblioteca.md`) · **Estado:** borrador para review

La spec dice **qué** y fija los contratos; la implementación React decide **cómo**. Cero migraciones, **cero cambios de backend** (verificado abajo — el único que el plan preveía ya existe).

---

## 1. Resumen

Las tres pantallas de sesión (lectura de Story, Repaso de fichas, Speak) y el cierre de historia (StoryFinish) viven hoy bajo `LegacyShell` (`kapp`/`kframe`/`Masthead`) con su CSS viejo (`pages.css`, `sentence-view.css`, `finish.css`, `speak.css`). F2 las re-viste con el design system v4 (`m3-*`) siguiendo el mockup `docs/design/klara-v4/mobile4-sessions.jsx`, **sin tocar la lógica de sesión ni la persistencia de señales**. Es la última fase puramente visual antes del spec-gate de F3.

## 2. Estado actual verificado (2026-08-09, trazado con file:line)

| Hecho | Evidencia |
|---|---|
| Story se monta en `/story/:id` bajo LegacyShell | `App.tsx:145-152` |
| Practice en `/review`, Speak en `/chat` (no `/speak`), ambos LegacyShell | `App.tsx:161-168, 177-184` |
| Árbol Story: `Story.tsx` (287) → `useSentencePractice` (631), `SentenceView` (639), `WordPopover` (129), `BreakdownPopover` (88), `StoryFinish` (1437) | trazado §1 |
| **`next_intervals` YA existe** — payload por carta con los 4 ratings precalculados por FSRS sin persistir | `schemas/srs.py:27`, `routers/srs.py:46`, `services/srs_engine.py:111-127` (`project_intervals`) |
| El frontend ya lo consume | `RecallReviewSession.tsx:118,185` + `srsProjection.ts` (`formatInterval`) |
| Shape de sentences: `{target, native, new_words, breakdown[{word,translation,pos?}]|null}` | `schemas/story.py:21-50` (el plan omitía `new_words`) |
| `tokenize()` y `buildBreakdownMap()` existen | `SentenceView.tsx:101-111, 132-148` |
| `SpeakTurnOut`: `tokens[{t,s,focus}]`, `scores`, `target{word,gloss,focusAccuracy,shouldIpa,modelSentence}`, `reply{target,native}`, camelCase | `schemas/speak.py:14-52` |
| Las 7 clases de sesión v4 **ya están en el repo**: `m3-sess-top`, `m3-lect`, `m3-dock`, `m3-fb`, `m3-sheet`, `m3-carta`, `m3-corr` | `frontend/src/styles/mobile3.css:100-158` |
| El repo mobile3.css **divergió** del mockup (líneas distintas — el repo evolucionó: safe-area, fixes de Iris) | comparación de line numbers repo vs mockup |
| StoryFinish persiste: quiz attempts, pronunciation attempts, gender attempts, difficulty; Summary lee insight/l1-notes/schedule/klara-note | `StoryFinish.tsx` (trazado §7) |
| El mockup **no tiene** pantalla de fin de sesión — las 3 sesiones salen directo a `go("curso")` | `mobile4-sessions.jsx:33,121,134` |

## 3. Decisiones cerradas en esta spec

### D-D — intervalos reales: **ya satisfecha por #125, F2 solo la muestra**

El plan escribió D-D cuando el motor era SM-2 y pedía "~30 líneas + test" de backend. Eso ya lo trajo FSRS (PR #147): `project_intervals()` precalcula los 4 ratings sin persistir y viaja en cada `CardOut`. Consecuencia:

- **F2 no toca backend.** El item de roster "Halberg revisa el PR de `next_intervals`" queda sin objeto — se retira.
- UI de Repaso v4: **3 salidas** — `Otra vez` (again), `Bien` (good), `Fácil` (easy) — cada una con su intervalo real formateado (`formatInterval`) como sublabel donde el mockup hardcodea "1 día / 4 días / 9 días". `hard` sigue en el enum y en el payload, **sin botón** (D-D original: "Sin HARD en UI"). La UI actual muestra 4 botones; el reskin baja a 3.
- **Atajos de teclado (finding Serrano #4):** el mapa baja con los botones — `1`/`2`/`3` → again/good/easy, alineado 1:1 con las salidas visibles; `4` deja de hacer nada y `hard` queda **inalcanzable por teclado** (coherente con "Sin HARD en UI"). El array `RATINGS` visible de `RecallReviewSession.tsx:12` y el handler de `revealed` se ajustan juntos. Test de contrato obligatorio: pulsar `2` tras el recorte envía `good`, jamás `hard`.

### Mic de Estudiar — nada que corregir

El plan pedía corregir un label "Mantén pulsado" en el teleprompter. El mockup real no lo tiene: el mic de Estudiar es toggle limpio con `aria-label="Decirlo en voz alta"` y estado "● Te escucho…" en el dock (`mobile4-sessions.jsx:17-93`). Se porta tal cual.

### Mic de Explicar — el copy se corrige, el comportamiento no cambia

El label "Mantén pulsado para hablar" vive en **Explicar** (`mobile4-sessions.jsx:119`) sobre un botón que se comporta como toggle — el mockup se contradice a sí mismo. Resolución: comportamiento **toggle** (el de Speak hoy), copy corregido a `Toca para hablar` / `Te escucho…`. Hold-to-talk **no se implementa** (nada lo pide; fuera de alcance).

### D-E — StoryFinish: **el quiz SE CONSERVA, se re-viste**

El plan condicionaba D-E a "uso real de Samuel en F1", insumo que no va a existir (etapa de construcción). Se resolvió con el corpus de research (búsqueda nivel-índice 2026-08-09, `docs/research/`):

- **A favor de conservar:** meta-análisis y revisiones sistemáticas del testing effect (`Eficacia real de los métodos de aprendizaje/Rethinking the Use of Tests…`, `…Retrieval Practice Consistently Benefits…`, `Medición…/Effects of Test Taking…`, `…The influence of retrieval on retention`); recuperación **con feedback** supera relectura (`…Strengthening concept learning by repeated testing`). Cero entries a favor de cerrar sin quiz.
- **Además:** el quiz es la fuente de señal por historia del eje aprendiz — quiz attempts, pronunciation attempts, gender attempts, difficulty taps — materia prima de #126/#134. Matarlo violaría la regla F1-F2 del plan ("los reskins NO pierden señales que hoy se persisten").
- El mockup no tiene pantalla de fin: **desviación documentada del mockup**, con esta razón. El quiz y el Summary se re-visten con el chrome v4 (SessTop + `m3-prog` + tipografía/clases m3), **la lógica y la persistencia quedan intactas** (no se reescribe el reducer de `quizSession` ni los componentes de pregunta; cambia la piel, no el esqueleto de 1437 líneas).

### Rutas y shell — se adopta el Global Constraint de URLs 1:1

El plan maestro exige URLs 1:1 con el mockup (`/estudiar/:id`, `/explicar/:id`, `/repaso/:id`) "en toda fase"; el borrador inicial de esta spec lo contradecía sin declararlo (finding Serrano #2). Resolución — F2 es el momento natural del cambio, porque es la fase que saca estas pantallas de LegacyShell:

- **Rutas canónicas nuevas:** `/estudiar/:id` (id de story), `/repaso`, `/explicar`. Las dos últimas van **sin `:id` de curso**: el dominio Course no existe hasta F3 — desviación documentada del constraint, se completa cuando el curso sea real (F3).
- **Los paths legacy redirigen**, no mueren: `/story/:id` → `/estudiar/:id`, `/review` → `/repaso`, `/chat` → `/explicar` (`<Navigate replace>`). Ningún deep-link ni bookmark se rompe.
- Las tres salen de `LegacyShell` a un **layout de sesión v4**: `m3-app` **sin TabBar** (mockup: las sesiones excluyen tabs), con safe-area según el patrón del shell F1 (`m3-sess-top` arriba, `m3-dock`/`m3-fb`/`m3-srs` abajo).
- **"← Salir" (SessTop):** navega a `state.from` si la pantalla de origen lo pasó al entrar (Portada pasa `/curso/:id`, Inicio pasa `/`), con fallback `/`. Regla única para las 3 sesiones (finding #11 — el mockup vuelve a la Portada, el código de hoy a Inicio; `state.from` satisface ambos flujos sin acoplar sesiones a un dominio de curso que aún no existe).
- `Masthead` deja de renderizarse en esas pantallas (el plan lo conservaba "hasta F2" — esto es F2). Sigue vivo para login/signup/onboarding/settings mientras existan en LegacyShell.

### Alcance de Repaso

Solo el segmento **fichas** (`RecallReviewSession`) se re-viste. Los segmentos `pronunciation` y `gender` de `Practice.tsx` quedan como están (el mockup no los cubre; se re-visitan cuando toque, no en F2).

### Estados que el mockup no dibuja — contrato v4 (cierra el BLOCKER de Serrano)

El mockup es una demo con `curso` pre-cargado: jamás dibuja carga, error ni vacío. El código real sí los modela (11 `PronunciationErrorKind` en `pronunciation.ts:127-138`, shape discriminado de `SpeakTurnOut`, 6 fases en `recallSession.ts:9`). Contrato único, sin diseño nuevo por tipo:

**Regla general — un solo contenedor de nota:** todo error y estado terminal usa el patrón `m3-fb` (nota serif 17px + acciones `k-btn`), el mismo slot que el feedback de pronunciación. Cero contenedores ad-hoc; los `.k-error`/`.story-loading` legacy mueren solo cuando su pantalla ya porta esto.

| Pantalla | Estado | Contrato v4 |
|---|---|---|
| Estudiar | cargando story | `SessTop` + spinner centrado en el slot `m3-lect` (sin dock) |
| Estudiar | error de fetch / story inexistente | nota `m3-fb` con el mensaje i18n existente + acción "← Salir" |
| Estudiar | cualquier `PronunciationErrorKind` (los 11, `mic_denied` incluido) | nota `m3-fb` **reemplaza el dock** con el mensaje i18n ya existente por tipo + "Otra vez" (reintentar) / "Continuar" (saltar). Sin visual nuevo por tipo: el mensaje distingue, el contenedor es uno |
| Repaso | `loading` | `SessTop` + spinner en el slot de la ficha |
| Repaso | `failed` | nota `m3-fb` con mensaje existente + "Reintentar" |
| Repaso | `empty` (cero vencidas — estado de producción frecuente) | nota `m3-fb` con el copy existente de "nada vencido" + "← Salir". Sin culpa, sin CTA de "estudia más" (D-A) |
| Repaso | `done` | resumen actual (`restedCount`) re-vestido: cifra serif + "← Salir" |
| Explicar | `noSpeech` / `lowConfidence` | hint en el `miclbl` bajo el mic (copy actual de Speak), la carta conserva el último turno — no son errores, son turnos fallidos |
| Explicar | errores de hardware/permiso de mic | nota `m3-fb` bajo la carta con mensaje existente + "Otra vez" |

Los mensajes son los que ya existen en i18n — este contrato asigna contenedor, no reescribe copy.

## 4. F2.0 — Cola de apertura (antes del primer reskin)

Deuda diferida de F1, ya enumerada en el plan (línea 167-174), cero decisiones pendientes:

1. **Pase a11y** de las pantallas v4 existentes: `li onClick` → botones reales con teclado (Portada/MapaCurso/NuevoPlaceholder), `aria-current` en TabBar, `role="switch"` en la fila de tema de Perfil, glifos decorativos `aria-hidden`, Escape cierra el menú Más. Obligatorio antes de un segundo usuario.
2. **Limpieza vex-rune:** borrar `Home.tsx` (huérfano), `CourseVM.currentModule` y `loading` de `useCourseData` (cero consumidores), condicionar `data-hot`.
3. **Copy:** saludo con `{{name}}` (puntuación ja), punto latino tras h1 en ja, spacing "Klara が/Klaraが".
4. **Doc reconcile:** el diagrama del plan dice "`nuevo` sin TabBar", F1 lo montó con TabBar — anotar en el plan cuál gobierna cuando `/nuevo` sea real (F4).

(El ítem "validar `.m3-fb`/`line-clamp`/9px con contenido real" se ejecuta dentro de cada reskin, no como paso previo.)

## 5. Los cinco reskins (un PR cada uno, en este orden)

### F2.1 — Estudiar (teleprompter)

- `Story.tsx` deja LegacyShell; chrome nuevo: `SessTop` (título + `NN/NN` + "← Salir") + barra `m3-prog` de segmentos.
- `SentenceView` adelgaza al formato `m3-lect`: `m3-oracion` (serif, clamp 25-30px) con tokens clickeables `m3-w`, `m3-gloss` mono **12px** (Iris: "la L1 es lectura funcional, no nota al pie" — el mockup trae 11.5px, gana Iris).
- Adaptador client-side: `sentences[{target,native,new_words,breakdown}]` → tokens vía `tokenize()`/`buildBreakdownMap()` existentes. El shape del server **no cambia**.
- Dock: ← anterior · play 66px · mic 54px (toggle, `data-on`) · siguiente →. Estados del dock: "K lee · despacio" (playing), "● Te escucho…" (rec).
- Feedback de pronunciación: `m3-fb` **reemplaza** el dock (nota serif 17px con `em` accent + "Otra vez"/"Continuar →"). Toda la maquinaria de `useSentencePractice` (scoring, stream, hints, diagnose, attempts) queda intacta.
- Estados de carga/error/captura: contrato de §3 ("Estados que el mockup no dibuja").
- **Oraciones largas (finding Serrano #8):** el recorte silencioso de `line-clamp:7` deja de ser aceptable como comportamiento por defecto. Regla: auto-ajuste de `--fscale` (la variable ya existe justo para esto — `font-size:calc(clamp(...)*var(--fscale,1))`) midiendo la oración al montar; escalones 1 → 0.92 → 0.85; **piso 0.85**. Solo por debajo del piso el clamp actúa como último recurso (outlier extremo del LLM). Validación en el PR contra la oración más larga real del corpus; ídem min-height de `.m3-fb` contra el feedback más largo.

### F2.2 — Sheet de palabra

- `WordPopover` + `BreakdownPopover` se **fusionan** en un `m3-sheet` (bottom sheet con `m3-scrim`, grab, animación `m3-up`).
- Contenido: lemma serif 28px con artículo coloreado (`m3-art-*`, solo de), botón audio, traducción, ejemplo con borde izquierdo.
- Botón `+ Añadir al repaso` / `✓ En repaso`: **solo cuando hay `StoryWord` con id** (camino `api.addCard` actual de WordPopover). Entradas que solo existen como `WordBreakdown` (sin vocab id — hoy BreakdownPopover) muestran el sheet **sin** botón de repaso. `frequency_rank` y POS se conservan donde existan.
- **El botón es async, no el toggle instantáneo del mockup (finding Serrano #7):** estados `idle → adding (deshabilitado) → added ✓`; si `api.addCard` falla, vuelve a `idle` (el swallow actual se conserva). Desviación de comportamiento respecto al mockup, documentada aquí. Test de contrato: el tap dispara `api.addCard`, no un estado local.
- **Locuciones (finding #10):** cuando `WordBreakdown.word` trae varias palabras, el título del sheet renderiza la locución completa en el mismo serif 28px con wrap (`overflow-wrap:anywhere`, como la ficha de Repaso) y sin artículo. Sin tratamiento tipográfico nuevo.
- Los `.wpop*` de `pages.css` quedan muertos tras este PR → se lo lleva vex-rune.

### F2.3 — Repaso (fichas)

- `RecallReviewSession` → `m3-ficha` (tap para girar; recto: artículo + palabra + audio; dorso: `posw` + trad + ejemplo de/es) + `m3-srs` de **3 botones** con intervalos reales (D-D §3, incluido el contrato de teclado 1/2/3). Botones visibles sólo con dorso (el mockup reserva el espacio con `visibility:hidden` — se porta igual para que la ficha no salte).
- `SessTop` "Repaso · {curso}" + progreso lineal por posición.
- El flujo `recallSession.ts` (reducer de fases) no cambia; `api.dueCards`/`api.review` intactos. Las 6 fases (`loading/failed/empty/prompt/revealed/done`) tienen su chrome asignado en §3 ("Estados que el mockup no dibuja") — ninguna queda a criterio del ejecutor.

### F2.4 — StoryFinish (D-E ejecutada)

- Chrome v4 sobre el flujo actual: quiz (MC/Cloze/Shadow/GenderCloze, pase principal + retry) y Summary con la piel m3 (tipografía, rows, botones k-btn), dentro del layout de sesión.
- **Contrato duro:** los endpoints y el orden de llamadas no cambian — `quiz/attempts`, `pronunciation/attempts` (incluido el sentinel −1), `gender/attempts`, `difficulty`, `finish` en `onSummaryShown`, lecturas del Summary. Checklist de señales en el PR (regla F1-F2 del plan).
- `finish.css` queda muerto al final → vex-rune.

### F2.5 — Explicar (reskin superficial de Speak)

- `Speak.tsx` con piel `m3-carta`: turno de Klara (`quien` mono 9px→**10px** si el pase de legibilidad de Iris aplica igual que en el resto del repo, `de` serif clamp 24-28px, `es` mono con borde), corrección `m3-corr` (`mal` tachado → `bien` accent + nota) alimentada por los campos existentes de `SpeakTurnOut`.
- Dock `hablar`: grid 1fr-auto-1fr, mic grande 74px toggle, laterales mono ("¿Cómo se dice…?" / "Terminar"). Copy del mic: `Toca para hablar` / `Te escucho…` (§3).
- `noSpeech`/`lowConfidence` (shape discriminado de `SpeakTurnOut` — el cliente branchea sobre ellos PRIMERO) y errores de mic: contrato de §3.
- Los 3 modos de Explicar **no entran** (F5). `speak.css` muere si queda sin consumidores → vex-rune.

## 6. Disciplina de CSS (lección del handoff de F1.5)

- **Nunca copiar archivos enteros del mockup al repo.** El repo ya evolucionó (safe-area, fixes de legibilidad de Iris, clases nuevas); 3 de 4 CSS del handoff de onboarding estaban stale y copiarlos habría regresionado fixes reales.
- Método: diff mockup↔repo de las reglas de sesión; portar **solo reglas faltantes** a `mobile3.css`/`mobile4.css` del repo; toda divergencia deliberada (gloss 12px, micro-mono 9px→10px si aplica) se anota en el PR.
- CSS viejo (`sentence-view.css`, `finish.css`, `speak.css`, `.wpop*`/`.kp-*` de `pages.css`) **no se borra en el PR del reskin**: vex-rune pasa después de cada pantalla y propone la eliminación de lo que quedó sin consumidores (roster del plan).

## 7. Fuera de alcance

- **Continuidad de sesión a medio quiz (finding Serrano #6):** un refresh durante el quiz de StoryFinish devuelve a la vista de lectura y pierde el intento en curso. Es comportamiento heredado, **se declara statu quo aceptado** — los attempts ya respondidos sí quedaron persistidos (van pregunta a pregunta), solo se pierde la posición. Se revisita si duele con uso real, no en F2.
- Hold-to-talk real (nada lo pide).
- Los 3 modos de Explicar y toda generalización de Speak (F5; los gates `FOCUS_PHONEME_SETS`/`target_language` no se tocan).
- Segmentos `pronunciation` y `gender` de Practice.
- Rediseño del contenido del quiz (tipos de pregunta, reducer) — solo piel.
- Consolidación de los 3 tokenizadores del frontend (`SentenceView.tokenize`, copia local de `StoryFinish`, `pronunciation.ts` espejo de `tokens.py`) — anotada para vex-rune, no es de F2.
- `next_intervals` (ya existe) y cualquier otro cambio de backend.
- Pantallas LegacyShell restantes (login/signup/onboarding/settings/module/gender): siguen como están.

## 8. Criterios de éxito

1. Las tres sesiones + StoryFinish renderizan con chrome v4 (SessTop/m3-prog/dock) sin TabBar, con safe-area correcta arriba y abajo, pixel-perfect contra `mobile4-sessions.jsx` salvo desviaciones documentadas (§3, §5, §6).
2. **Cero señales perdidas:** por PR, checklist de que cada endpoint de persistencia que la pantalla llamaba antes se sigue llamando con el mismo payload en los mismos momentos (la lista exacta por pantalla está en §5).
3. Los intervalos mostrados en Repaso son los de `next_intervals` del payload, nunca hardcodeados.
4. Gates locales verdes (tsc, vitest, i18n 6 locales, build) por PR; pytest no debería moverse (cero backend) — si se mueve, es un smell.
5. Gate visual de Iris por pantalla (roster del plan). Los textos nuevos pasan por i18n (nada hardcodeado en español).
6. a11y de F2.0 aplicada también a las pantallas nuevas: mic y controles con `aria-label`, botones reales, foco gestionado al abrir/cerrar el sheet.

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Regresión silenciosa de persistencia al re-vestir StoryFinish (1437 líneas) | Contrato §5.4 + checklist de señales por PR; piel sin tocar lógica |
| Copiar CSS stale del mockup | §6: diff dirigido, nunca archivos enteros |
| `m3-oracion`/`m3-fb` no aguantan contenido real (oraciones/feedback largos) | Validación con contenido real dentro de F2.1 (plan, cola F1) |
| El sheet fusionado pierde un caso de BreakdownPopover (palabra sin id) | Contrato §5.2: sheet sin botón de repaso para esas entradas |
| Micro-mono 9px ilegible (ya corregido a 10-12px en el resto del repo por Iris) | Decidir en cada PR con la misma regla que el repo ya adoptó; anotar la desviación del mockup |

## 10. Roster de ejecución

- **Ejecutor:** kimi `k3-max` con TDD (Claude escribe los tests del contrato de señales y adaptadores; kimi implementa en worktree; protocolo de la skill saver §5). Piel/CSS puro puede ir directo con review de diff.
- **Iris Tane:** gate visual por pantalla (merge-blocker).
- **vex-rune:** pasa tras cada pantalla a proponer eliminación de CSS/componentes muertos.
- ~~Halberg sobre `next_intervals`~~ — retirado: el cambio ya existe (§3 D-D). Racional del retiro (finding Serrano #9): `project_intervals()` es proyección pura sin escritura (`review_card` copia internamente — docstring verificado en `srs_engine.py:111-127`) y #125 pasó TDD (14 tests) + 2 refutadores + ensayo de deploy sobre dump real. Si Halberg pasa, sería sobre #125 ya mergeado, no como gate de F2.

## 11. Cierre del review de Serrano (2026-08-09)

| # | Sev | Finding | Dónde se cerró |
|---|---|---|---|
| 1 | BLOCKER | Errores de captura de voz sin contrato v4 | §3 "Estados que el mockup no dibuja" (tabla) |
| 2 | HIGH | Rutas contradicen el Global Constraint 1:1 | §3 "Rutas y shell" — se adoptan `/estudiar/:id`, `/repaso`, `/explicar` + redirects |
| 3 | HIGH | 4 de 6 fases del reducer de Repaso sin chrome | §3 tabla de estados; referenciado en §5 F2.3 |
| 4 | HIGH | Atajo 1-4 desalineado al bajar a 3 botones | §3 D-D — mapa 1/2/3, `hard` inalcanzable, test de contrato |
| 5 | HIGH | Carga/error de story sin chrome v4 | §3 tabla de estados (filas Estudiar) |
| 6 | MEDIUM | Quiz interrumpido sin declarar | §7 — statu quo aceptado, con racional |
| 7 | MEDIUM | Botón del sheet: async real vs toggle del mockup | §5 F2.2 — estados idle/adding/added + test de contrato |
| 8 | MEDIUM | `line-clamp:7` sin resolución | §5 F2.1 — auto-ajuste `--fscale`, piso 0.85, clamp solo último recurso |
| 9 | LOW | Retiro de Halberg sin verificar su lente | §10 — racional documentado |
| 10 | LOW | Locuciones multi-palabra en el sheet | §5 F2.2 — wrap serif 28px sin artículo |
| 11 | MEDIUM | Destino de "← Salir" sin declarar | §3 "Rutas y shell" — regla `state.from` con fallback `/` |
