# Acta — Sesión adversarial ronda 3: mnemo, multi-tema y "otra aplicación" (2026-08-11)

**Objeto:** el encargo nuevo de Samuel — escritorio *entre lo que tenemos y mnemo* (más cerca de mnemo en limpieza), **funcionalidad distinta del móvil (otra app, complementaria)**, y **multi-tema** ("aprender cualquier cosa").
**Roster:** Lyra Sage · Voronov · Richter · Serrano · Cassian. **Evidencia:** reasonix ×2 (ingeniería inversa de mnemo, 865K tok / $0.0165; inventario multi-tema de Klara, 1.1M tok / $0.0212) + investigación de producto (anexos 6, 7, 8).
**Axiom-0 no se invocó:** los cinco convergen en el diagnóstico; la única diferencia fue de secuencia táctica, resuelta por Samuel.

## Veredictos

| Agente | Veredicto en una línea |
|---|---|
| **Lyra** | Multi-tema no expande el foso, **te saca de él**: el eje de voz en la nube y el léxico de género (90.993 entradas) son lo único que mnemo estructuralmente no puede copiar. Toda la velocidad histórica viene de fases con constraint *"cero migraciones"*; F3 serían 6-10 semanas de cirugía sobre datos vivos, algo en lo que Klara nunca se ha medido. Asignación propuesta: 45% perfil consumido / 35% cerrar F2 / 20% sondas / 0% escritorio. |
| **Voronov** | **Ley del alcance semántico**: la generalidad de dominio es el inverso exacto de la profundidad con que el sistema lee su contenido. La generalidad de mnemo no es un logro: es una **abstención** (nunca lee sus blobs). Los ~35 archivos con `target_language` **no son deuda: son el producto escrito**. `tipo` no es atributo del curso, es el nombre del motor que sabe leer ese contenido. "Curso" es una proyección de la escolaridad: sin institución certificadora queda **teatro curricular**. |
| **Richter** | Deriva, no evolución: la pregunta del plan v4 sigue abierta y cada vencimiento se absorbe con una superficie nueva. **"Ya está adelantado" está invertido**: los docs prometen más de lo que el código tiene — se está leyendo el plan propio como si fuera estado. El perfil no está solo sin consumir: tiene la **aridad equivocada** (`user_id` PK ⇒ f(perfil), no f(tema × perfil)). Y el perfil sigue sin consumo *precisamente porque el consumo es donde la tesis puede fallar*. |
| **Serrano** | **6 BLOCKERS**: clase de artefacto sin declarar (auth solo cookie-JWT `samesite=strict`); la tesis deroga la res. 2 y hace insatisfacible el gate diff-cero; el usuario desktop-only nace corrupto (`target_language` NOT NULL); SRS global sin scoping ni idempotencia (dos clientes = corrupción del ledger); **el criterio de éxito es infalsable** — `study_sessions` tiene un solo escritor, `speak_finish.py:80`, y Speak está fuera de alcance; dos documentos normativos en `main` sin marca de precedencia. |
| **Cassian** | El motor genérico **ya existe en prod** (FSRS desde `0018`; `schedule_next_review`/`project_intervals` son funciones puras). Lo que falta es autoría. Core shippeable: **"el taller"** — ruta standalone ≥1024px, pegar/escribir texto → tarjetas con etiquetas libres → repaso con el FSRS existente. Tres sustantivos: tarjeta, etiqueta, cola. **La limpieza de mnemo no es su paleta, es su conteo de sustantivos.** |

## Hallazgos técnicos que no dependen de esta decisión

1. **La FK que define el techo** (Richter): `user_cards.vocab_item_id → vocab_items.id NOT NULL`. Klara **no puede agendar nada que no sea un lexema**. El bloqueo #1 del multi-tema es una línea de DDL, no una fase.
2. **`vocab_items` es global entre usuarios** (unique `(lemma, language, pos)`, sin `user_id`): correcto para idiomas, contaminación cross-tenant para material autoral.
3. **El canal de pronunciación no tiene loop de aprendizaje** (Voronov): el Optimizer solo entrena con recall, y la escalera del otro canal está clavada en `srs_engine.py:135-139`. Media medición del producto no aprende. **Bug real, hoy, en alemán.**
4. **El perfil está construido y no lo lee ningún prompt**; y su aridad es global, no por tema. `course_learner_overlay` nunca se construyó.
5. **`study_sessions` solo lo escribe Speak** — el criterio conductual del kickoff v2 medía la superficie excluida.
6. **Cero offline**: el service worker solo cachea Google Fonts. "El escritorio construye" sin durabilidad de escritura pierde trabajo en un corte de red.

## Resoluciones

1. **El encargo se acepta acotado, no rechazado.** Se construye el escritorio con funcionalidad divergente y estética limpia — vía **conteo de sustantivos**, no vía cambio de identidad. Papel/tinta, serif y bermellón **se conservan** (resuelve el arbitraje que Serrano marcó sin árbitro: no hay conflicto real entre el encargo y la constitución).
2. **Multi-tema entra SIN entidad `Course`** (lección de mnemo: la generalidad viene de no cablear la taxonomía). Etiquetas libres, no jerarquía, no `tipo`.
3. **Aislamiento total del dominio alemán**: tablas nuevas `study_cards` y `study_card_reviews`. Nada entra a `vocab_items`. F3 queda diferida como proyecto aparte, no como precondición.
4. **Un solo scheduler**: `srs_engine` se parametriza con un `Protocol` de ~6 líneas. Dos implementaciones de FSRS que derivan es el peor resultado posible.
5. **La telemetría se corrige**: `device` va en `study_card_reviews` (tabla que sí escribe la superficie nueva), no en `study_sessions`.
6. **Anti-gamification sigue siendo constitucional**: nada de streak, XP ni minutos-en-app cruza desde mnemo. El dashboard de widgets es su vehículo — se descarta.
7. **Lo cortado explícitamente**: editor de bloques, mapa mental, dashboard de widgets, `IModule`/plugins, paquetes `.mnemo`, import de Anki, command palette (con una concesión de costo cero: los atajos de la pantalla nueva viven en un array, para que la palette futura sea leer ese array).
8. **Regla de decisión comprometida por adelantado**: tras el fin de semana de dogfood, **≥20 tarjetas creadas → continúa; <20 → se congela y la pregunta multi-tema vuelve a Lyra con datos**.
9. **Convivencia declarada con fecha y dueño**: dos sistemas de tarjetas conviven; revisión a 4 semanas, dueño Lyra. Sin fecha y sin dueño es cómo nacen las bases de datos que nadie entiende.
10. **Se deroga la res. 2 del acta previa** ("dispositivo = renderer") en lo que respecta al taller: el escritorio SÍ tiene una función que el móvil no tiene (autoría). El gate diff-cero se conserva y se cumple **por construcción** (ruta standalone, archivos nuevos, una línea en `App.tsx`).
11. **Waivers con rastro**: Petra Haft se difiere para el taller (una superficie a la vez, keybinds reusados) y vuelve a ser obligatoria cuando entre `/estudiar` a ≥1024. **Iris se mantiene** (gate visual antes del plan). **Serrano se mantiene** (el taller tiene estados de fallo reales: parseo, duplicados, vacío, huérfanas).
12. **Decisión de Samuel (2026-08-11): taller primero, consumo del perfil en paralelo.** Son carriles disjuntos en archivos: el taller toca tablas/rutas/CSS nuevos; el perfil toca `llm/prompts.py`, `story_gen.py`, `learner_synthesis.py`.
13. **Este documento y el KICKOFF v3 son normativos** desde hoy; el plan maestro v4 queda **superseded en su línea** "Desktop hereda el frame centrado / el foco del rediseño es la app móvil", y sus promesas de F3/F4 se marcan explícitamente como **no implementadas** para que ninguna spec futura las cite como estado.

## Deudas de evidencia (declaradas, no escondidas)

- Demanda multi-tema: **inferida del comportamiento, no articulada**. El fin de semana de dogfood es la primera evidencia de primera mano.
- La pregunta de Lyra sigue viva y ahora tiene instrumento: *el único usuario con datos densos eres tú; ¿qué te hace pensar que un tema nuevo retendrá a quien el alemán no retuvo?*
- Offline / durabilidad de escritura: fuera del taller v1, declarado; si el dogfood produce pérdida de trabajo, sube a blocker.
