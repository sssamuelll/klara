# Anexo 8 — Mnemo como producto: estética, filosofía y estado

*Investigación web 2026-08-11 (subagente) + lectura directa de capturas.*

## Qué es, en su voz

App de estudio gratuita y open source (notas + flashcards con repetición espaciada + mapas mentales + IA local) para estudiantes y *lifelong learners*. Su pitch: **"No subscriptions. No ads. No tracking. Ever."** Frente a Anki no promete mejor algoritmo: promete **todo el estudio en un lugar, sin que nadie viva de tus datos**, con un editor de notas de verdad.

**Dato de estado que cambia el cálculo: mnemo está migrando de .NET/Avalonia a React + Photino**, con las descargas pausadas hasta la versión nueva. El lenguaje visual que nos interesa **no depende de ser app nativa** — el propio mnemo lo está portando a React.

## Escala real del proyecto

63 estrellas, 8 forks, prácticamente **un solo contribuidor de peso**, 1 issue abierto, sin releases desde v0.6.5 (junio 2025) aunque los commits siguen. Gobernanza founder-led. Sin huella pública: ni Show HN, ni hilos de Reddit, ni reviews. **No es un gigante: es alguien con muy buen gusto trabajando solo** — alentador y advertencia a la vez. Su roadmap declarado (juegos, video-lecciones locales, tienda de extensiones) todavía no existe.

`BRAND.md` **no contiene nada de diseño**: es puramente legal (marca registrada, qué puede hacer un fork). La identidad hay que leerla en las pantallas.

## Las pantallas (lectura directa)

**Sesión de repaso** — la más radical y la más instructiva:
- Barra superior de una línea: cerrar · nombre del mazo · chip "Review" · `1/5` con barra de progreso finísima · ajustes.
- Después, nada. Blanco. Una tarjeta centrada con hairline y esquina redondeada; la pregunta en cuerpo mediano; dos tags diminutos.
- Un único elemento de alto contraste: botón negro de ancho completo con **el atajo dentro del propio botón** (`Show answer` + chip `Space`).
- Bajo el botón, una línea gris: `E edit · Ctrl Z undo · Esc end session`.
- **Cero estadísticas durante el estudio.** Nada compite con la pregunta.

**Notas** — el registro de construcción:
- Rail de iconos ultraestrecho (conmutador de módulo) + sidebar con árbol: **Medicine, Biology, Physics, Engineering, Architecture, History, General** — el multi-tema son carpetas con emoji.
- Pestañas tipo navegador (varias notas abiertas), breadcrumb, buscador con `Ctrl P` visible.
- Cuerpo con negritas, resaltados amarillos, callouts, superíndices químicos.
- Banner de gradiente decorativo y emojis — **esto Klara lo tiene prohibido**.

**Dashboard (versión Avalonia, `showcase.png`)** — tarjetas sin borde sobre gris frío, un acento coral, densidad bajísima… y **"Day Streak 2"**, **"Minutes studied 0/30"**, más `streak.svg` y `xp.svg` en los assets. El modelo de progreso que la constitución de Klara condena por Goodhart.

## Los 8 rasgos del "extremadamente limpio"

1. Chrome reducido a barras finas monocromas; 80-90% de la pantalla vacía.
2. Una pantalla, una tarea — el repaso no muestra nada más que la tarjeta.
3. Color reservado para contenido semántico (tags, nodos), nunca para decorar el chrome.
4. Dos tipografías con roles: serif de display en títulos, sans geométrica en el chrome.
5. Un único elemento de alto contraste por pantalla.
6. Paneles contextuales flotantes por invocación, no toolbars fijas.
7. Paleta de acento curada y limitada (6 swatches), no sistema expansivo.
8. Atajos expuestos como hints tipográficos discretos, no como botones.

## Lo que la calma de mnemo esconde (Richter)

**Su limpieza está pagada en gran parte por la ausencia del LLM.** Local-first, monousuario, sin generación: sin latencia, sin costo por acción, sin estados de carga, sin fallo del modelo, sin job asíncrono, sin cuota. Klara tiene que renderizar *"Klara está leyendo tu tema…"*, el fallo y el reintento. **No se puede copiar la calma y quedarse con el generador.**

## La lección de composición (Cassian)

> La limpieza de mnemo no es su paleta: es su **conteo de sustantivos**. Se puede tener papel/tinta cálido, serif editorial y un bermellón, y sentirse tan limpio como mnemo, si la pantalla tiene tres cosas. Se puede copiar su gris frío exacto y sentirse abarrotado con nueve.

**La identidad de Klara no está en conflicto con la limpieza pedida. El scope sí.**

## Legibilidad de capacidad (Voronov)

Mnemo puede verse vacío porque mnemo **es** semánticamente vacío: nunca lee su contenido, agenda blobs opacos. Una superficie neutra promete un contenedor. La identidad de Klara (papel/tinta, serif, hairlines, un bermellón) es la declaración visual de un sistema que **tiene una opinión sobre el contenido**. Adoptar la carcasa desnuda sobre un motor que sí opina hace que la interfaz deje de decir la verdad sobre lo que el sistema sabe.
