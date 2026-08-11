# Kickoff v2 — El escritorio de Klara (app + landing)

**Fecha:** 2026-08-10 · **Para:** el agente de diseño que escribirá la spec del escritorio
**Estado de partida:** main `c5a0faf` (Puerta de entrada v4 en prod) — la spec se escribe contra este estado CONGELADO; si F2.x aterriza antes de la ejecución, se reconcilia en la fase de plan, no en la spec.
**Este documento sustituye íntegramente la v1** (PR #160). Fue endurecido por sesión adversarial del roster + investigación de mercado + evidencia del corpus propio: `ACTA-2026-08-10-sesion-adversarial.md` y `research/anexo-1..5`. Las resoluciones del acta son vinculantes.

---

## 0. Misión

Diseñar el escritorio de Klara y llevar el diseño al siguiente nivel. Hoy, a 1440px, toda la app v4 es una columna de 430px flotando con un borde (`mobile3.css:10-11`). No hay diseño de escritorio que mejorar: se parte de cero, con identidad ganada y producto funcionando.

Dos audiencias, dos superficies, dos varas — no se mezclan:
- **La app** sirve al **estudiante**: que quien estudia una hora en escritorio termine convencido de que estudiar aquí es mejor que en el teléfono. Su vara es conductual (§9.1).
- **La landing** sirve al **evaluador** (invitado que decide si entra; curioso que deja su correo): que piense "producto serio hecho por gente con criterio". Su vara es el gate de Iris + conversión del waitlist.

## 1. El caso — por qué este proyecto existe (anexos 1, 2, 4)

- **Ningún competidor mainstream diseña para desktop.** Duolingo/Babbel/Busuu/Mango son el mismo layout móvil ensanchado; los atajos de teclado de Duolingo y Busuu existen solo vía extensiones de terceros. La IA conversacional se lanza móvil-first; el escritorio es ciudadano de segunda en toda la categoría (anexo 1).
- **Las herramientas que sí sirven a la sesión larga cobran peaje**: LingQ/Migaku/Clozemaster = "anticuada", "abrumadora", "confuso al inicio". **El hueco exacto: nadie fusionó motor de repaso serio (grado Anki: FSRS, colas, teclado, densidad) con producto que no da miedo abrir.** Los AI tutors 2026 son chat con piel: ninguno tiene sesión larga con memoria estructurada visible (anexo 2).
- **Cuando alguien resuelve el escritorio del estudiante para un dominio, se vuelve el estándar de su comunidad** (medicina: Anki+AMBOSS; japonés: Migaku/Yomitan) — y todo ese ecosistema serio ya reparte los roles así: desktop para el trabajo profundo, móvil para el repaso en movimiento (anexos 2, 4).
- **El usuario expulsado existe y paga**: pasó A2/B1, Duolingo lo castiga con energía/anuncios, Anki le exige paciencia técnica que no tiene; hoy vive en un Frankenstein de 3 apps y paga $10-15/mes sin culpa cuando le respetan el tiempo (anexo 4).
- **El único dato duro de rendimiento favorece al desktop**: Lingvist midió 25% más tarjetas por sesión y 30% más aprendizaje en web que en móvil (anexo 1).
- **Deudas de evidencia declaradas** (no se esconden): la demanda multi-tema está inferida del comportamiento, no articulada como pedido; y el corpus propio no tiene papers desktop-vs-móvil — el caso se sostiene en CLT + accesibilidad + mercado, y se falsará con telemetría propia (§2, §9).

Klara puede reclamar lo que nadie: motor serio + producto editorial + herramientas en función de (tema × perfil) + anti-gamification constitucional. El escritorio es donde ese reclamo se vuelve visible.

## 2. La tesis, enmendada por la evidencia

**Decisión original de Samuel (2026-08-10):** el escritorio es el modo de estudio profundo, no la app móvil ensanchada. **Esa decisión queda en pie.** Lo que la sesión adversarial y el corpus propio enmendaron es el *mecanismo* (acta, resoluciones 1-2):

> **El escritorio estructura la sesión larga como un protocolo — un foco dominante, profundidad a demanda, teclado de primera clase, tiempo externalizado — no como un lienzo con más cosas a la vez.**

- **La simultaneidad por defecto está contraindicada por la evidencia propia**: expertise reversal (la misma ayuda estorba al experto), monotropismo (la sesión larga es posible POR el foco en túnel), gloss redundante = carga extraña, texto+texto = el caso más débil del multimedia (anexo 5 §1). El segundo panel existe como **opción colapsable/on-demand con fading gobernado por el perfil** — jamás layout por defecto. La invocación (tap/atajo) es además señal para el perfil: un panel persistente mataría ese canal probatorio.
- **La sesión es un protocolo** (anexo 5 §3): pretest al abrir, organizer (mapa antes del territorio), bloques con testing embebido e interleaving, descansos, temporizador visible (TDAH/time blindness). El valor del escritorio es ESTRUCTURAR la hora, no llenarla.
- **Ontología resuelta** (acta, res. 2): el dispositivo es un **renderer** — el perfil es dueño de la forma (densidad, chunk, guía). Para que la promoción a `f(tema × perfil × dispositivo)` sea una decisión empírica y no un eslogan, **v1 instrumenta `device` en la evidencia** (columna aditiva en `study_sessions`; único cambio backend permitido en todo el proyecto).
- **Identidad: se profundiza, no se reemplaza** (segunda decisión de Samuel, intacta): papel/tinta, serif, UN bermellón, hairlines — llevados a su versión adulta.

## 3. Constitución, precedencia y barra

- **Identidad constitucional** (`docs/design/klara-v4/DESIGN.md` L3-5, L26, L30-51, L115, L147-151): serif `Source Serif 4` para lectura, sans `Inter Tight` para UI, mono para metadata; papel/tinta nunca puros; un acento; hairlines; sin mascota; sin gradientes/glow/glassmorphism.
- **Anti-Duolingo constitucional** (plan maestro L19-20) + anexo 5 §4: sin streaks, sin tiempo-en-app, sin nivel global de vanidad. El progreso honesto es **open learner model + calibración** (dominio por skill editable, confianza vs acierto).
- **i18n total** (plan maestro L24): 6 locales, mismo PR, `check-i18n.mjs`.
- **Regla de precedencia** (acta, res. 12): evidencia de aprendizaje > identidad visual > preferencia estética. Iris arbitra la EXPRESIÓN de la identidad, nunca contra la evidencia pedagógica.
- **Superseded** (acta, res. 13): la línea del plan maestro "Desktop hereda el frame centrado. El foco del rediseño es la app móvil" queda superseded por este documento.
- **Jurisprudencia de Iris** (v1 §3, vigente): micro-mono 10/12, gutters 22px (80px como suelo desktop per DESIGN.md L110), `--art-die` separado del acento, nada se recorta en silencio, una portada por página, lo interactivo no viste uniforme de metadata.
- **Barra 2026** (anexo 3, vinculante como referencia): jerarquía por color+espaciado antes que negrita (Perplexity); split de roles del serif (Anthropic); ancho de línea como parámetro (iA, `--maxw-read`); chrome contextual (Arc); estructura que se siente sin verse (Linear). Las 3 trampas — serif totalizante, vacío de museo, densidad fija para leer Y operar — son fallos de gate.

## 4. Estado medido del terreno (post-`c5a0faf`)

| Superficie | Hoy a 1440px | Fuente |
|---|---|---|
| Todo lo v4 (Inicio, Portada, Mapa, Perfil, auth, `/estudiar`) | 430px fijos + borde | `mobile3.css:10-11` |
| Landing pública | 430px fijos + borde | `landing.css:5,16` |
| LegacyShell (Module, NewStory, Settings, Practice, Speak) | crece a 1180px | `global.css:108-114` |
| Onboarding | único layout desktop real: grid `200px/1fr/280px` | `onboarding.css:48-67` |

**Activos a explotar:** gramática de teclado completa oculta en touch (`useSentencePractice.ts:544-577`: `→`/`Enter`, `←`, `Espacio`, `M`, `Esc`; `RecallReviewSession.tsx:57-66`: `1-4`; hint `.k-hint` oculto por `hover:none` en `sentence-view.css:569-576`) — en escritorio asciende a interfaz de primera clase, PERO exige un **modelo de propiedad de foco**: los listeners globales de un carácter asumen una superficie dueña de la pantalla; con paneles vivos, "¿quién es dueño de Espacio?" es arquitectura, no estilo. Tokens de escala casi vírgenes: `--t-display` 88px (1 uso real + 1 redefinición), `--maxw-read` 640px (1 uso), `--maxw-page` (2), `--shadow-*`; `tokens.css` no tiene ni una media query — listo para crecer sin romper. Pieles de sesión compartidas (`sentence-view/finish/recall-review/gender-review.css`) sirven al v4 Y al legacy. `pages.css`+`path.css` (~180 selectores) solo sostienen Module/NewStory/Settings. PWA sin nada de desktop (`vite.config.ts:8-33`).

## 5. Fronteras (resueltas en el acta — el agente no las re-decide)

- **Núcleo v1:** `/estudiar/:id` (standalone, `App.tsx:229-238`) + Repaso (fichas) — las pieles de sesión compartidas.
- **Speak: FUERA del v1** (una sola categoría — acta res. 3): su reskin F2.5 sigue pendiente sobre la misma piel; su escritorio se especifica después.
- **Semántica de "fuera" con CSS compartido** (res. 4): las pieles compartidas PUEDEN ganar breakpoints ≥1024px; las pantallas legacy que las consumen aceptan esos cambios de composición — y el smoke a 1180px entra al perímetro de verificación. "Fuera" = no se rediseñan su flujo ni su piel propia.
- **Module/NewStory/Settings: fuera del v1.** Absorberlas es decisión de scope futura (con Cassian), no del agente de diseño.
- **Onboarding + cuestionario F1.5: fuera, con veredicto** (res. 14): conservan su grid; se auditan en dark y anchos, no se rediseñan.
- **EL gate móvil** (formulación única — res. 5): la spec enumera la lista de archivos móviles; `git diff` sobre esa lista = **cero**, salvo excepciones registradas en la spec con justificación línea a línea. + smoke en iPhone. (Sin lenguaje píxel/byte.)
- **Frontera de viewport** (res. 7): desktop nace en **≥1024px con `pointer:fine`**; 431-1023 = el móvil centrado actual, explícito; tablet táctil ≥1024 = layout desktop con hints ocultos por la regla touch existente (que NO se toca); un resize que cruza el breakpoint cierra los paneles on-demand sin perder el estado de la sesión.
- **Dark: se audita, no se difiere** (res. 6): ya está vivo (toggle `Perfil.tsx:68` + `prefers-color-scheme` en `preferences.ts:69`); toda composición nueva se revisa en ambos temas desde el día uno.
- **Manifest PWA = perímetro móvil** (res. 15): es un artefacto único que muta lo que instala el iPhone; cualquier cambio es excepción registrada.
- **Backend: cero cambios**, con UNA excepción declarada: la columna `device` en `study_sessions` (§2). Dominio Course/F3, suscripción, racha, SEO/legal de la landing: fuera (deudas heredadas explícitas).

## 6. Lo que la spec debe contener (en este orden)

1. **La hora narrada.** El modelo de sesión ANTES del de composición: una sesión de estudio de escritorio contada minuto a minuto, implementando el protocolo del anexo 5 §3 (pretest, organizer, bloques, testing embebido, interleaving, descansos, temporizador). Sin esta narrativa, cualquier catálogo de layouts carece de criterio de selección.
2. **La composición.** Un foco dominante (columna de lectura, `--maxw-read` como parámetro à la iA); profundidad a demanda (gloss/ficha colapsables con fading gobernado por perfil — expertise reversal); qué evidencia produce cada invocación (el canal del tap no se pierde). Qué pasa a 1024, 1280, 1440 y en ventana a media pantalla.
3. **El modelo de propiedad de foco.** Zonas, dueño de cada tecla, la gramática existente como base. Palette de comandos: diferida salvo evidencia (Cassian). Territorio de Petra Haft — su review es obligatoria antes de cerrar la spec.
4. **El progreso honesto.** Open learner model en pantalla grande: dominio por skill editable, calibración confianza-vs-acierto, el porqué de la siguiente acción. Jamás streaks/tiempo-en-app (Goodhart).
5. **La landing desktop** (fase D2): audiencia y trabajo definidos (§0); mostrar el objeto real (la sesión, no un mockup genérico); nombrar para quién NO es; tipografía como hero; estreno de `--t-display` en UNA superficie.
6. **La navegación del shell** (fase D2+, con evidencia de D1): qué reemplaza a la TabBar en desktop. No bloquea D1 — `/estudiar` es standalone.

## 7. Fases y permission slip (Cassian, acta res. 11)

- **D1 (una semana):** `/estudiar` + Repaso a ≥1024px — columna de lectura, panel on-demand, teclado visible, temporizador. CSS nuevo detrás de breakpoint; lista móvil con diff cero. Ship viernes.
- **D2 (una semana):** landing desktop + pase de Repaso/Finish + decisión de navegación con la evidencia de D1.
- **D3+:** shell completo, absorciones legacy (con Cassian), Speak post-F2.5.

> **Permission slip:** se autoriza shippear un escritorio donde solo `/estudiar` tiene composición de escritorio real mientras landing, shell y legacy siguen en columna móvil una semana más — un evaluador verá esa mezcla — porque la tesis en manos de usuarios el viernes vale más que la coherencia total en octubre. Rechazarlo debe ser explícito; el default no puede ser "más spec".

## 8. Proceso y gates

1. Spec de la fase D1 solamente (el resto del territorio: direcciones, no specs).
2. Review de spec: **Serrano** (gaps/estados de fallo) + **Petra Haft** (gramática de interacción — obligatoria).
3. **Gate visual antes del plan** (res. 10): mockup/artefacto de la composición aprobado por Iris ANTES de escribir el plan de implementación — la lección del v4: el mockup dictaba el diseño.
4. Plan (`writing-plans`) → ejecución subagent-driven con Iris por pantalla.
5. Gates mecánicos por PR: diff-cero sobre la lista móvil, `check-i18n` (6 locales), a11y de foco/teclado real, auditoría dark, smoke matrix (1024 / 1280 / 1440 / 1920 / ventana ~720px + 1180px legacy + iPhone).

## 9. Criterios de éxito (falsables)

1. **EL criterio (conductual):** a 4 semanas del ship de D1, la mayoría de los minutos de sesión larga (>20 min) de los usuarios activos ocurre en escritorio — medible con la columna `device` de §2. Si no migran, la tesis se revisa con esos datos.
2. **Piso de teclado:** una sesión completa de `/estudiar` operable sin tocar el mouse (entrar→leer→audio→revelar→calificar→salir), verificada por checklist.
3. **Móvil intacto:** diff cero sobre la lista enumerada + smoke iPhone verde.
4. **Dark auditado** en cada composición nueva (checklist de Iris cubre ambos temas).
5. **i18n:** 6 locales, cero strings duros.

*(La calidad estética no es criterio: es el gate de Iris. Un criterio que un gate cumple por construcción no mide nada — Serrano F9.)*
