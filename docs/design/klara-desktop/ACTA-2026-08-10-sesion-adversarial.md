# Acta — Sesión adversarial sobre el kickoff desktop (2026-08-10)

**Objeto:** el KICKOFF.md v1 (PR #160, mergeado). **Roster:** Serrano, Richter, Voronov, Cassian + 4 investigadores de mercado (anexos 1-4) + destilado del corpus propio por reasonix (anexo 5). **Resultado:** KICKOFF v2 (PR #161). Axiom-0 no se invocó: los veredictos convergen, no se contradicen.

## Veredictos en una línea

| Agente | Veredicto |
|---|---|
| **Voronov** | Error de categoría: el kickoff predica del instrumento (escritorio) una propiedad del acto (estudio profundo). Solo hay dos posiciones legales: dispositivo = renderer, o dispositivo = tercer argumento de f(tema × perfil × dispositivo) instrumentado; el v1 afirmaba lo segundo instrumentado como lo primero. El action space tiene herramientas, no composiciones — el bandit no puede atribuir crédito a superficies simultáneas; el gloss persistente además mata el canal probatorio del tap. |
| **Richter** | "Inventario impecable y un decreto, no un caso." La pregunta que las 8 esquivaban: ¿la simultaneidad es pedagógicamente correcta o solo espacialmente posible? Faltan: narrativa minuto-a-minuto de la hora, modelo de propiedad de foco para el teclado, la franja 431-1023, un criterio conductual falsable, audiencia/trabajo de la landing, y un gate visual entre spec y ejecución (la lección del v4: el mockup existía ANTES del plan). |
| **Serrano** | 3 BLOCKERS: Speak en dos categorías de alcance a la vez; "dejar fuera" ficticio para pantallas cuyo cuerpo es CSS compartido con el núcleo; tres formulaciones no equivalentes del constraint móvil. HIGHs: dark mode ya está VIVO (toggle en Perfil + `prefers-color-scheme`) — "diferir" no existe; la spec se escribiría sobre sustrato que F2 sigue moviendo; criterios de éxito no falsables; frontera sin estados de borde (tablet táctil, resize, 431-1439). |
| **Cassian** | Core shippeable: `/estudiar` a ≥1024px — es standalone, la pregunta de la TabBar no está en el camino crítico. Estudio primero, landing semana 2 ("nunca shippees el anuncio antes del producto"). Gold-plating a diferir: palette, dark-como-entregable, absorción legacy, 88px sistémico. Plan de viernes + permission slip. |
| **Mercado (anexos 1-4)** | Ningún mainstream diseña para desktop; Lingvist midió 25% más tarjetas/30% más aprendizaje en web; el hueco = motor serio + producto que no da miedo abrir; el expulsado paga $10-15/mes y hoy vive en un Frankenstein de 3 apps; los AI tutors son chat con piel. Demanda multi-tema: inferida del comportamiento, NO articulada — hueco de evidencia declarado. |
| **Corpus propio (anexo 5)** | La evidencia ENMIENDA la tesis: expertise reversal como interruptor maestro; monotropismo + "too much is too much" → un foco dominante, segundo panel solo colapsable/on-demand con fading; texto+texto es el caso más débil; la sesión larga es un protocolo (pretest, organizer, testing embebido, interleaving, descansos, tiempo externalizado), no un lienzo; progreso = open learner model + calibración, jamás streaks; cero papers desktop-vs-móvil en el corpus. |

## Resoluciones (finding → cambio en v2)

1. **La tesis se enmienda** (Voronov + Richter + anexo 5): "superficies simultáneas" deja de ser definicional. Tesis v2: *el escritorio estructura la sesión larga como protocolo, con un foco dominante, profundidad a demanda y teclado de primera clase*. La simultaneidad queda como capacidad opt-in gobernada por el perfil, con fading — nunca layout por defecto.
2. **Ontología resuelta** (Voronov): dispositivo = **renderer** en v1; el perfil es dueño de la forma. Se instrumenta `device` en la evidencia (columna aditiva en `study_sessions`) desde v1, para que la promoción a tercer argumento sea una decisión empírica futura, no un eslogan.
3. **Speak: una sola categoría** (Serrano B1): FUERA del núcleo v1 — su reskin F2.5 sigue pendiente sobre la misma piel (Serrano F8); el escritorio de Speak se especifica después.
4. **Semántica de "fuera" con CSS compartido** (Serrano B2): las pieles de sesión compartidas PUEDEN ganar breakpoints ≥1024px; las pantallas legacy que las consumen aceptan esos cambios de composición, y el smoke a 1180px entra al perímetro de verificación. "Fuera" = no se rediseñan flujo ni piel propia.
5. **Gate móvil único** (Serrano B3): lista enumerada de archivos móviles en la spec; `git diff` sobre esa lista = CERO salvo excepciones registradas en la spec con justificación. Se abandona el lenguaje píxel/byte.
6. **Dark**: ya está vivo → toda composición nueva se AUDITA en ambos temas desde v1. No es diferible.
7. **Frontera declarada**: desktop ≥1024px con `pointer:fine`; 431-1023 = móvil centrado actual (explícito); tablet táctil ≥1024 = layout desktop con hints ocultos por la regla touch existente (que no se toca); resize que cruza el breakpoint cierra paneles on-demand sin perder estado de sesión.
8. **Criterio conductual falsable** (Richter): las sesiones largas de Samuel migran al escritorio, medible con la columna `device`. Más piso operable de teclado (sesión completa sin mouse). Los juicios estéticos quedan en el gate de Iris (proceso), no como criterios.
9. **Narrativa antes de composición** (Richter): la spec abre con la hora de estudio narrada minuto a minuto, con el protocolo del anexo 5.
10. **Gate visual** (Richter): mockup/artefacto aprobado por Iris ANTES del plan de implementación — la lección del v4.
11. **Fases** (Cassian): D1 = `/estudiar` ≥1024px; D2 = landing + navegación con evidencia; D3+ = absorciones. Permission slip en el kickoff.
12. **Precedencia** (Richter/Serrano): evidencia de aprendizaje > identidad visual > preferencia estética. Iris arbitra la EXPRESIÓN de la identidad, nunca contra la evidencia pedagógica.
13. **Plan maestro**: la línea "Desktop hereda el frame centrado. El foco del rediseño es la app móvil" queda **superseded** por el kickoff v2.
14. **Onboarding**: fuera del v1 con veredicto explícito — conserva su grid (único layout desktop preexistente); se audita en dark/anchos, no se rediseña.
15. **Manifest PWA** = perímetro móvil; cualquier cambio es excepción registrada (artefacto único que muta lo que instala el iPhone).
16. **Corrección de inventario** (Serrano F15): `--t-display` tiene 1 uso real + 1 redefinición + 1 comentario (no "3 usos").

## Deudas de evidencia declaradas

- Demanda multi-tema articulada: pase de research con acceso directo a Reddit antes de comprometer messaging público (anexo 4).
- Desktop vs móvil como superficie: el corpus no lo cubre; el caso se sostiene en CLT + accesibilidad + datos de mercado (Lingvist), y se falsará con la telemetría propia (`device`).
