# Contrato del vocabulario — `k-*`

Este documento fija los nombres, los estados y las medidas de los 17 átomos con los que se escriben todas las pantallas de Klara; después de esto ninguna hoja de pantalla define un botón, una tarjeta, una fila ni una barra propios.
Va dirigido a quien implemente la hoja de estilo y a quien migre cada pantalla: lo que no está aquí no existe, y lo que aquí se llama de una manera se llama así en el `.tsx`.
Lo implementa `frontend/src/styles/sistema.css`, una hoja nueva que se importa en `frontend/src/main.tsx` justo después de `./styles/global.css` (main.tsx:6) y antes que `native.css` (main.tsx:7).
Lo muestra `docs/design/klara-sistema/hoja.html`, que carga solo `global.css` + `sistema.css` (hoja.html:17-18): si un átomo necesita `mobile3.css` para verse bien, la hoja lo delata.
**Estado a 4 de septiembre de 2026: la migración está terminada en lo que era su encargo.** Las **catorce** hojas de pantalla que había están borradas (mobile4, mobile3, recall-review, taller, speak, sentence-view, finish, onboarding, auth, landing, perfil-aprendizaje, gender-review, path y pages), y `sistema.css` es la única hoja de pantalla del proyecto. Lo que queda del CSS viejo es el cascarón de escritorio de `global.css:87-254`, que **no se puede borrar todavía y no por CSS**: es el único sitio desde el que se llega a Práctica y a Hablar. Ver la decisión 18.

Lo verifica `docs/design/klara-sistema/hoja.check.mjs`: cero colores literales en `sistema.css` (hoja.check.mjs:66-70), los estados obligatorios del §5 (hoja.check.mjs:33-50), objetivos táctiles ≥44px (hoja.check.mjs:96-101), cero scroll horizontal y cero animaciones bajo `prefers-reduced-motion` (hoja.check.mjs:124-133), en los dos temas y en dos anchos.

---

## Gramática

1. **Namespace y nombres.** Todo bloque empieza por `.k-`. Los nombres son en inglés porque es la generación que ya sobrevivió: `k-btn`, `k-btn--ghost`, `k-chip`, `k-level`, `k-error` y `klara-mark` se conservan textuales, con sus consumidores intactos.
2. **BEM-lite.** Bloque `.k-x`; elemento `.k-x__y`; variante estática (la decide el que escribe el markup y no cambia en ejecución) `.k-x--z`. Un elemento nunca cuelga de otro elemento: `.k-card__word`, nunca `.k-card__face__word`.
3. **Estado siempre por atributo, nunca por clase.** Enumerado: `data-state="…"`. Booleano: `data-<flag>="true"`. Se reutilizan los atributos que el código ya emite —`data-active`, `data-selected`, `data-on`, `data-done`, `data-speaking`, `data-score`— para que la migración no toque lógica de React, solo markup. **Criterio de desempate**, porque hoy «seleccionado» se escribe de tres maneras: navegación y foco de lectura → `data-active` (pestaña, ítem de menú, palabra que suena); elección dentro de un grupo de opciones → `data-selected` (chip) o `data-state="selected"` cuando el átomo ya tiene un enumerado (fila); ciclo de vida de la pieza → `data-state` (`pending`/`now`/`done`/`locked`/`mastered`, `front`/`back`). Un mismo atributo puede significar cosas distintas en átomos distintos —`data-done` es «segmento hecho» en la barra y «ya sonó» en el botón redondo— y eso se declara en cada átomo, no se resuelve renombrando.
4. **Reduced motion.** `sistema.css` apaga sus propias animaciones con `animation: none` dentro de `@media (prefers-reduced-motion: reduce)`, y en cada caso conserva la información en estático: la marca que habla mantiene su halo fijo, el botón de grabar mantiene su anillo fijo, la hoja inferior aparece ya en reposo. No se depende de la regla global de `recall-review.css:333-337`, que hoy se cuela en todas las rutas por accidente y además mata `--dur-breath`.
5. **Radios pequeños.** El techo normal es `--r-md` (8px). Tres excepciones, y solo tres: el chip (`--r-pill`), el botón redondo (50 %) y la hoja inferior (`--r-lg`, solo en las dos esquinas de arriba). La píldora de `.qcard__mic` (finish.css:637) y las de `.k-tool--mic` (sentence-view.css:245) y `.rr-flip` (recall-review.css:225) se traducen a `.k-btn` normal, con `--r-sm`.
6. **Objetivos táctiles ≥44px en todo lo tocable**, incluida la marginalia en mono. El patrón es `min-height: 44px` (y `min-width: 44px` donde el rótulo sea corto) con `padding` compensado por `margin` negativo, nunca agrandar el dibujo. El precedente vivo es `mobile3.css:143` —`.m3-dock .estadoK button{padding:8px 14px;margin:-8px -14px}`, **no** la línea 139, que es la safe-area de `.m3-fb`— y **su aritmética no se hereda**: 8px de padding sobre mono de 14px da 30px de alto, o sea no cumple. Cada átomo rehace la cuenta contra `hoja.check.mjs:96-101`, que mide ancho **y** alto. Única excepción razonada del sistema: el **ancho** de `.k-word` (átomo 14), que es el ancho de la palabra.
7. **Compatibilidad hacia atrás, con cuatro cambios declarados.** `k-btn` (42 usos), `k-btn--ghost` (17), `k-error` (15), `k-chip` (2), `k-level` (1) y `klara-mark` (1) mudan su definición de `global.css` a `sistema.css` sin tocar ningún `.tsx`. Se ven igual salvo: (a) dos estados del botón, mejora deliberada — `:disabled` **se atenúa por primera vez** (global.css no lo declara en ninguna línea) y `:active` pasa de `translateY(0)` (global.css:312) a `scale(0.985)`; (b) el botón baja de ≈47 a **44px** de alto (padding 12px en vez de 14px), para que el sistema tenga exactamente dos alturas de control, 44 y 56 (resuelve la objeción 9); (c) el chip sube de ≈33 a 44px de alto por §7.2; (d) `k-error` baja de 12 a 11px, el escalón mono único (resuelve la objeción 8). Ninguno de los cuatro mueve un layout. `k-btn--accent` **está muerta hoy** (0 usos: `auditoria-css.md` cuenta dos muertas en `global.css`, `k-rule` y `k-btn--accent`), así que no entra en la lista de compatibilidad: el átomo la resucita, y de paso su `#fff` (global.css:329) pasa a `var(--on-accent)`. `k-link`, `k-hairline`, `k-spinner`, `k-mono` y `k-serif` se quedan en `global.css` porque no son átomos del §5.
8. **Bilingüe siempre.** Alemán como contenido (serif), interfaz en el idioma del usuario (sans para controles, mono para marginalia). Toda fila, ficha, chip y campo tiene que sobrevivir a `Bundesausbildungsförderungsgesetz`: los títulos parten palabra (`overflow-wrap: anywhere`), la marginalia de la derecha no se encoge (`flex-shrink: 0`).
9. **Reparto tipográfico, con sus tres excepciones escritas.** Serif = contenido y titulares (cursiva para la voz de Klara). Sans = controles y campos. Mono = marginalia, en versalitas con `letter-spacing: var(--tracking-mark)`. Las excepciones son tres, y ninguna más: (a) `.k-btn--text` es un control en mono, por la decisión 3 del orquestador —queda registrado como objeción abierta al final—; (b) `.k-error` y `.k-note--mono` son mono **sin** versalitas, porque un párrafo en versalitas no se lee, y `.k-error` conserva además su `0.02em` por la regla 7; (c) `.k-field--area` es un campo en serif, porque lo que se teclea ahí es el pasaje alemán, o sea contenido —es el valor vivo en `taller.css:145` y `onboarding.css:565`; (d) `.k-field__hint` habla en el registro de la nota al margen (serif itálica `--t-meta`): es Klara diciéndote qué pasó, no un metadato.
10. **Un solo escalón mono: `var(--t-mono)` = 11px.** Es token nuevo en `tokens.css` (junto a `--t-mark` y `--t-meta`); en `sistema.css` la marginalia nunca escribe `11px` literal, escribe `var(--t-mono)`. Toda la marginalia del sistema mide eso con `--tracking-mark`; los 10px de `m3-top` (mobile3.css:17), `m4-sec` (mobile4.css:9), `m3-tab .lbl` (mobile3.css:26), `qcard__leg` (finish.css:497), `m3-cefr .stop` (mobile3.css:73) y `m3-hero .tag` (mobile3.css:59) **suben**, los 12px de `m3-gloss` y de `k-error` **bajan**, y los `0.1em`/`0.12em`/`0.14em` sueltos de esas hojas se reemplazan por `--tracking-mark`. Sin excepciones. (Donde este documento dice «mono 11px» léase `var(--t-mono)`.)
11. **Cero literales de color.** `sistema.css` consume `var(--…)`; `color-mix()` sobre `var()` se permite; hex, `oklch()`, `rgb()` y `hsl()` sueltos, no. Las medidas usan token siempre que exista uno exacto (`12px` es `var(--space-3)`, `2px` de radio es `var(--r-xs)`, `14px` de cuerpo es `var(--t-mark)`); solo se escribe literal lo que ningún token cubre, y cada literal se justifica en su apartado **Medidas**.
12. **Independencia de hoja, y por eso el armazón también se declara.** Ningún átomo depende de `mobile3.css` ni de `mobile4.css` para verse bien. Cuatro átomos —`.k-scrim`, `.k-sheet`, `.k-tabs__menu` y `.k-card--anchored`— se posicionan en absoluto y hoy dependen de que `mobile3.css:10` `.m3-app` sea `position: relative`, así que `sistema.css` declara además trece piezas de armazón que **no son átomos** y que ninguna pantalla vuelve a escribir (las cuatro primeras salieron de la migración del cascarón; las tres siguientes, de la de lectura; las cuatro del taller; las dos últimas, de la de Hablar):
    - `.k-app` — `position: relative; max-width: 430px; margin: 0 auto; height: 100dvh; display: flex; flex-direction: column; overflow: hidden; background: var(--paper)`, y `:root{--tb:58px}`. Es §7.3 (cero scroll) y §7.4 (430px) a la vez, y el ancestro posicionado que los cuatro necesitan.
    - `.k-page` — `flex: 1; min-height: 0; display: flex; flex-direction: column; padding: var(--space-4) 22px 14px; padding-top: calc(var(--space-4) + env(safe-area-inset-top)); overflow: hidden`. Y desde la migración 10, **el inset de abajo cuando es el último hijo del cascarón**: `.k-app > .k-page:last-child { padding-bottom: calc(14px + env(safe-area-inset-bottom)) }`. El de arriba lo pone siempre; el de abajo, solo entonces, porque en la app hay una barra de pestañas debajo que ya lo pone y escribirlo en las dos abría un hueco de más sobre ella. Los últimos hijos del cascarón son la puerta: la portada y las cinco de auth.
    - `.k-stage` — el pasaje de lectura: serif `calc(clamp(25px, 7vw, 30px) * var(--fscale, 1))`, `line-height: 1.5`, `letter-spacing: -0.005em`, `text-wrap: pretty`, `-webkit-line-clamp: 7` con `display: -webkit-box`, margen 0. Es donde viven `.k-word` y sus hermanos sin clase, y es el ancla del selector de puntaje (átomo 14). `--fscale` lo pone el `.tsx` en línea (EstudiarView.tsx:283). Lleva además `animation: page-in var(--dur-med) var(--ease-page) both` —el paso de página al cambiar de oración, que el `.tsx` redispara con `key={index}`—: `page-in` vive en `global.css:255` y bajo `prefers-reduced-motion` `--dur-med` es 0ms (`tokens.css:136`), así que no queda animación viva. Reemplaza la de `mobile3.css:27` `.m3-oracion`. Declara además `flex: 0 1 auto`, `padding: 0` y `text-align: start`, que no son decoración sino defensa: acotar el selector protege solo lo que este bloque **nombra**, y lo que no nombra sigue cayendo del `.k-stage` global de `sentence-view.css:81` (+ `:560`), que trae `flex: 1`, `padding: 8px 0` y `text-align: center`. Sin ellas el pasaje crecía hasta el pie y empujaba la glosa al fondo. Mueren con esa hoja.
    - `.k-wrap` — `display: flex; flex-wrap: wrap; gap: var(--space-2)`. El único contenedor de nube/rejilla del sistema; mata diez clases (`qcard__opts` finish.css:307, `fin-sched__list` :792, `fin-l1__list` :921, `kp-segments` pages.css:724, `kp-returns__list` :706, `kp-chips__row` :667, `snew__chips` :217, `ob-level__grid` onboarding.css:494, `taller .chips` taller.css:168, `m4-chips` mobile4.css:38). Las listas verticales son `<ul>` sin clase: `sistema.css` las resetea con `ul:has(> li > .k-row)` y el filete lo dibuja `.k-row`.
    - `.k-fill` — la zona de sesión que crece con lo que sobra y centra su contenido: `flex: 1; min-height: 0; display: flex; flex-direction: column; justify-content: center; padding: 0 28px; overflow: hidden`. Ahí viven `.k-stage` y su glosa `.k-note--mono`, o un `.k-spinner` mientras carga (`align-self: center`: el pasaje sí ocupa el ancho, el spinner no). Reemplaza `mobile3.css:26` `.m3-lect` y `:52` `.m3-cargando`.
    - `.k-dock` — el dock de transporte al pie de la sesión: `flex: 0 0 auto; padding: 10px 22px calc(20px + env(safe-area-inset-bottom))`. Dos hijos: `.k-dock__status` —`height: 18px` (**fijo**, no mínimo: es lo único que cumple lo que el bloque promete, porque con `min-height` el control de velocidad —44px compensados a 20 por su margen negativo— estiraba la línea en el estado «leyendo» y el dock cambiaba de alto a media sesión), `margin-bottom: 10px` y `display: flex` centrado en los dos ejes, como la `.estadoK` que reemplaza; dentro, una `.k-cap k-cap--center` **con el margen anulado** (`.k-dock__status .k-cap { margin: 0 }`: el átomo 6 trae 18px de aire de marginalia de página y, como el status no tiene ni relleno ni borde, ese margen se escapaba por colapso y empujaba el dock entero), cuyo texto vivo va en `.k-cap__count[data-tone="live"]` y cuyo control de velocidad es un `.k-btn k-btn--text`— y `.k-dock__row` —`display: flex; align-items: center; justify-content: center; gap: 18px`, la fila de `.k-rbtn`—. Reemplaza `mobile3.css:31` `.m3-dock` (+ `:50`, la safe-area), `:32` `.estadoK` (+ `:53` `.rec` y `:55`, el área táctil de la velocidad, que ahora la trae `.k-btn--text`) y `:33` `.fila`.
    - `.k-band` — la banda de respuesta que sustituye al dock cuando Klara dice algo: `flex: 0 0 auto; border-top: 1px solid var(--rule); padding: var(--space-4) 22px calc(20px + env(safe-area-inset-bottom)); min-height: 130px; display: flex; flex-direction: column; gap: var(--space-4)`. Dentro, una `.k-note` (el veredicto, `role="status"`) o una `.k-error` (`role="alert"`), y un `.k-wrap` con dos `.k-btn k-btn--block`. El aire lo reparte el `gap`, así que aquí la nota pierde su margen superior (`.k-band > .k-note { margin-top: 0 }`). Reemplaza `mobile3.css:43` `.m3-fb` (+ `:51`, la safe-area), `:44` `.nota` y `:46` `.acciones`.

    - `.k-desk` — **el segundo cascarón: la mesa ancha.** `.k-app` es el teléfono (430px, alto fijo, cero scroll); el taller es lo contrario y a propósito —dos columnas, mucho texto pegado, scroll normal—, así que no cabe en el primero. Por debajo de 1024px no se abre (`display: none`) y en su lugar habla `.k-desk__gate`; a partir de ahí es `display: grid; grid-template-columns: 200px 1fr; column-gap: var(--space-7); row-gap: var(--space-6); align-content: start; max-width: var(--maxw-page); margin: 0 auto; padding: var(--space-8) var(--space-6)`. Su `.k-topline` cruza las dos columnas (`grid-column: 1 / -1`) y trae su propio filete inferior, porque aquí la tira no cuelga de una página que ya lo dibuje. Reemplaza `taller.css:20-34` `.taller` y `:66` `.body`.
    - `.k-desk__gate` — la puerta: `max-width: var(--maxw-read); margin: 15vh auto 0; padding: 0 var(--space-5); text-align: center`, y `display: none` a partir de 1024px. Vive como hermano de `.k-desk` y no dentro, porque es lo que se ve **en vez** de la mesa. Reemplaza `taller.css:9` `.taller-gate`.
    - `.k-desk__rail` — la columna índice, separada por regla y no por vacío: `border-right: 1px solid var(--rule); padding-right: var(--space-5); display: flex; flex-direction: column; min-height: 0`. Su cinta abre el riel y pierde el margen de marginalia (`.k-desk__rail > .k-cap { margin-top: 0 }`), y su `<ul>` topa a la altura de la columna (`flex: 1; min-height: 0; overflow-y: auto`) en vez de a una constante. Reemplaza `taller.css:74-97`.
    - `.k-desk__col` — la columna de trabajo: `display: flex; flex-direction: column; gap: var(--space-4); min-width: 0`. Aquí el `gap` da el aire base **y los átomos que traen su propio margen de página —la cinta, el héroe, la nota— lo suman encima**, así que una sección se separa más que dos hermanos sin escribir un margen por pieza. Reemplaza `taller.css:141` `.col` (que era una regla vacía) y los cinco `margin-top` sueltos de esa hoja.

    - `.k-live` — **la columna que sí scrollea.** El cascarón no scrollea (§7.3), pero una conversación crece sin fin y no se puede recortar a siete líneas como el pasaje: `flex: 1; min-height: 0; width: 100%; overflow-y: auto; scroll-behavior: smooth`, dentro de `.k-fill`. Sus turnos son un `<ul>` sin clase (`.k-live > ul` lo resetea) y el aire entre ellos lo da el margen de la `.k-cap` que abre cada uno. Dos elementos: `.k-live__turn`, que solo existe para firmar el turno propio (`[data-who="you"]` → filete de 2px `--rule` a la izquierda, que es atribución y no marginalia), y `.k-live__said`, lo dicho, en serif a `var(--t-read)` —el mismo escalón del pasaje—. La palabra que el apunte comenta va anclada al contenedor (`.k-live__said [data-active="true"]`), como el puntaje del pasaje, porque sale `<span>` sin clase: aquí no se toca. Lo usa también el cierre de Hablar, para que la lista de palabras que vuelven a Práctica no se recorte. Reemplaza `speak.css:136-157` y `:204-213`.
    - `.k-presence` — **el escenario de Hablar**: disco, anillo de 44 varillas y la marca dentro, con cuatro estados por atributo (`data-state="idle|listening|thinking|speaking"`). Es armazón por lo mismo que `.k-stage`: es la superficie de una pantalla, no una pieza que se componga en otras. `position: relative; align-self: center; flex: 0 0 auto; display: grid; place-items: center`, y `--orbit` como radio del anillo. Elementos: `__disc` (`inset: 18%`, `--paper-2` con borde `--rule`; escuchando el borde toma `color-mix(in oklch, var(--accent) 30%, transparent)` y hablando el fondo pasa a `--accent-wash`), `__ring` (`inset: 0`, decorativo), `__tick` (posicionada con `transform: rotate(var(--a)) translateY(calc(-1 * var(--orbit)))`, con la varilla dentro) y `__think` (los tres puntos que ocupan el sitio de la K mientras piensa). Reemplaza `speak.css:83-134`.

    **Literales del escenario**, mudados de `speak.css`: **164px** de caja y **78px** de órbita (**132/62** comprimidos), **2×10px** de varilla, **8px** del punto y los retardos **180/360ms** de los tres puntos. La varilla cuelga **hacia dentro** desde la órbita, así que la caja solo tiene que medir el doble de `--orbit`; lo que estaba roto en la hoja vieja era el radio, que iba en línea en el `.tsx` mientras la consulta de ancho encogía la caja a 132, o sea el anillo se salía 12px por lado. Por eso es variable y por eso el disco va en porcentaje. Los dos ritmos (1s hablando, 0,7s escuchando) convergen en **uno**, `--dur-breath`: hablar y escuchar se distinguen por el color —tinta y acento—, no por la velocidad, y así ninguna duración queda en literal (§7.6).

    **Literales del armazón de escritorio**, mudados de `taller.css`: **200px** del riel, **1180px** (`--maxw-page`) de la mesa, **1024px** del umbral y **15vh** de la puerta. El `min-width: 0` de `.k-desk__col` no es cosmético: en una rejilla el `min-width: auto` de una celda deja que su contenido empuje la pista `1fr` más allá del contenedor, y la página entera se va de ancho.

    **Literales del armazón de sesión**, mudados de `mobile3.css`: **28px** de aire lateral del pasaje (`.m3-lect`), **10/22/20px** del dock, **18px** entre redondos, **18px/10px** de la línea de estado y **22px** de sangrado de la barra de sesión (`.k-app > .k-bar`, que además recupera el `flex: 0 0 auto` de `.m3-prog`: la barra cuelga del cascarón, no de `.k-page`, así que nadie más le pone ese aire). El único que **cambia** de valor es el alto mínimo de la banda, que sube de 124 a **130px**: es la suma del dock, y el dock creció —10 + 18 (estado) + 10 + 72 (el redondo grande, que el átomo 2 sube de 66 a 72) + 20—. Los dos pies son mutuamente excluyentes y tienen que medir lo mismo: es lo único que impide que el pasaje salte al cambiar uno por otro. Si cambia cualquiera de esos cinco sumandos, el 130 cambia con ellos. Con la banda mudada, `mobile3.css` se queda sin regla y muere entera.

    **Acotado al cascarón.** `.k-page` y `.k-stage` se escriben `.k-app > .k-page` y `.k-app .k-stage`, porque hoy existen otros dos con el mismo nombre y vivos: el `.k-page` de escritorio (global.css:246, diez pantallas) y el `.k-stage` de SentenceView (sentence-view.css:81). Sin el ancestro, el armazón los pisaría por orden de cascada (`overflow: hidden` sobre una página que scrollea). Por la misma razón el selector de puntaje del átomo 14 se escribe `.k-app .k-stage [data-score]`: sentence-view.css:132 ya subraya sus `.k-tok[data-score]` y sin el ancestro habría doble subrayado en la lectura de escritorio. Cuando esas pantallas migren y sus hojas mueran, el ancestro sobra pero no estorba. En pantallas de ≥520px `.k-app` conserva los dos filetes laterales de `mobile3.css:11`.
13. **Compresión en viewport corto (§7.3, no es preferencia).** Un solo bloque `@media (max-height: 720px)` en `sistema.css` sustituye a los dos que hay hoy (`mobile3.css:87-98`, `mobile4.css:51-58`): `.k-page` `padding: var(--space-3) 22px 10px` reponiendo el inset superior (el shorthand lo resetea), `.k-row` `padding: 7px 0`, `.k-cap` `margin: 10px 0 2px`, `.k-hero` `padding: var(--space-3) var(--space-4); margin-top: var(--space-3)`, `.k-note` `margin-top: var(--space-3)`, `.k-card__inner` `min-height: 288px`, `.k-field--area` `min-height: 96px`, `.k-dock` `padding-top: var(--space-2)` y `.k-band` `min-height: 0` (en 720px el mínimo de 130px se come la oración). **No se comprime ningún control**: §7.2 no admite excepción por altura de viewport, y por eso muere la compresión del chip a 40px de `perfil-aprendizaje.css:107`. El `clamp` del titular hace innecesario el recorte a 22px de `mobile3.css:93`, y `.k-hero__dek` deja de esconderse (`mobile4.css:58`).

---

## Tokens nuevos

Los **nueve** tokens nuevos ya están escritos en `tokens.css` (working tree, sin commit) — trece declaraciones contando las cuatro del tema oscuro; ningún valor preexistente cambió. La columna «de dónde viene» dice de qué hoja se mudó el valor, no dónde vive ahora.

| token | claro | oscuro | de dónde viene (hoja:línea) | quién lo usa |
|---|---|---|---|---|
| `--score-good` | `oklch(0.62 0.13 145)` (tokens.css:48) | el mismo (sin variante) | finish.css:363-516, sentence-view.css:132/485, mobile3.css:146 | `.k-stage [data-score="good"]`, `.k-chip__dot[data-tone]` |
| `--score-good-ink` | `oklch(0.42 0.12 145)` (tokens.css:49) | el mismo (sin variante) | finish.css:372/391/393 | marca de acierto y letra de la opción revelada (Pendientes, StoryFinish) |
| `--score-ok` | `oklch(0.74 0.13 80)` (tokens.css:50) | el mismo (sin variante) | finish.css:481/516, sentence-view.css:133/486, mobile3.css:147 | `.k-stage [data-score="ok"]` |
| `--score-bad` | `var(--accent)` (tokens.css:51) | hereda el acento oscuro | decisión 5: «mal» es el acento, no un cuarto color | `.k-stage [data-score="bad"]` |
| `--art-der` | `oklch(0.48 0.09 250)` (tokens.css:54) | `oklch(0.72 0.09 250)` (tokens.css:118) | mobile3.css:6-7 (mudado; la línea 6 ya es solo un comentario) | `.k-card__article`, `.k-row__n[data-gender]` |
| `--art-die` | `oklch(0.42 0.14 10)` (tokens.css:55) | `oklch(0.68 0.13 10)` (tokens.css:119) | mobile3.css:6-7 | idem |
| `--art-das` | `oklch(0.46 0.1 150)` (tokens.css:56) | `oklch(0.7 0.1 150)` (tokens.css:120) | mobile3.css:6-7 | idem |
| `--on-accent` | `var(--paper)` (tokens.css:59) | `var(--paper)` (hereda el papel oscuro) | global.css:329 (`#fff`) y mobile3.css:125 (`#fff`) | `.k-btn--accent`, `.k-rbtn--rec[data-on="true"]` |
| `--scrim` | `rgba(26, 24, 20, 0.35)` (tokens.css:60) | `rgba(0, 0, 0, 0.5)` (tokens.css:121) | mobile3.css:151-152 | `.k-scrim` (hoja inferior y menú de pestañas) |
| `--t-mono` | `11px` | el mismo | gramática 10: converge los 9–12px de once hojas | toda la marginalia mono del sistema (`k-cap`, `k-topline`, `k-tabs__lbl`, `k-row__n/__meta`, `k-bar__count/__stop`, `k-level`, `k-chip--static`, `k-note--mono`, `k-btn--text/__sub`, `k-field__label`, `k-error`) |

Notas de esta tabla:

- **Los tres colores de puntaje no se invierten en oscuro, y eso es deuda declarada, no descuido.** Hoy tampoco se invertían (finish.css, sentence-view.css y mobile3.css los llevaban literales), así que tokenizarlos no empeora nada y deja el arreglo en un solo sitio. Ver «Pendientes».
- `--art-*` **ya vivían en variables**, solo que fuera de `tokens.css`: es mudanza verificada, no invención (`mobile3.css:6` es hoy un comentario).
- El grano del papel (`global.css:31-32` y `:38-39`) sigue con sus cuatro `rgba` literales: §3.5 del brief lo declara intocable y `global.css` no es `sistema.css`, así que hoja.check.mjs no lo mira.
- Los siete porcentajes distintos de `color-mix` sobre `--accent` repartidos hoy entre speak, sentence-view, recall-review y finish (5/25/28/30/40/45/55 %) se reducen en `sistema.css` a **uno**: 30 % para el borde de «grabando».
- `--t-h2` **no lo consume ningún átomo**: `pages.css:776-781` lo redefine a 28px bajo `max-width: 600px`, o sea justo en el teléfono. Ver «Trampas conocidas».
- **La tinta de la marginalia es una sola: `--ink-3`.** Contadores, metas y cintas van en `--ink-3`; `--ink-4` queda para lo secundario dentro de otra pieza (el numeral de la fila, la barra `/` del contador, el hito no alcanzado) y para los estados apagados. Hoy el mismo contador aparece en `--ink-2`, `--ink-3` y `--ink-4` según la hoja.

---

## Los átomos


### 1. Botón — `.k-btn`

**Reemplaza:** global.css:296 `.k-btn` · global.css:311 `.k-btn:hover` · global.css:312 `.k-btn:active` · global.css:313 `.k-btn .arrow` · global.css:318 `.k-btn:hover .arrow` · global.css:320 `.k-btn--ghost` · global.css:325 `.k-btn--ghost:hover` · global.css:327 `.k-btn--accent` (muerta) · finish.css:41 `.fin-btn` · finish.css:61 `.fin-btn--primary` · finish.css:67 `.fin-btn--ghost` · finish.css:35 `.fin-arr` · finish.css:616 `.qcard__next` · finish.css:21 `.fin-back` · finish.css:749 `.fin-back--right` · finish.css:625 `.qcard__ghost` · finish.css:637 `.qcard__mic` · finish.css:591 `.qcard__gender-btn` · onboarding.css:203 `.ob-btn` · onboarding.css:229 `.ob-btn--lg` · onboarding.css:222 `.ob-btn__arrow` · onboarding.css:234 `.ob-link` · onboarding.css:249 `.ob-link--mute` · onboarding.css:254 `.ob-link__arrow` · onboarding.css:22 `.ob__exit` · sentence-view.css:25 `.k-chapter__exit` · sentence-view.css:204 `.k-tool--speed` · sentence-view.css:245 `.k-tool--mic` · sentence-view.css:364 `.k-rec__stop` · sentence-view.css:489 `.k-feedback__btn` · sentence-view.css:504 `.k-feedback__btn--strong` · sentence-view.css:529 `.k-stepnav__btn` · sentence-view.css:546 `.k-stepnav__btn--next` · sentence-view.css:555 `.k-stepnav__arrow` · recall-review.css:225 `.rr-flip` · recall-review.css:239 `.rr-flip__arrow` · recall-review.css:311 `.rr-done__cta` · recall-review.css:250 `.rr-rate__btn` · recall-review.css:272 `.rr-rate__btn--again` · recall-review.css:202 `.rr-listen` · recall-review.css:55 `.rr-head__exit` · speak.css:55 `.kac-feedback__btn` · speak.css:67 `.kac-feedback__btn--strong` (muerta) · taller.css:293 `.taller .k-btn:disabled` · perfil-aprendizaje.css:16 `.ob5-mute` · perfil-aprendizaje.css:15/72/89 (los tres tamaños contextuales de `.k-btn`) · auth.css:75 `.auth-links a` · landing.css:48/53 `.landing__login-q` · landing.css:56 `.landing__login-a` · pages.css:159 `.snew__back`/`.story__back` · pages.css:572 `.wpop__add` · mobile3.css:105 `.m3-back` · mobile3.css:134 `.m3-fb .acciones .k-btn` · mobile3.css:197 `.m3-srs button` (muerta) · mobile4.css:24 `.m4-add` · mobile4.css:42 `.m4-upload`.
`m3-hero`, que el §5 fila 1 del brief lista aquí (BRIEF.md:189), **no es botón**: es bloque, y va al átomo 12. Se dice explícitamente por el mismo motivo por el que se dice de `.m4-add` (que va al átomo 4).

**Elementos:** `.k-btn__arrow` — la flecha serif itálica que avanza 3px en `:hover`; `.k-btn .arrow` se conserva como **alias textual** del mismo selector mientras haya consumidores sin migrar. `.k-btn__sub` — segunda línea en mono bajo el rótulo (el intervalo SRS proyectado de `.rr-rate__when`). `.k-btn svg` — el icono de trazo, a 16px y sin encogerse (entró en la migración 3, con el «Escuchar» de la ficha).

**Variantes:**
- `.k-btn--ghost` — secundario: transparente con borde de 1px.
- `.k-btn--accent` — el único botón que usa el acento; se reserva para lo que declara **pérdida o fallo**: borrar, descartar sin guardar, y la calificación de fallo del SRS («otra vez»).
- `.k-btn--text` — mono, sin caja: volver, salir, revelar, saltar. Entra por la decisión 3 (aparece en siete hojas: `fin-back`, `qcard__ghost`, `ob__exit`, `rr-head__exit`, `k-chapter__exit`, `ob5-mute`, `story__back`).
- `.k-btn--lg` — un solo tamaño mayor, para la acción única de una pantalla de apertura o cierre.
- `.k-btn--block` — `flex: 1` + contenido centrado, para pares de acciones a ancho repartido.

**Estados:**
- reposo sólido (**sólido**): fondo `--ink`, texto `--paper`, sin borde.
- `.k-btn--ghost` (**fantasma**): fondo transparente, borde 1px `--rule`, texto `--ink`.
- `.k-btn--accent` (**acento**): fondo `--accent`, texto `--on-accent`.
- `:hover` — `transform: translateY(-1px)` (global.css:311); en fantasma además `border-color: var(--ink)` y fondo `--paper-2` (global.css:325); la flecha hija hace `translateX(3px)` (global.css:318).
- `:active` — `transform: scale(0.985)`. Entra por la decisión 3, y es el único estado que el teléfono puede mostrar. **Cambia** el `translateY(0)` de global.css:312 en los 42 consumidores.
- `:disabled` (**deshabilitado**) — `opacity: 0.45`, `cursor: not-allowed`, `transform: none`. **Es nuevo**: `global.css` no lo declara, así que hoy los `disabled={…}` de NewStory.tsx:119 y decenas más no se atenúan.
- `data-loading="true"` (**cargando**) — `pointer-events: none`, `cursor: default`; el `.tsx` añade `aria-busy="true"` y mete un `<span class="k-spinner">` como primer hijo. El spinner se re-tinta con `currentColor` para que se vea sobre el sólido. Es el único estado del §5 que ninguna hoja implementa hoy; el patrón vivo más cercano es NewStory.tsx:115-130 (`disabled={loading}` + spinner intercambiado en el rótulo), que este estado formaliza.
- **con flecha** — presencia de `.k-btn__arrow` (o del alias `.arrow`).
- `aria-pressed="true"` — seleccionado; no lleva pintura propia: el `.tsx` alterna `--ghost` y sólido, que es lo que ya hace StoryFinish.tsx:994.

**Medidas:** `min-height: 44px` (padding `var(--space-3)` 22px sobre sans 15px con `line-height: 1.2`), `gap: 10px`, `var(--font-sans)` 500, `letter-spacing: -0.005em`, radio `var(--r-sm)`, borde 1px (transparente en el sólido, `--rule` en el fantasma), `white-space: nowrap`, `flex-shrink: 0`. `--lg`: `min-height: 56px`, padding `var(--space-4)` 28px sobre `var(--t-body)`. `--text`: mono 11px, `var(--tracking-mark)`, versalitas, color `--ink-3` → `--ink`, `display: inline-flex; align-items: center; justify-content: center`, `min-height: 44px`, `min-width: 44px`, `padding: 0 var(--space-3)`, `margin: -12px calc(-1 * var(--space-3))` para que el área táctil crezca sin mover la línea. `__sub`: mono 11px `--ink-3` con `tabular-nums`.
Literales justificados: **15px** de cuerpo (la escala salta de `--t-mark` 14 a `--t-body` 17 y 15px es lo que usan hoy `k-btn` global.css:302, `fin-btn` y `ob-btn`, o sea los tres botones vivos); **11px** de la variante texto, el escalón mono único de la gramática 10; **28px** del padding horizontal de `--lg` (la escala de espacio salta de 24 a 32); **-1px** y **3px** de los desplazamientos de `:hover`, que son gestos, no espaciado. El alto es 44px y no los ≈47 heredados de global.css:296: el sistema tiene dos alturas de control, 44 (`k-btn`, `k-row`, `k-chip`, `k-rbtn--sm`, `k-tabs__tab`) y 56 (`k-btn--lg`, `k-row--boxed`, `k-rbtn--md`), más el redondo grande de 72.

**Tokens:** `--font-sans`, `--font-serif` (flecha), `--font-mono` (`--text`, `__sub`), `--t-body` (`--lg`), `--space-3`, `--space-4`, `--r-sm`, `--ink`, `--ink-3`, `--paper`, `--paper-2`, `--rule`, `--accent`, `--on-accent`, `--tracking-mark`, `--dur-fast`, `--ease-out`.

**Markup canónico:**
```html
<button type="button" class="k-btn">Siguiente <span class="k-btn__arrow" aria-hidden="true">→</span></button>

<button type="button" class="k-btn k-btn--ghost" data-loading="true" aria-busy="true">
  <span class="k-spinner" aria-hidden="true"></span> Guardando
</button>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.k-btn` (global.css:296) | `.k-btn` (idéntico) |
| `.k-btn:hover` (global.css:311) | `.k-btn:hover` (idéntico) |
| `.k-btn:active` (global.css:312) | `.k-btn:active`; **cambia** de `translateY(0)` a `scale(0.985)` |
| `.k-btn .arrow` (global.css:313) | `.k-btn__arrow`, con `.k-btn .arrow` conservado como alias textual: nueve `<span className="arrow">` vivos, ocho dentro de un `.k-btn` (NewStory.tsx:127, Practice.tsx:329 y :445, perfil/views.tsx:83 y :314, Speak.tsx:654, EstudiarView.tsx:329 y :354) y uno dentro de un héroe (Inicio.tsx:94, que va al átomo 12). El alias muere cuando cada pantalla migre |
| `.k-btn:hover .arrow` (global.css:318) | `.k-btn:hover .k-btn__arrow` (idéntico), con el mismo alias |
| `.k-btn--ghost` (global.css:320) | `.k-btn--ghost` (idéntico) |
| `.k-btn--ghost:hover` (global.css:325) | idéntico |
| `.k-btn--accent` (global.css:327, muerta) | `.k-btn--accent`; el `#fff` pasa a `var(--on-accent)` y la variante se estrena en `.rr-rate__btn--again` |
| `.fin-btn` (finish.css:41) | `.k-btn k-btn--ghost` |
| `.fin-btn--primary` (finish.css:61) | `.k-btn` |
| `.fin-btn--ghost` (finish.css:67) | `.k-btn k-btn--ghost` |
| `.fin-arr` (finish.css:35) | `.k-btn__arrow` |
| `.qcard__next` (finish.css:616) | se pierde: era solo `align-self: flex-end`. La posición la pone el contenedor de la pantalla, no el botón |
| `.fin-back` / `.fin-back--right` (finish.css:21, :749) | `.k-btn k-btn--text` (la posición la reparte `.k-topline`) |
| `.qcard__ghost` (finish.css:625) | `.k-btn k-btn--text` |
| `.qcard__mic` (finish.css:637) | `.k-btn` — se pierde el radio de 999px por la regla 5 de la gramática |
| `.qcard__gender-btn` (finish.css:591) | `.k-btn k-btn--ghost k-btn--block`; su `:active` invertido se pierde y lo cubre el `:active` general |
| `.ob-btn` (onboarding.css:203) | `.k-btn` |
| `.ob-btn--lg` (onboarding.css:229) | `.k-btn--lg` |
| `.ob-btn__arrow` (onboarding.css:222) | `.k-btn__arrow` |
| `.ob-link` (onboarding.css:234) | `.k-link` (global.css, no es átomo del §5) |
| `.ob-link--mute` (onboarding.css:249) | `.k-btn k-btn--text` |
| `.ob__exit` (onboarding.css:22) | `.k-btn k-btn--text` dentro de `.k-topline__exit` |
| `.k-chapter__exit` (sentence-view.css:25) | `.k-btn k-btn--text` dentro de `.k-topline__exit` |
| `.k-tool--speed` (sentence-view.css:204) | `.k-btn k-btn--ghost k-btn--text`; se pierde la píldora |
| `.k-tool--mic` (sentence-view.css:245) | `.k-btn`; se pierde la píldora y el serif de 17px (los controles son sans) |
| `.k-rec__stop` (sentence-view.css:364) | `.k-btn k-btn--ghost`; su borde `color-mix(accent 40%)` pasa al 30 % único |
| `.k-feedback__btn` (sentence-view.css:489) y `--strong` (:504) | `.k-btn k-btn--ghost` y `.k-btn` |
| `.k-stepnav__btn` (sentence-view.css:529) y `--next` (:546) | `.k-btn k-btn--ghost` y `.k-btn` |
| `.k-stepnav__arrow` (sentence-view.css:555) | `.k-btn__arrow` |
| `.k-stepnav__btn--prev` (SentenceView.tsx:621) | no existía en CSS: se borra del markup |
| `.rr-flip` (recall-review.css:225) + `__arrow` (:239) | `.k-btn` + `.k-btn__arrow`; se pierde la píldora |
| `.rr-done__cta` (recall-review.css:311) | `.k-btn` (gana el `:hover` y la transición que no tenía) |
| `.rr-rate__btn` (recall-review.css:250) | `.k-btn k-btn--ghost k-btn--block` con `.k-btn__sub` |
| `.rr-rate__lbl` / `.rr-rate__when` (:262, :263) | contenido directo del botón / `.k-btn__sub` |
| `.rr-rate__btn--again` (recall-review.css:272) | `.k-btn k-btn--accent` (la calificación de fallo del SRS entra en la reserva del acento) |
| `.rr-listen` (recall-review.css:202) + `__tri` (:214) | `.k-btn k-btn--ghost` con icono SVG; el triángulo por bordes se sustituye por trazo |
| `.rr-head__exit` (recall-review.css:55) | `.k-btn k-btn--text` |
| `.kac-feedback__btn` (speak.css:55) | `.k-btn k-btn--ghost` |
| `.kac-feedback__btn--strong` (speak.css:67, muerta) | `.k-btn`; la variante sólida existía diseñada y ahora se usa de verdad |
| `.taller .k-btn:disabled` (taller.css:293) | `:disabled` del átomo; el override de la hoja desaparece |
| `.ob5-mute` (perfil-aprendizaje.css:16) | `.k-btn k-btn--text` (ya tenía `min-height: 44px`) |
| `.ob5-cta .k-btn` / `.ob5-foot .k-btn` / `.ob5-acciones .k-btn` (:15, :72, :89) | `.k-btn--lg` / `.k-btn` / `.k-btn k-btn--block`; los tres tamaños por ancestro mueren |
| `.ob5-foot .k-btn:disabled` (perfil-aprendizaje.css:73) | `:disabled` del átomo (0.45 en vez de 0.28) |
| `.auth-links a` (auth.css:75) | `.k-link` con `min-height: 44px`. Es un enlace de navegación con subrayado (`border-bottom: 1px solid var(--rule)`), igual que `.landing__login-a`, y va al mismo sitio: un solo destino, no dos |
| `.landing__login-q` (landing.css:48/53) | `.k-topline__meta`: no es control, pero tampoco «texto de pantalla» — es la marginalia derecha de la tira, y ahí sube a versalitas mono de 11px (gramática 10). La migración 10 corrige este destino: en el sistema no hay sitio para un texto de 12px suelto en el encabezado |
| `.landing__login-a` (landing.css:56) | `.k-link` dentro de `.k-topline`, que es quien le pone el suelo de 44px. **La coletilla «ya declara `min-height: 44px`» era falsa**: lo declaraba `landing.css:60`, y `.k-link` (global.css:263) no declara altura ninguna. La migración 10 lo descubrió al portarlo y subió el suelo de `.k-topline--foot .k-link` a `.k-topline .k-link` (ver decisión 17) |
| `.snew__back` / `.story__back` (pages.css:159) | `.k-btn k-btn--text`. **Gastado por la migración 15** en las tres pantallas, con la regla del armazón que la 13 escribió para el «volver» que abre una página |
| `.wpop__add` (pages.css:572) | `.k-btn k-btn--text`; su `[data-added="true"]` se conserva textual y pinta en `--accent`. **Hecho en la migración 14**, con `--accent-ink` y no `--accent` a secas: es tinta sobre papel, y la gramática 4 reserva `--accent` para superficies y filetes. La regla va **después** del `:hover`, con la misma especificidad, para que pasar el cursor por encima de una palabra ya añadida no la despinte |
| `.m3-back` (mobile3.css:105) | `.k-btn k-btn--text` |
| `.m3-fb .acciones .k-btn` (mobile3.css:134) | `.k-btn k-btn--block` |
| `.m3-srs button` (mobile3.css:197, muerta) | `.k-btn k-btn--ghost k-btn--block` con `.k-btn__sub`; `.bien` → sólido |
| `.m4-add` (mobile4.css:24) | `.k-row` (átomo 4): es una fila con afordancia de añadir, no un botón |
| `.m4-upload` (mobile4.css:42) | `.k-btn k-btn--ghost k-btn--block` — se pierde el `dashed`, que pasa a Pendientes |

**Notas:** el botón nativo es `<button type="button">`; el `:focus-visible` lo hereda de global.css:49 y **no se anula** (hoy ninguna de las diez implementaciones lo declara). El estado `cargando` lo anuncia `aria-busy`, no solo el spinner, porque §7.6 prohíbe que la información dependa de una animación; bajo `prefers-reduced-motion` el spinner deja de girar y el botón sigue inerte y anunciado. La variante `--text` es la única que necesita el `min-width` de la gramática 6, porque un rótulo mono de 11px («Salir» ≈ 33px) no llega solo. Con alemán largo el rótulo no se parte (`nowrap`): si no cabe, la pantalla usa `--block`.

---

### 2. Botón redondo — `.k-rbtn`

**Reemplaza:** mobile3.css:121 `.m3-rbtn` y sus cuatro tamaños `.play` (:123), `.mic` (:124), `.step` (:126), `.micgrande` (:176, muerta) · finish.css:520 `.qcard__play` + `:hover` (:534) + `.qcard__play-tri` (:540) · sentence-view.css:221 `.k-tool--play` + `:hover` (:234), `.k-pause` (:238), `.k-tri--lg` (:272) · speak.css:17 `.kac-tool--play` + `:hover` (:27), `.kc-note__play` (:186) · speak.css:228 `.kc-ctrl` + `:hover` (:238), `--mic` (:240) + `:hover` (:246), `--end` (:248) · pages.css:520 `.wpop__audio` + `.wpop__audio-icon` (:532).

**Elementos:** `.k-rbtn__ring` — el anillo exterior que late al grabar (hoy es un `::after`; se hace elemento para poder congelarlo sin tocar la caja).

**Variantes:**
- `.k-rbtn--sm` — 44px.
- `.k-rbtn--md` — 56px (el tamaño por defecto; una `.k-rbtn` sin modificador mide 56).
- `.k-rbtn--lg` — 72px.
- `.k-rbtn--ink` — relleno sólido de tinta (el «play» principal).
- `.k-rbtn--rec` — el micrófono: el único que enciende el anillo.

**Estados:**
- **reposo**: contorno — fondo `--paper`, borde 1px `--rule`, color `--ink`. Con `--ink`: fondo y borde `--ink`, color `--paper`.
- `data-on="true"` (**activo**): fondo `--paper-2` y borde `--ink` (control encendido, p. ej. el silencio de Speak). El borde es la segunda señal: en oscuro `--paper-2` sobre `--paper` no se ve.
- `.k-rbtn--rec[data-on="true"]` (**grabando**): fondo y borde `--accent`, color `--on-accent`, y `.k-rbtn__ring` visible —`inset: -8px`, borde 1px `--accent`— latiendo con `klara-breath` a `--dur-breath`.
- `:disabled` (**deshabilitado**): `opacity: 0.45`, `cursor: default`, `pointer-events: none`.
- `:hover`: `transform: scale(1.04)`, y en el contorno `border-color: var(--ink)`. Entra por el mismo criterio que el `:active` del átomo 1 (aparece en cuatro hojas: sentence-view.css:234, finish.css:534, speak.css:27, speak.css:246).
- `:active`: `transform: scale(0.95)`.
- `data-done="true"`: ya sonó — el botón **se apaga**: contorno con borde `--rule` y color `--ink-3`, también sobre `--ink` (es la memoria de `.qcard__play[data-on]`, que en su hoja significaba «ya lo escuchaste», no «está sonando»; allí invertía a contorno de tinta plena y el estado gastado pesaba más que el disponible — aquí pesa menos). El mismo atributo significa otra cosa en la barra de progreso, y eso es deliberado (gramática 3).
- `data-state="playing"`: oculta el glifo `[data-icon="play"]` y muestra `[data-icon="pause"]`; los dos glifos viven siempre en el DOM.
- **tres tamaños**: `--sm` 44 · `--md` 56 · `--lg` 72.

**Medidas:** cuadrado según variante (44 / 56 / 72), `border-radius: 50%`, borde 1px, `display: inline-flex` centrado, `flex-shrink: 0`, `transition: transform var(--dur-fast) var(--ease-out), background var(--dur-fast)`. Iconos SVG de trazo de 1.5px, nunca triángulos por bordes CSS ni glifos de texto. `__ring`: `position: absolute; inset: -8px; border-radius: 50%`.
Literales justificados: **44 / 56 / 72px** unifican los ocho tamaños vivos (28 / 40 / 44 / 54 / 56 / 64 / 74 / 76) y no hay tokens de tamaño de control; **-8px** del anillo es el valor que ya tiene `mobile3.css:178` y el que deja el halo fuera del borde sin tocar al vecino; **1.04** y **0.95** son gestos, no espaciado.

**Tokens:** `--paper`, `--paper-2`, `--ink`, `--ink-3`, `--rule`, `--accent`, `--on-accent`, `--dur-fast`, `--dur-breath`, `--ease-out`. Ningún `--r-*`: el radio es 50 %.

**Markup canónico:**
```html
<button type="button" class="k-rbtn k-rbtn--ink k-rbtn--lg" aria-label="Escuchar">
  <svg data-icon="play" …/><svg data-icon="pause" …/>
</button>

<button type="button" class="k-rbtn k-rbtn--rec k-rbtn--lg" data-on="true" aria-pressed="true" aria-label="Grabando">
  <svg …/><span class="k-rbtn__ring" aria-hidden="true"></span>
</button>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-rbtn` (mobile3.css:121) | `.k-rbtn` (contorno, 56px) |
| `.m3-rbtn.play` 66px (mobile3.css:123) | `.k-rbtn k-rbtn--ink k-rbtn--lg` (72px) |
| `.m3-rbtn.mic` 54px (mobile3.css:124) | `.k-rbtn k-rbtn--rec k-rbtn--md` (56px) |
| `.m3-rbtn.mic[data-on="true"]` (mobile3.css:125) | `.k-rbtn--rec[data-on="true"]`; el `#fff` pasa a `var(--on-accent)` |
| `.m3-rbtn.step` 44px (mobile3.css:126) | `.k-rbtn k-rbtn--sm`; la flecha serif itálica se sustituye por SVG |
| `.m3-rbtn.step:disabled` opacity .3 (mobile3.css:127) | `:disabled` del átomo (0.45) |
| `.m3-rbtn.micgrande` 74px (mobile3.css:176, muerta) | `.k-rbtn k-rbtn--rec k-rbtn--lg` |
| `.m3-rbtn.micgrande[data-on]::after` (mobile3.css:178) | `.k-rbtn__ring` (mismo `inset:-8px`, misma `klara-breath`) |
| `.qcard__play` (finish.css:520) | `.k-rbtn k-rbtn--ink k-rbtn--md` |
| `.qcard__play:hover` (finish.css:534) | `:hover` del átomo (mismo `scale(1.04)`) |
| `.qcard__play[data-on="true"]` (finish.css:535) | `.k-rbtn[data-done="true"]` — se renombra el atributo porque aquí significaba «ya sonó» |
| `.qcard__play-tri` (finish.css:540) | `<svg data-icon="play">` |
| `.k-tool--play` 64px (sentence-view.css:221) + `:hover` (:234) | `.k-rbtn k-rbtn--lg` (72px) + `:hover` del átomo |
| `.ksentence[data-state="playing"] .k-tool--play [data-icon]` (sentence-view.css:236-237) | `.k-rbtn[data-state="playing"] [data-icon]` — el estado deja de venir del ancestro |
| `.k-pause` / `.k-tri--lg` (sentence-view.css:238, :272) | `<svg data-icon="pause">` / `<svg data-icon="play">` |
| `.kac-tool--play` (speak.css:17) + `:hover` (:27) | `.k-rbtn k-rbtn--lg` + `:hover` del átomo |
| `.kac-tool` (Speak.tsx:754) | className fantasma: se borra del markup |
| `.kc-note__play` 40px (speak.css:186) | `.k-rbtn k-rbtn--sm` (44px, cumple §7.2 por primera vez) |
| `.kc-ctrl` 56px (speak.css:228) + `:hover` (:238) | `.k-rbtn k-rbtn--md` + `:hover` del átomo (el `border-color: var(--ink)` se conserva) |
| `.kc-ctrl[data-on="true"]` (speak.css:239) | `.k-rbtn[data-on="true"]` (fondo `--paper-2`) |
| `.kc-ctrl--mic` 76px (speak.css:240) + `:hover` (:246) | `.k-rbtn k-rbtn--rec k-rbtn--lg k-rbtn--ink` + `:hover` del átomo |
| `.kc-ctrl--mic[data-on="true"]` (speak.css:247) | `.k-rbtn--rec[data-on="true"]` — y **gana el latido**: hoy es color plano y el pulso lo pone otro componente |
| `.kc-ctrl--end:hover` (speak.css:248) | se pierde la variante destructiva redonda; la salida pasa a `.k-btn--text`. Ver «Pendientes» |
| `.wpop__audio` 28px (pages.css:520) | `.k-rbtn k-rbtn--sm` (44px). **Gastado por la migración 14**: el disco de tinta de 28px con su triángulo de bordes CSS pasa al contorno de 44 con el glifo de trazo 1.5, que es el mismo que la lectura usa dos centímetros más abajo |
| `.wpop__audio-icon` (pages.css:532) | `<svg data-icon="play">` |

**Notas:** siempre `aria-label` (no lleva texto) y `aria-pressed` cuando `data-on` expresa un conmutador. Bajo `prefers-reduced-motion` el anillo se queda visible y quieto: la información «estoy grabando» la da el acento y el anillo, no el latido. El tamaño mínimo `--sm` es exactamente 44px, así que ningún redondo baja del mínimo táctil; los 28px de `.wpop__audio` y los 40px de `.kc-note__play` desaparecen. No hay variante de 28px: donde hoy la hay, el dibujo se mantiene pequeño y crece el área.

---

### 3. Ficha — `.k-card`

**Reemplaza:** mobile3.css:186 `.m3-ficha` y sus hijos `.centro` (:187), `.art` (:188), `.palabra` (:189), `.posw` (:190), `.trad` (:191), `.ej` (:192), `.hint` (:195) (bloque muerto) · recall-review.css:110 `.rr-ficha`, `__inner` (:115), `__face` (:124), `--front` (:147), `--back` (:181), `__word` (:156), `__gender-cue` (:166), `__cue` (:173), `__answer` (:190), `__article` (:191), `__answer-word` (:192), `__tx` (:193), `__rule` (:194), `__eg` (:195) · finish.css:265 `.qcard`, `::before` (:276), `__head` (:283), `__body` (:289), `__foot` (:549), `__prompt` (:295), `__prompt--lg` (:304), `.qstage` (:257) · taller.css:227 `.taller .rows`, `li` (:232), `.front` (:242), `.back` (:248), `li.bad .back` (:254) · pages.css:485 `.wpop` y sus once hijos (`__head`, `__article`, `__lemma`, `__translation`, `__example`, `__example-de`, `__foot`, `__pos`, `__tail`) · onboarding.css:664 `.ob-done__summary` · mobile4.css:14 `.m4-tema` (ver átomo 4: es fila, no ficha).

**Elementos:** `.k-card__inner` — el eje del volteo. `.k-card__face` — cada cara. `.k-card__head` / `__body` / `__foot` — las tres bandas de la ficha plana. `.k-card__word` — el lema alemán, serif grande. `.k-card__cue` — la pista bajo el lema (serif itálica). `.k-card__answer` — la línea de respuesta del reverso. `.k-card__article` — der/die/das, en el color de su género. `.k-card__tx` — la traducción. `.k-card__rule` — el filete entre respuesta y ejemplo. `.k-card__eg` — el ejemplo. `.k-card__tail` — la cola de la variante anclada.

**Variantes:** `.k-card--flip` — dos caras con volteo 3D. `.k-card--flat` — una sola cara (el enunciado de una pregunta, el popover de palabra). `.k-card--anchored` — flotante con posición inline y cola.

**Estados:**
- `data-state="front"` (**frente**): cara delantera visible.
- `data-state="back"` (**reverso**): `.k-card__inner` gira `rotateY(180deg)` en `--dur-slow` con `--ease-page`; la cara trasera va pre-rotada y `backface-visibility: hidden`.
- **con ejemplo**: presencia de `.k-card__rule` + `.k-card__eg`; sin selector propio, es contenido.
- `data-empty="true"` (**vacía**): las caras se mantienen, el cuerpo se sustituye por una línea serif itálica en `--ink-3`. Es también el estado de la ficha del taller a la que le falta el reverso, que además tiñe el hueco de `--accent-ink`.

**Medidas:** `max-width: 560px`; `.k-card__face`: fondo `--paper-2`, borde 1px `--rule`, radio `var(--r-md)`, sombra `var(--shadow-rest)`, padding 26px 22px, columna flex. `__inner`: `min-height: 340px`, `perspective: 1600px` en el bloque, `transform-style: preserve-3d`. `__word`: serif `clamp(30px, 9cqw, 44px)` (el bloque es `container-type: inline-size`: el cuerpo del lema se mide contra el ancho de la ficha, no contra el viewport), `line-height: 1.1`, `letter-spacing: -0.015em`, `overflow-wrap: anywhere`. `__cue`: serif itálica `var(--t-body)` `--ink-3`. `__article`: serif itálica 24px con el color de `--art-der/die/das`. `__tx`: serif `var(--t-read)` `--ink-2`. `__eg`: serif `var(--t-read)` `line-height: 1.45`. `__rule`: 1px `--rule`. `__tail`: cuadrado de 10px girado 45°, mismo fondo y borde que la cara, `position: absolute` bajo el borde inferior y recortado por él; solo existe con `--anchored`.
Literales justificados: **340px** de alto mínimo es el valor comprimido de `recall-review.css:343`, el que cabe en un teléfono de 390×844 sin scroll (y baja a 288px bajo la gramática 13); **1600px** de perspectiva y **26px/22px** de padding vienen de la misma hoja; **24px** del artículo y **10px** de la cola son los valores vivos de `recall-review.css:191` y `pages.css:590`; el `clamp` de la palabra sustituye a los tres tamaños incompatibles de hoy (60px, 44px, 38px), y su porcentaje se mide en `cqw` porque con `vw` la misma ficha de 350px componía a 35px en un teléfono y a 44px en escritorio, y partía el compuesto alemán en sitios distintos; **320px** es el ancho vivo del popover de palabra (`pages.css:487`), lo único que mantiene `--anchored` como globo en vez de una banda de lado a lado del cascarón.

**Tokens:** `--paper-2`, `--rule`, `--ink`, `--ink-2`, `--ink-3`, `--accent-ink`, `--art-der/die/das`, `--r-md`, `--shadow-rest`, `--t-body`, `--t-read`, `--font-serif`, `--font-mono`, `--shadow-pop`, `--dur-slow`, `--dur-med`, `--ease-page`.

**Markup canónico:**
```html
<article class="k-card k-card--flat">
  <header class="k-card__head"><span class="k-cap">Souvenir</span></header>
  <div class="k-card__body"><p class="k-card__word" lang="de">Bundesausbildungsförderungsgesetz</p></div>
</article>

<article class="k-card k-card--flip" data-state="back">
  <div class="k-card__inner">
    <div class="k-card__face"><span class="k-card__word" lang="de">Monat</span><span class="k-card__cue">der · die · das?</span></div>
    <div class="k-card__face"><p class="k-card__answer"><span class="k-card__article" data-gender="der">der</span> Monat <span class="k-card__tx">el mes</span></p><hr class="k-card__rule"><p class="k-card__eg" lang="de">Im nächsten Monat.</p></div>
  </div>
</article>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-ficha` (mobile3.css:186, muerta) | `.k-card k-card--flip` |
| `.m3-ficha .centro` (:187) | `.k-card__face` (ya centra) |
| `.m3-ficha .art` (:188) | `.k-card__article` |
| `.m3-ficha .palabra` (:189) | `.k-card__word` |
| `.m3-ficha .posw` (:190) | `.k-card__cue` |
| `.m3-ficha .trad` (:191) | `.k-card__tx` |
| `.m3-ficha .ej` + `.de` + `.es` (:192-194) | `.k-card__eg` (alemán) y `.k-note k-note--mono` (traducción) |
| `.m3-ficha .hint` (:195) | `.k-cap` bajo la ficha |
| `.rr-ficha` (recall-review.css:110) | `.k-card k-card--flip` |
| `.rr-ficha__inner` (:115) | `.k-card__inner` |
| `.rr[data-state="revealed"] .rr-ficha__inner` (:122) | `.k-card[data-state="back"] .k-card__inner` — el estado pasa del ancestro a la ficha |
| `.rr-ficha__face --front/--back` (:124, :147, :181) | `.k-card__face` (las dos iguales; la trasera se pre-rota por `:nth-child(2)`) |
| `.rr-ficha__word` (:156) | `.k-card__word`; se pierden los 60px fijos, entra el `clamp` |
| `.rr-ficha__gender-cue` + `b` (:166, :172) | `.k-card__cue` con `.k-card__article` dentro |
| `.rr-ficha__cue` (:173) | `.k-card__cue` |
| `.rr-ficha__answer` / `__article` / `__answer-word` / `__tx` (:190-193) | `.k-card__answer` / `__article` / `__word` / `__tx` |
| `.rr-ficha__rule` / `__eg` (:194, :195) | `.k-card__rule` / `.k-card__eg` |
| `.rr-ficha__eg em` (:196) | se pierde: el `.tsx` nunca emite `<em>`, el resalte no se ha visto nunca |
| `.rr-ficha__folio`, `__front-folio`, `__back-folio`, `__pos`, `__src`, `__eg-tx` (muertas) | no se traducen: se borran (ver «Orden de borrado») |
| `.qcard` (finish.css:265) | `.k-card k-card--flat`; el radio baja de 10px a `--r-md` |
| `.qcard::before` (finish.css:276) | se pierde la franja superior de 3px: era el único sello de una hoja y la regla 5 no lo necesita |
| `.qcard__head` / `__body` / `__foot` (:283, :289, :549) | `.k-card__head` / `__body` / `__foot`; el filete discontinuo del pie pasa a `.k-card__rule` sólido |
| `.qcard__prompt` / `--lg` (:295, :304) | `.k-card__word` (un solo tamaño con `clamp`) |
| `.qcard__cloze` (finish.css:404, y su 32px de :1013) | `.k-stage` (gramática 12): la frase con hueco es el mismo pasaje en otro momento, no una pieza de la ficha |
| `.qstage` + `@keyframes qcard-in` (:257, :260) | animación de entrada de pantalla, no del átomo. Ver «Pendientes» |
| `data-type="mc\|cloze\|shadow\|gender_cloze"` (StoryFinish.tsx:441…) | se conserva como dato semántico sin pintura, igual que hoy |
| `.taller .rows li` (taller.css:232) | `.k-card k-card--flat` en `.k-wrap`, o `.k-row` si la vista pasa a lista |
| `.taller .rows .front` / `.back` (:242, :248) | `.k-card__word` / `.k-card__tx` |
| `.taller .rows li.bad .back` (:254) | `.k-card[data-empty="true"] .k-card__tx` |
| `.wpop` (pages.css:485) | `.k-card k-card--flat k-card--anchored`. **Gastado por la migración 14**, que además le dio a `--anchored` su propia métrica (ver candidato 18) |
| `.wpop__head` / `__lemma` / `__article` (:501, :513, :507) | `.k-card__head` / `__word` / `__article`; el color inline del artículo pasa a `--art-*`. **Hecho**: mueren los tres `oklch` literales que `WordPopover.tsx:16-20` llevaba en un objeto de JavaScript y el `style={{color}}` que los aplicaba. El lema sube de 22px a los 30 del clamp del átomo, que es el mínimo de `9cqw` sobre un globo de 320: la palabra es la razón por la que el globo existe, así que se compone como palabra de ficha |
| `.wpop__translation` (:539) | `.k-card__tx` |
| `.wpop__example` / `__example-de` (:545, :553) | `.k-card__rule` + `.k-card__eg` |
| `.wpop__foot` / `__pos` (:564, :586) | `.k-card__foot` + `.k-cap` |
| `.wpop__tail` (:590) | `.k-card__tail` |
| `.wpop__example-es` (:559, muerta) | `.k-note k-note--mono` |
| `.wpop__freq` (WordPopover.tsx:110) | className fantasma: se borra del markup o se convierte en `.k-cap`. **La migración 14 eligió `.k-cap`** —es una cifra al margen, que es lo que la cinta significa— y de paso encontró que la cinta traía su propio `margin: 18px 0 2px` dentro de una columna con `gap`: dos reglas del sistema le dicen ahora que en una ficha el hueco lo reparte el `gap` |
| `@keyframes wpop-in` (:497) | `--anchored` entra con la misma coreografía que `.k-sheet`, apagada en reduced-motion |
| `.ob-done__summary` (onboarding.css:664) | no es ficha: son tres `.k-row` entre dos `.k-hairline` |

**Notas:** la ficha volteada anuncia el cambio con `aria-live="polite"` sobre `.k-card__inner`, porque con reduced-motion el volteo desaparece y solo cambia el contenido. Bajo reduced-motion `--flip` conmuta las caras con `display`, sin `rotateY`. La ficha no es tocable: voltearla es trabajo de un `.k-btn` o de la tecla Espacio, así que el mínimo de 44px no le aplica; los botones que lleva dentro sí lo cumplen. `overflow-wrap: anywhere` en `__word` es lo que hace que `Bundesausbildungsförderungsgesetz` parta en vez de desbordar. `--anchored` necesita el ancestro posicionado de `.k-app` (gramática 12).

---


### 4. Fila — `.k-row`

**Reemplaza:** mobile3.css:78 `.m3-rowbtn` + `.n`/`.tit`/`.estado` de `.m3-plan` (:47-49) y de `.m3-rows` (:79-81) · mobile3.css:44 `.m3-plan li` y sus `[data-e="hecha"|"ahora"]` (:50-53) · mobile3.css:77 `.m3-rows li` y sus `[data-e="dominado"|"futuro"]` (:82-83) · mobile4.css:14 `.m4-tema` y sus `.f1`/`.tit`/`.estado`/`.sub` (:16-20) · mobile4.css:24 `.m4-add` · finish.css:315 `.qcard__opt` con sus cuatro `data-state` (:362, :373, :384, :394), `__opt-letter` (:334), `__opt-text` (:347), `__opt-mark` (:355) · finish.css:799 `.fin-sched__item` con `[data-struggled]` (:857) y sus hijos `__word` (:808) / `__art` (:814) / `__lemma` / `__tx` / `__next` / `__next-dot` · finish.css:929 `.fin-l1__item` · onboarding.css:463 `.ob-isel__opt` con `:hover` (:480) y `[data-active="true"]` (:481) y `__opt-sub` (:485) · onboarding.css:502 `.ob-level__card` con `::before` (:518), `:hover` (:527), `[data-active="true"]` (:531), `__title` (:543), `__phrase` (:551) · onboarding.css:675 `.ob-done__row` + `__row-val` (:681) · taller.css:98 `.taller .rail button`, `.name` (:113), `.n` (:118), `li.on` (:125), `:disabled` (:135) · pages.css:731 `.kp-segment` + `:hover` (:748) + `__title`/`__dek`/`__arrow` · pages.css:707 `.kp-returns__item` + `__word`/`__tx`/`__next` · perfil-aprendizaje.css:36 `.ob5-opt` con `[data-on]`/`[data-nega]`/`[data-otra]`, `.ob5-mark` (:40) y `.txt` (:45-46) · perfil-aprendizaje.css:84 `.ob5-fact` + `.k`/`.v` · perfil-aprendizaje.css:92 `.ob5-fila` (muerta) · path.css:75 `.mod__story` · path.css:16-65 `.path__node` y sus `--locked`/`--current`/`--completed` (muertas).

**Elementos:** `.k-row__n` — numeral, artículo alemán o insignia de la izquierda, mono, ancho mínimo fijo. `.k-row__title` — el rótulo, serif. `.k-row__sub` — la segunda línea (traducción, dek). `.k-row__meta` — el estado o el contador de la derecha, mono. `.k-row__mark` — la marca de selección (radio o casilla). `.k-row__arrow` — la flecha de afordancia.

**Variantes:** `.k-row--quiet` — fila de solo lectura (clave/valor, agenda), no tocable, sin `min-height`. `.k-row--boxed` — fila con caja: borde 1px y radio `--r-md`, para las opciones de una pregunta y las tarjetas de elección del onboarding.

**Estados:** (`data-state` en el elemento de la fila)
- sin atributo o `data-state="pending"` (**pendiente**): filete superior 1px `--rule`, título `--ink`, meta `--ink-3`.
- `data-state="now"` (**ahora**): título en `600`, meta en `--accent`.
- `data-state="done"` (**hecha**): título `--ink-3` con `line-through` de 1px, meta `--ink-3`. El tachado es la señal; el color solo la acompaña (en oscuro `--ink-4` sobre papel da 2,4:1 y el título desaparecía).
- `data-state="locked"` (**bloqueada**): toda la fila en `--ink-4` (título, meta y numeral), `cursor: default`, sin fondo de contacto en `:hover`/`:active`; el `.tsx` añade `aria-disabled="true"`. Se descartó la `opacity: 0.55` de la v1: apilada sobre las tintas bajas dejaba el numeral en 1,6:1. Una pieza inactiva está exenta del mínimo de contraste, y así se distingue de la dominada, que conserva el título en `--ink-3`.
- `data-state="mastered"` (**dominada**): título `--ink-3`, meta `--ink-4`, sin tachado.
- `data-state="selected"` — entra por la decisión 3: `box-shadow: inset 3px 0 0 var(--ink)`, `padding-left: var(--space-2)` compensado con `margin-left: calc(-1 * var(--space-2))`, título en `600`, y `.k-row__mark` relleno de `--ink`.
- `:hover`: fondo `--paper-2`. Entra por el mismo criterio que el `:active`: vive en pages.css:748 (`.kp-segment:hover`) y onboarding.css:480 (`.ob-isel__opt:hover`), o sea dos hojas, y sin él el escritorio pierde la afordancia.
- `:active`: fondo `--paper-2`.
- `:disabled`: idéntico al reposo salvo `cursor: default`. Es deliberado y viene de `taller.css:133-134`: una fila inerte por permisos no debe parecer rota; lo que no está disponible se dice con `locked`.
- `.k-row__n[data-gender="der|die|das"]`: el artículo alemán toma su color de `--art-der/die/das`. Es el único caso en que el numeral cambia de tinta.

**Medidas:** `min-height: 44px`, `display: flex`, `align-items: baseline`, `gap: var(--space-3)`, `padding: var(--space-3) 0`, `width: 100%`, `text-align: left`, `border-top: 1px solid var(--rule)` (la primera pierde el filete con `:first-child`). `__n`: mono 11px `--ink-4`, `flex: 0 0 auto`, `min-width: 22px`, `tabular-nums`. `__title`: serif `var(--t-body)`, `flex: 1`, `overflow-wrap: anywhere`. `__sub`: serif itálica `var(--t-meta)` `--ink-3`. `__meta`: mono 11px versalitas `--ink-3`, `flex-shrink: 0`. `--boxed`: padding 14px var(--space-4), borde 1px `--rule`, radio `var(--r-md)`, `min-height: 56px`.
Literales justificados: **11px** de `__n` y `__meta` es el escalón mono único de la gramática 10; **22px** de `min-width` del numeral es el valor vivo de `mobile3.css:47`, pero pasa de `flex: 0 0 22px` a `min-width` porque «die» en mono no cabe en 22px y la etiqueta clave de `.ob-done__row` («Nivel objetivo») tampoco; **14px** del padding vertical de `--boxed` (la escala salta de 12 a 16) y **56px** de alto, que es la altura de control del sistema junto a 44; **3px** del canto de la fila seleccionada es el grosor que ya usan `finish.css:365` y `taller.css:125` para decir «esta».

**Tokens:** `--rule`, `--ink`, `--ink-3`, `--ink-4`, `--paper-2`, `--accent`, `--art-der`, `--art-die`, `--art-das`, `--space-2`, `--space-3`, `--space-4`, `--t-body`, `--t-meta`, `--r-md`, `--font-serif`, `--font-mono`, `--tracking-mark`, `--dur-fast`, `--ease-out`.

**Markup canónico:**
```html
<li><button type="button" class="k-row" data-state="now">
  <span class="k-row__n">03</span>
  <span class="k-row__title">Beim Arzt</span>
  <span class="k-row__meta">ahora</span>
</button></li>

<li><button type="button" class="k-row k-row--boxed" data-state="selected" role="radio" aria-checked="true">
  <span class="k-row__mark" aria-hidden="true"></span>
  <span class="k-row__title" lang="de">Bundesausbildungsförderungsgesetz</span>
</button></li>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-rowbtn` (mobile3.css:78) | `.k-row` |
| `.m3-plan li` / `.m3-rows li` (mobile3.css:44, :77) | el `<li>` deja de estilarse: el filete lo pone `.k-row` |
| `.m3-plan .n` / `.m3-rows .n` (:47, :79) | `.k-row__n` |
| `.m3-plan .tit` / `.m3-rows .tit` (:48, :80) | `.k-row__title` |
| `.m3-plan .estado` / `.m3-rows .estado` (:49, :81) | `.k-row__meta`; sube de 10 a 11px y de `--ink-4` a `--ink-3` |
| `li[data-e="hecha"]` (mobile3.css:50-51) | `data-state="done"` |
| `li[data-e="ahora"]` (mobile3.css:52-53) | `data-state="now"` |
| `li[data-e="dominado"]` (mobile3.css:82) | `data-state="mastered"` |
| `li[data-e="futuro"]` (mobile3.css:83) | `data-state="pending"` |
| `.m4-tema` (mobile4.css:14) | `.k-row` |
| `.m4-tema .f1` (:16) | se pierde: la fila ya es flex con `space-between` |
| `.m4-tema .tit` / `.estado` / `.sub` (:17, :18, :20) | `.k-row__title` / `__meta` / `__sub` |
| `.m4-tema .estado[data-hot="true"]` (:19) | `data-state="now"` en la fila |
| `.m4-tema .m4-bar` (:21) | `.k-bar` dentro de la fila (átomo 5) |
| `.m4-add` + `.tile`/`.tit`/`.sub` (mobile4.css:24-27) | `.k-row` con `.k-row__n` (el mosaico de 30px pasa a icono SVG dentro del numeral); el borde discontinuo del mosaico va a Pendientes |
| `.qcard__opt` (finish.css:315) | `.k-row k-row--boxed` |
| `.qcard__opt[data-state="correct"\|"wrong"\|"reveal"\|"muted"]` (:362-394) | no entran en el sistema; migran con StoryFinish. Ver «Pendientes» |
| `.qcard__opt-letter` (:334) | la insignia circular de 26px **no** es el numeral: migra con los cuatro `data-state` de la opción. Ver «Pendientes» |
| `.qcard__opt-text` (:347) | `.k-row__title` |
| `.qcard__opt-mark` (:355) | `.k-row__meta` |
| `.qcard__opts` (finish.css:307) | `.k-wrap` o `<ul>` sin estilar (gramática 12) |
| `.fin-sched__item` (finish.css:799) | `.k-row k-row--quiet` |
| `.fin-sched__word` (finish.css:808) | se pierde el envoltorio: la fila ya es flex y `__art` y `__lemma` son hermanos directos |
| `.fin-sched__art` (:814) | `.k-row__n[data-gender="der\|die\|das"]`, que conserva el color de género vía `--art-*` |
| `.fin-sched__lemma` / `__tx` / `__next` (:820-842) | `.k-row__title` / `__sub` / `__meta` |
| `.fin-sched__next-dot` (:852) y `[data-struggled]` (:857) | pasan a `.k-chip` con `data-tone`. Ver «Pendientes» |
| `.fin-sched__list` (:792) / `.fin-l1__list` (:921) | `<ul>` sin estilar (gramática 12) |
| `.fin-l1__item` / `__word` (finish.css:929, :936) | `.k-row k-row--quiet` / `.k-row__title` |
| `.ob-isel__opt` (onboarding.css:463) | `.k-row` |
| `.ob-isel__opt:hover` (:480) | `:hover` del átomo; el `--paper-3` baja a `--paper-2`, que es el fondo de contacto único del sistema |
| `.ob-isel__opt[data-active="true"]` (:481) | `data-state="selected"` — el atributo cambia por el criterio de desempate de la gramática 3 (es elección dentro de un grupo, no navegación); se pierde la inversión total del fondo, que el sistema reserva al chip |
| `.ob-isel__opt-sub` (:485) | `.k-row__meta` |
| `.ob-isel__opt-label` (ObInlineSelect.tsx:72) | `.k-row__title` (hoy es un gancho sin regla en ninguna hoja) |
| `.ob-level__card` (onboarding.css:502) | `.k-row k-row--boxed` dentro del `role="radiogroup"` de StepLevel.tsx:36 |
| `.ob-level__card::before` (:518) + `[data-active="true"]` (:531, :535) | `data-state="selected"` (el canto `inset 3px` sustituye al `::before`) |
| `.ob-level__card:hover` (:527) | `:hover` del átomo |
| `.ob-level__grid` (:494) | `.k-wrap` (gramática 12) |
| `.ob-level__code` (:536) | `.k-level k-level--bare` (átomo 7) |
| `.ob-level__title` (:543) / `__phrase` (:551) | `.k-row__title` / `.k-row__sub` |
| `.ob-done__row` / `__row-val` (onboarding.css:675, :681) | `.k-row k-row--quiet` con `.k-row__n` (etiqueta mono, que ahora puede pasar de 22px) y `.k-row__title` |
| `.taller .rail button` (taller.css:98) | `.k-row` |
| `.taller .rail .name` (:113) | `.k-row__title`; el `ellipsis` se cambia por `overflow-wrap: anywhere` (una etiqueta alemana larga se lee partida, no cortada) |
| `.taller .rail .n` (:118) | `.k-row__meta` |
| `.taller .rail li.on` (:125-128) | `data-state="selected"` (el canto pasa de 2px a 3px) |
| `.taller .rail button:disabled` (:135) | `:disabled` del átomo, que conserva a propósito el aspecto de reposo |
| `.kp-segment` (pages.css:731) | `.k-row k-row--boxed`. **Gastado por la migración 15**: las tres puertas de Práctica, con `__title` / `__sub` / `__arrow` y dentro de un `.k-wrap`, que es lo que la gramática 12 mandaba para `kp-segments` — y funciona porque `.k-row` mide `width: 100%`, así que cada fila se lleva su renglón y el `gap` es el hueco |
| `.kp-segment:hover` (pages.css:748) | `:hover` del átomo; el `border-color: var(--ink)` se pierde a favor del fondo `--paper-2`, que es el gesto único |
| `.kp-segment__title` / `__dek` / `__arrow` (:752-767) | `.k-row__title` / `__sub` / `__arrow` |
| `.kp-segments` (:724) / `.kp-returns__list` (:706) | `<ul>` sin estilar (gramática 12) |
| `.kp-returns__item` (pages.css:707) | `.k-row k-row--quiet` |
| `.kp-returns__word` / `__tx` / `__next` (:716-718) | `.k-row__title` / `__sub` / `__meta` |
| `.ob5-opt` (perfil-aprendizaje.css:36) | `.k-row` |
| `.ob5-opt .txt` (perfil-aprendizaje.css:45) | `.k-row__title` (es el rótulo real de la fila; hoy solo se estila desde los estados) |
| `.ob5-opt[data-on="true"]` (:39) y `[data-on] .txt` (:45) | `data-state="selected"` (incluido el peso 600 del rótulo) |
| `.ob5-mark` + `.radio`/`.check` (:40-44) | `.k-row__mark` (la forma la decide `role="radio"` o `"checkbox"`) |
| ~~`.ob5-opt[data-nega="true"]` / `[data-otra="true"]` → `.k-row__title[data-nega]`~~ | **enmendado por la migración 11**: los dos atributos pintaban lo MISMO, así que en el sistema son un solo nombre, y no son estado sino propiedad de la opción (la decide el catálogo, no el uso): **`.k-row--aside`**, variante |
| `.ob5-fact` + `.k` / `.v` (:84-86) | `.k-row k-row--quiet` + `.k-row__n` / `.k-row__title` |
| `.ob5-tri` + `.n` (:53, :54) | `.k-row k-row--quiet` con dos `.k-chip` a la derecha. La migración 11 lo cumple, y de paso **muere `.ob5-trihead`**: los chips llevan «Sirve» y «No» escritos, así que no hay dos columnas que rotular. Muere también el tinte de `[data-set="true"] .n`: que la fila esté contestada lo dice el chip lleno |
| `.ob5-fila` (:92-97, muerta) | no se traduce: se borra. El brief §5 la nombra por error; Perfil pinta con `m3-rowbtn` |
| `.mod__story` (path.css:75) | `.k-row` con `.k-row__arrow`. **Gastado por la migración 13** tal cual lo mandaba el mapa: la flecha deja de ser un `.k-mono` escrito a mano en el `.tsx` y pasa al elemento, que además le da el gesto de 3px al pasar el cursor |
| `.path__node`, `--locked`, `--current`, `--completed`, `.path__num`, `.path__check`, `.path__cta` (path.css:16-65, muertas) | son la referencia de los cinco estados; se leen y luego se borran. **Hecho en la migración 13**: leídas y borradas. Los cinco estados que el átomo ya tenía escritos (`now`, `done`, `locked`, `mastered`, `selected`) salieron de aquí, así que la lectura no cambió nada — que es exactamente lo que se quería comprobar |

**Notas:** la fila tocable es `<button type="button">` dentro de `<li>`; la fila de formulario lleva `role="radio"`/`"checkbox"` con `aria-checked` (StepLevel.tsx:36 ya declara el `role="radiogroup"`), y la bloqueada `aria-disabled="true"` (no `disabled`, para que siga siendo alcanzable con el lector de pantalla). `:focus-visible` se hereda del global y no se anula. Alemán largo: `__title` parte palabra, `__meta` no encoge, y por eso una fila puede crecer a dos líneas sin romperse. Todas las filas cumplen 44px de alto; la `--quiet` no, y no le hace falta porque no es tocable.

---

### 5. Barra de progreso — `.k-bar`

**Reemplaza:** mobile3.css:107 `.m3-prog`, `.segs` (:108), `.seg` (:109), `.seg[data-done="true"]` (:110) · mobile3.css:184 `.m3-repbar` + `.fill` (muerta) · mobile3.css:69 `.m3-cefr` con `.track` (:70), `.fill` (:71), `.dot` (:72), `.stop` (:73), `.stop[data-past]` (:74), `.aqui` (:75) · mobile4.css:22 `.m4-bar` + `i` (:23) · finish.css:225 `.quiz-hero__prog`, `__track` (:239), `__pip` (:245) con `[data-state="done"|"now"]` (:251-252), `__count` (:231), `__slash` (:238) · onboarding.css:689 `.ob__progress`, `.ob__pips` (:694), `.ob__pip` (:700) con sus dos estados (:706-707) · sentence-view.css:57 `.k-prog`, `__count` (:62), `__slash` (:69), `__track` (:70), `__pip` (:71) con sus dos estados (:77-78) · recall-review.css:80 `.rr-prog` + `__count` (:81); `.rr-prog__track`/`__pip`/`__slash` (:89-94, muertas) · perfil-aprendizaje.css:23 `.ob5-ticks`, `.ob5-grupo` (:24), `.ob5-tick` (:25) con `[data-s="done"|"skip"|"now"]` (:26-28) · path.css `.path__bar`, `--fast`, `--slow` (muertas).

**Elementos:** `.k-bar__track` — la pista. `.k-bar__seg` — un segmento. `.k-bar__fill` — el relleno continuo. `.k-bar__count` — el contador acoplado, mono con `tabular-nums`. `.k-bar__stop` — un hito con su etiqueta (CEFR). `.k-bar__dot` — la posición actual sobre la pista de hitos.

**Variantes:** `.k-bar--segs` · `.k-bar--fill` · `.k-bar--milestones`. Son las tres formas de §5, y por eso se repiten abajo como estados: `hoja.check.mjs:39` las exige con los slugs `segmentos`, `continua` e `hitos`.

**Estados:**
- **segmentos** (`.k-bar--segs`): la pista se reparte en `.k-bar__seg` iguales.
- **relleno continuo** (`.k-bar--fill`): un solo `.k-bar__fill` con el ancho en línea.
- **con hitos** (`.k-bar--milestones`): pista de 1px con `.k-bar__stop` debajo y `.k-bar__dot` encima.
- `.k-bar__seg` sin atributo: fondo `--rule` (pendiente).
- `.k-bar__seg[data-state="done"]`: fondo `--ink-2`.
- `.k-bar__seg[data-state="now"]`: fondo `--ink`.
- `.k-bar__fill`: ancho por `style="width:…%"` desde el `.tsx`, sobre pista `--rule`.
- `.k-bar__stop[data-past="true"]`: color `--ink-2` (hito ya alcanzado); el resto `--ink-4`.
- `.k-bar__dot`: círculo de 9px en `--accent` sobre la pista.

**Medidas:** `.k-bar`: flex, `align-items: center`, `gap: var(--space-3)`. `__track`: `flex: 1`, alto 2px, `display: flex`, `gap: 5px` en `--segs`. `__seg`: `flex: 1`, alto 2px, sin radio. `__fill`: alto 2px, fondo `--ink`, `transition: width var(--dur-med) var(--ease-out)`. `__count`: mono 11px, `--ink-3`, `tabular-nums`, con la barra `/` en `--ink-4`. `--milestones`: pista de 1px, `__stop` en mono 11px bajo la pista, `__dot` 9px. `--milestones` es además el contexto de posición del átomo (`position: relative`) y por eso su inset lateral de 16px va en **margen** y no en padding: la caja de posición de un absoluto es la de padding, y con padding el hito del 0 % caería 16px antes que la pista. La `.k-cap` de dentro es «estás aquí»: absoluta con `bottom: 100%`, `margin: 0 0 var(--space-1)` (el margen normal de la cinta se sumaría al desplazamiento), `translateX(-50%)` y color `--accent`, con el mismo `left` en línea que `__dot`.
Literales justificados: **2px** de alto y **5px** de gap son la firma editorial de la barra en las cinco implementaciones vivas; **1px** de la pista de hitos y **9px** del punto vienen de `mobile3.css:70-72`; **11px** del contador y de la etiqueta de hito es el escalón mono único (los 13px de `--t-meta` y los 10px de `mobile3.css:73` convergen ahí).

**Tokens:** `--rule`, `--ink`, `--ink-2`, `--ink-3`, `--ink-4`, `--accent`, `--space-3`, `--font-mono`, `--tracking-mark`, `--dur-med`, `--ease-out`.

**Markup canónico:**
```html
<div class="k-bar k-bar--segs">
  <span class="k-bar__count">03 <span aria-hidden="true">/</span> 08</span>
  <div class="k-bar__track" role="progressbar" aria-valuenow="3" aria-valuemin="0" aria-valuemax="8">
    <span class="k-bar__seg" data-state="done"></span><span class="k-bar__seg" data-state="now"></span><span class="k-bar__seg"></span>
  </div>
</div>

<div class="k-bar k-bar--fill"><div class="k-bar__track"><i class="k-bar__fill" style="width:42%"></i></div></div>

<div class="k-bar k-bar--milestones">
  <span class="k-cap" style="left:62%">Estás aquí</span>
  <div class="k-bar__track" role="progressbar" aria-label="Nivel alcanzado" aria-valuenow="62" aria-valuemin="0" aria-valuemax="100">
    <i class="k-bar__fill" style="width:62%"></i>
  </div>
  <span class="k-bar__dot" style="left:62%"></span>
  <span class="k-bar__stop" data-past="true" style="left:0%">A1</span>
  <span class="k-bar__stop" style="left:100%">B2</span>
</div>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-prog` (mobile3.css:107) | `.k-bar k-bar--segs` |
| `.m3-prog .segs` (:108) | `.k-bar__track` |
| `.m3-prog .seg` (:109) | `.k-bar__seg`; su `data-done="true"` (:110) pasa a `data-state="done"`, que es la única forma que queda: el alias murió con la migración de Lectura |
| `.m3-repbar` + `.fill` (:184-185, muertas) | `.k-bar k-bar--fill` + `.k-bar__fill` |
| `.m3-cefr` (:69) | `.k-bar k-bar--milestones` |
| `.m3-cefr .track` / `.fill` (:70, :71) | `.k-bar__track` / `.k-bar__fill` |
| `.m3-cefr .dot` (:72) | `.k-bar__dot` |
| `.m3-cefr .stop` / `.stop[data-past]` (:73, :74) | `.k-bar__stop` / `[data-past="true"]`; sube de 10 a 11px |
| `.m3-cefr .aqui` (:75) | `.k-cap` en acento sobre el punto (átomo 6) |
| `.m4-bar` + `i` (mobile4.css:22-23) | `.k-bar k-bar--fill` + `.k-bar__fill` |
| `.quiz-hero__prog` (finish.css:225) | `.k-bar k-bar--segs` |
| `.quiz-hero__track` / `__pip` (:239, :245) | `.k-bar__track` / `.k-bar__seg` |
| `.quiz-hero__pip[data-state="done"\|"now"]` (:251-252) | igual, sobre `.k-bar__seg` |
| `.quiz-hero__count` / `__slash` (:231, :238) | `.k-bar__count` (el `/` se marca `aria-hidden`) |
| tope `max-width: 280px` de la pista (finish.css:239) | se pierde del átomo: el tope lo pone la pantalla, no la barra |
| `.ob__progress` (onboarding.css:689) | contenedor de pantalla; la barra es `.k-bar k-bar--segs` |
| `.ob__pips` / `.ob__pip` (:694, :700) | `.k-bar__track` / `.k-bar__seg` |
| `.k-prog` / `__track` / `__pip` (sentence-view.css:57, :70, :71) | `.k-bar` / `__track` / `__seg` |
| `.k-prog__count` / `__slash` (:62, :69) | `.k-bar__count` |
| `.rr-prog` / `__count` (recall-review.css:80, :81) | `.k-bar k-bar--segs` / `.k-bar__count` — y por fin dibuja pista, que hoy tiene 0px de alto |
| `.rr-prog__track` / `__pip` / `__slash` (:89-94, muertas) | `.k-bar__track` / `__seg`; el `data-state="again"` no entra. Ver «Pendientes» |
| `.ob5-ticks` / `.ob5-grupo` / `.ob5-tick` (perfil:23-25) | `.k-bar k-bar--segs` / — / `.k-bar__seg` |
| `.ob5-tick[data-s="done"\|"now"]` (:26, :28) | `data-state="done"` / `"now"`; el `now` deja de ser acento y pasa a `--ink` |
| `.ob5-tick[data-s="skip"]` (:27) | ~~no entra~~ **enmendado por la migración 11: SÍ entra**, como `data-state="skipped"` y una declaración (`--ink-4`). Sin él una pregunta dejada en blanco se ve igual que una por responder, o sea la barra miente. Lo que no entra es el anillo: sobre un riel de 2px un `inset 0 0 0 1px` no deja hueco y lo que se veía era el relleno |
| grupos con peso `--w` (`.ob5-grupo`, :24) | **no entra, confirmado por la migración 11**: el sistema tiene una barra de segmentos, no una de grupos con peso, y en qué bloque vas lo dice el título de la línea superior, que es donde vive la orientación |
| `.path__bar`, `--fast`, `--slow` (path.css, muertas) | referencia de la barra dual (visto vs. dominado); se leen y se borran. **Hecho en la migración 13.** El doble relleno —lo encontrado bajo lo dominado— vive hoy en `.k-bar--dual`, que salió de aquí; el mapa de curso ya no lo usa porque su progreso lo dicen las tres cifras del héroe |

**Notas:** la pista lleva `role="progressbar"` con `aria-valuenow/min/max` y el contador es su texto visible: la información no depende del color de los segmentos, que es lo que exige §7.6. Y por eso mismo `role="progressbar"` no lleva nada dentro salvo los segmentos o el relleno: es un rol con «children presentational: true», así que `__stop`, `__dot` y la cinta van **fuera** de ese nodo, hermanos suyos dentro de `.k-bar`; si se meten dentro, las etiquetas de nivel («A0 A1 A2 B1») desaparecen del árbol de accesibilidad y el `aria-label` de la pista las pisa, y el hito se queda en señal solo visual. Con `prefers-reduced-motion` el `__fill` cambia de ancho sin transición. Los segmentos son `flex: 1` sin mínimo, así que un pasaje de 40 oraciones produce segmentos sub-píxel: el consumidor tiene que agrupar o recortar, y el átomo no lo resuelve solo.

---

### 6. Cinta de sección — `.k-cap`

**Reemplaza:** mobile4.css:9 `.m4-sec` + `::after` (:10) · finish.css:8 `.fin-cap`, `.fin-sched__head` (:779), `.fin-sched__count` (:786) · taller.css:81 `.taller .rail h2`, `.preview-head` (:212), `.flag` (:223) · speak.css:205 `.kc-transcript__cap` · pages.css:666 `.kp-chips__cap`, `.kp-returns__head` (:704), `.kp-returns__count` (:705) · path.css:10 `.path__kicker` · landing.css:67 `.landing__bloque` + `h2` (:72), `.landing__wl` (:88) + `__wl-title` (:90) —los cuatro rótulos de sección de la portada, que la migración 10 trajo aquí contra el mapa; ver abajo— · mobile3.css:119 `.m3-dock .estadoK` + `.rec` (:141) · mobile3.css:84 `.m3-statline` · mobile3.css:175 `.m3-dock .miclbl` (muerta) · onboarding.css:153 `.ob-prompt` (ver «Pendientes»: es encabezado de pantalla, no cinta).

**Elementos:** `.k-cap__count` — la cifra o el estado a la derecha.

**Junta:** `.k-cap + .k-note { margin-top: 0 }` — una nota que sigue a su cinta pertenece a la cinta, y sin esto no lo parecía: la nota nace con 18px arriba (12 bajo viewport corto) y ganaba al `margin-bottom: 2px` de la etiqueta, así que el párrafo se despegaba de su rótulo hasta quedar flotando entre dos secciones. La escribe la migración 10 y **no va en `:where()`**, a diferencia de las otras juntas del sistema: `.k-bar` y `.k-wrap` no traen margen propio y un suelo de especificidad 0 les basta; `.k-note` sí lo trae y lo pisaba. Dos clases, como `.k-band > .k-note`.

**Variantes:** `.k-cap--rule` — con filete de 1px que continúa a la derecha hasta el borde (`::after` con `flex: 1`), la gramática de `m4-sec`. `.k-cap--center` — centrada, para el estado de la sesión bajo el dock.

**Estados:**
- **sola**: solo la etiqueta.
- **con contador**: presencia de `.k-cap__count`; el bloque pasa a `justify-content: space-between`.
- `.k-cap__count[data-tone="live"]`: color `--accent`. Es el «GRABANDO» de `mobile3.css:141`, y por eso se declara como estado y no como excepción suelta. Es uno de los dos únicos casos en que la marginalia toma el acento; el otro es la cinta «estás aquí» sobre el punto de `.k-bar--milestones` (átomo 5), que lo toma por su sitio en la barra, no por este atributo.

**Medidas:** `display: flex`, `align-items: center`, `gap: var(--space-3)`, `margin: 18px 0 2px` (dentro de `.k-card__head` el margen superior es 0: la cabecera de la ficha ya trae su padding), `flex: 0 0 auto`, mono 11px, `letter-spacing: var(--tracking-mark)`, `text-transform: uppercase`, color `--ink-3`; `__count` en `--ink-3` con `tabular-nums` y `flex-shrink: 0`. `--rule`: `::after { content:""; flex:1; height:1px; background: var(--rule) }`.
Literales justificados: **11px** es el escalón mono único (gramática 10) y `--t-meta` (13px) no sirve: subir a 13 toda la marginalia engorda la interfaz entera. **18px/2px** de margen son los de `mobile4.css:9`, la cinta que más se ve hoy; bajo viewport corto pasan a 10px/2px (gramática 13).

**Tokens:** `--font-mono`, `--tracking-mark`, `--ink-3`, `--accent`, `--rule`, `--space-3`.

**Markup canónico:**
```html
<h2 class="k-cap k-cap--rule">Biblioteca</h2>

<header class="k-cap"><span>Agenda</span><span class="k-cap__count">12 palabras</span></header>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m4-sec` + `::after` (mobile4.css:9-10) | `.k-cap k-cap--rule` (el filete se conserva); sube de 10 a 11px |
| `.fin-cap` (finish.css:8) | `.k-cap`; su `letter-spacing: 0.12em` pasa a `--tracking-mark` (0.08em) |
| `.fin-sched__head` (finish.css:779) | `.k-cap` (ya es `space-between`) |
| `.fin-sched__count` (finish.css:786) | `.k-cap__count` |
| `.qcard__head` (finish.css:283) | `.k-card__head` con una `.k-cap` dentro (átomo 3) |
| `.taller .rail h2` (taller.css:81) | `.k-cap`; baja de `--t-meta` 13px a 11px |
| `.taller .preview-head` (taller.css:212) | `.k-cap` con `.k-cap__count`; se pierde el filete inferior, que pasa a `--rule` a la derecha |
| `.taller .preview-head .flag` (taller.css:223) | no entra el aviso en acento. Ver «Pendientes» |
| `.kc-transcript__cap` (speak.css:205) | `.k-cap` |
| `.kp-chips__cap` (pages.css:666) | `.k-cap`. **Gastado por la migración 15**, y con él los tres encabezados de sección de Ajustes —«Cuenta», «Invitaciones», «Lista de espera»— como `.k-cap k-cap--rule`. Ahí apareció la junta que faltaba: `.k-cap + .k-field`, porque la cinta deja 2px a propósito («la etiqueta pertenece a lo que sigue») y lo que seguía traía **su propio** rótulo mono en versalitas |
| `.kp-returns__head` / `__count` (pages.css:704, :705) | `.k-cap` / `.k-cap__count` |
| `.path__kicker` (path.css:10) | `.k-cap`; su `0.14em` pasa a `--tracking-mark`. **Gastado por la migración 13**, y de paso muere el `k-mono` que `Module.tsx:137` le pintaba encima: la cinta ya es mono en versalitas, y las dos clases juntas eran la misma declaración dos veces |
| `.landing__bloque` + `h2` (landing.css:67, :72) | ~~`.k-hairline` + `.k-hero--quiet` (átomo 12)~~ → **`.k-cap k-cap--rule`**. Enmienda de la migración 10, la segunda de la serie. Este destino se escribió pensando que el héroe silencioso era otro escalón de titular, y no lo es: es *el* titular, y con él los tres bloques de promesa quedaban del mismo tamaño que el tagline (los dos a `clamp(28px, 8vw, 40px)`, o sea 31,2px medidos en 390px). La portada se quedaba sin titular. El filete de arriba no se pierde, cambia de sitio: el `::after` de `--rule` lo continúa a la derecha del rótulo, que es la gramática de la biblioteca. Los 28px del serif itálico sí mueren, como murieron los 112 del onboarding |
| `.landing__wl` + `__wl-title` (landing.css:88, :90) | igual que la anterior; las dos recetas duplicadas de la hoja colapsan en una |
| `.landing__bloque p` (landing.css:80) | `.k-note k-note--bare` (átomo 13): es prosa de interfaz, y el único registro serif que el sistema tiene para ella es la voz de Klara |
| `.landing__wl-body` (landing.css:99) | idem |
| `.ob5-kicker` (perfil-aprendizaje.css:8) | `.k-cap`; su mono de 10px sube al escalón único |
| `.ob5-hint` (perfil-aprendizaje.css:71) | `.k-cap` dentro de la nube de transporte, con `margin: 0` (armazón), como la del dock: ahí no encabeza una sección, dice qué toca hacer |
| `.m3-dock .estadoK` (mobile3.css:119) | `.k-cap k-cap--center` |
| `.m3-dock .estadoK .rec` (mobile3.css:141) | `.k-cap__count[data-tone="live"]` |
| `.m3-dock .estadoK button` (mobile3.css:143) | `.k-btn k-btn--text` dentro de la cinta: el área táctil la pone el botón, no la cinta |
| `.m3-statline` (mobile3.css:84) | `.k-cap k-cap--center` |
| `.m3-dock .miclbl` (mobile3.css:175, muerta) | `.k-cap k-cap--center` |

**Notas:** la cinta es texto, no control: no necesita 44px, pero los controles que lleve dentro sí. Cuando encabeza una lista se escribe como `<h2>` para que el lector de pantalla la use de índice; cuando es un rótulo suelto dentro de una tarjeta, `<span>`. El contador nunca lleva información que no esté también en la lista que encabeza. Hay tres gramáticas incompatibles hoy (mono con filete después, mono sin filete, serif itálica con filete antes) y el sistema se queda con la primera. La tercera —la de la portada— **entra también**, contra lo que decían estas Notas: la migración 10 la midió y el bloque editorial que se le ofrecía como alternativa era el titular de la pantalla, o sea le habría dado a un rótulo de sección el tamaño del titular. Se queda con la primera gramática, y el filete que traía delante pasa a `--rule`, detrás. El margen `18px 0 2px` —suelto arriba, pegado abajo— es deliberado: la etiqueta pertenece a lo que sigue, y esa promesa se cumple con dos juntas, no con el margen solo: `.k-cap + .k-note` (migración 10) y `.k-cap + .k-hero` (migración 11), las dos sin `:where()` porque los dos átomos de destino traen su propio margen (trampa 17).

---


### 7. Marca de nivel — `.k-level`

**Reemplaza:** global.css:347 `.k-level` + `::before` (:361) · onboarding.css:536 `.ob-level__code` y su tinte en tarjeta activa (:542) · sentence-view.css:48 `.k-chapter__level`.

**Elementos:** ninguno.

**Variantes:** `.k-level--bare` — sin caja: mono pelado, sin fondo ni punto. Entra porque es la forma viva en dos hojas (`ob-level__code` y `k-chapter__level`); sin ella, migrar SentenceView y StepLevel obliga a meter una insignia donde hoy hay una etiqueta.

**Estados:** **A0 · A1 · A2 · B1 · B2 · C1 · C2** — el nivel es el texto del elemento; no hay un selector por nivel y el color no cambia con él (la paleta es tonal a propósito, §4 del brief: «no arcoíris»). `[data-active="true"]`: color `--accent`, para cuando el contenedor que la lleva está seleccionado.

**Medidas:** `display: inline-flex`, `align-items: center`, `gap: 6px`, `padding: 4px 10px`, fondo `--lvl-bg`, color `--lvl-ink`, mono 11px `500`, `letter-spacing: var(--tracking-mark)`, versalitas, radio `var(--r-sm)`; `::before` es un punto de 5px en `currentColor` a `opacity: 0.6`. `--bare`: sin fondo, sin padding, sin radio, sin punto, color `--ink-2`.
Literales justificados: **11px**, **5px** del punto, **6px** de gap y **4px 10px** de padding son los valores textuales de `global.css:347-369`, que la regla 7 de la gramática obliga a conservar. El 11px coincide con el escalón mono único, así que este átomo no aporta deuda; los otros tres literales sí, y quedan registrados en las objeciones.

**Tokens:** `--lvl-bg`, `--lvl-ink`, `--ink-2`, `--accent`, `--r-sm`, `--font-mono`, `--tracking-mark`.

**Markup canónico:**
```html
<span class="k-level">B1</span>

<span class="k-level k-level--bare" data-active="true">A2</span>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.k-level` (global.css:347) | `.k-level` (idéntico) |
| `.k-level::before` (global.css:361) | `.k-level::before` (idéntico) |
| `.ob-level__code` (onboarding.css:536) | `.k-level k-level--bare`; sube de 10px a 11px |
| `.ob-level__card[data-active="true"] .ob-level__code` (onboarding.css:542) | `.k-level[data-active="true"]` — el atributo se conserva textual porque aquí sí es «mi contenedor está activo», no una elección del propio elemento |
| `.k-chapter__level` (sentence-view.css:48) | `.k-level k-level--bare` |
| el punto «●» literal del JSX (SentenceView.tsx:365) | se pierde como texto: en la variante con caja lo pone `::before`; en `--bare` no hay punto |

**Notas:** no es interactiva, así que el mínimo de 44px no le aplica. El nivel se escribe en mayúsculas en el DOM (`B1`), no se depende de `text-transform` para el significado. `--lvl-bg`/`--lvl-ink` ya existen en los dos temas y ninguna hoja los consumía; con este átomo empiezan a usarse.

---

### 8. Chip — `.k-chip`

**Reemplaza:** global.css:371 `.k-chip`, `:hover` (:384), `[data-selected="true"]` (:388) · taller.css:175 `.taller .chip`, `.x` (:189), `.add` (:192), `.chip-input` (:197) · pages.css:668 `.kp-chip`, `:hover` (:679), `[data-selected="true"]` (:680) · perfil-aprendizaje.css:65 `.ob5-cloud .k-chip` y su compresión (:107) · perfil-aprendizaje.css:56 `.ob5-tri button` con `.si`/`.no[data-on]` (:58-59) · finish.css:497 `.qcard__leg` + `[data-tone]` (:515-517) · finish.css:826 `.fin-sched__tag` · sentence-view.css:467 `.k-feedback__pill` + `[data-tone]` (:485-487) · sentence-view.css:307 `.k-hint kbd` · speak.css:263 `.kc-foco` + sus cuatro hijos (:272-275) · speak.css:214 `.kc-turn__fix` + `[data-tone="clear"]` (:192) · taller.css:288 `.taller .kbd` · mobile4.css:39 `.m4-chips .k-chip`.

**Elementos:** `.k-chip__dot` — punto de 6px que lleva el tono. `.k-chip__x` — la cruz de eliminar.

**Variantes:** `.k-chip--static` — informativo, no tocable (leyenda): sin `cursor: pointer`, sin `:hover`, sin mínimo táctil.

**Estados:**
- **reposo**: transparente, borde 1px `--rule`, color `--ink-2`.
- `:hover`: borde y color a `--ink`.
- `[data-selected="true"]` (**seleccionado**): fondo y borde `--ink`, color `--paper`.
- `:disabled` (**deshabilitado**): `opacity: 0.45`, `pointer-events: none`, `cursor: not-allowed`. Es nuevo: hoy ninguna de las siete implementaciones lo pinta.
- `:active`: `transform: scale(0.96)`.
- `[data-tone="good|ok|bad"]`: tiñe `.k-chip__dot` con `--score-good` / `--score-ok` / `--score-bad`; el chip no cambia.

**Medidas:** `display: inline-flex`, `align-items: center`, `gap: var(--space-2)`, `padding: 11px 14px`, `min-height: 44px`, radio `var(--r-pill)`, `var(--font-sans)` `var(--t-mark)`, borde 1px, `transition: all var(--dur-fast) var(--ease-out)`. `--static`: `min-height: 0`, `padding: 4px 9px`, mono 11px con `--tracking-mark`. `__dot`: 6px, círculo.
Literales justificados: **11px 14px** y **min-height: 44px** son los de `perfil-aprendizaje.css:65`, la única implementación que ya cumple §7.2; el cuerpo es `--t-mark` (14px), que es exactamente el valor base de `global.css:379`, así que se escribe con token; **6px** del punto y **4px 9px** del estático son los de `finish.css:497-510`; los 10px del estático suben a 11 por la gramática 10.

**Tokens:** `--rule`, `--ink`, `--ink-2`, `--paper`, `--r-pill`, `--space-2`, `--t-mark`, `--font-sans`, `--font-mono`, `--tracking-mark`, `--score-good`, `--score-ok`, `--score-bad`, `--dur-fast`, `--ease-out`.

**Markup canónico:**
```html
<button type="button" class="k-chip" data-selected="true" aria-pressed="true">Comida</button>

<span class="k-chip k-chip--static" data-tone="good"><span class="k-chip__dot" aria-hidden="true"></span>4 claras</span>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.k-chip` (global.css:371) | `.k-chip`; **crece a 44px de alto** (hoy ≈33), único cambio visible de medida en la compatibilidad |
| `.k-chip:hover` (global.css:384) / `[data-selected="true"]` (global.css:388) | idénticos |
| `.k-chip` `font-size: 14px` (global.css:379) | `var(--t-mark)`, que vale exactamente eso |
| `.ob5-cloud .k-chip` (perfil:65) | el override desaparece: sus valores son ahora la base |
| `.ob5-cloud .k-chip` @720 → 40px (perfil:107) | se pierde: el mínimo táctil no admite excepción por altura de viewport (gramática 13) |
| `.m4-chips .k-chip` 12.5px (mobile4.css:39) | el override desaparece; sube a `--t-mark` |
| `.m4-chips` (mobile4.css:38) / `.kp-chips__row` (pages.css:667) / `.snew__chips` (pages.css:217) / `.taller .chips` (taller.css:168) | `.k-wrap` (gramática 12) |
| `.kp-chip` (pages.css:668) | `.k-chip k-chip--static` — son `<span>` sin `onClick` (Practice.tsx:306-314): dejan de fingir que son controles |
| `.kp-chip:hover` / `[data-selected]` (pages.css:679, :680) | `[data-selected="true"]` se conserva; el `:hover` se pierde en la variante estática |
| `.taller .chip` (taller.css:175) | `.k-chip` |
| `.taller .chip .x` (taller.css:189) | `.k-chip__x` |
| `.taller .chip.add` (taller.css:192) | no entra el borde discontinuo de «añadir». Ver «Pendientes» |
| `.taller .chip-input` (taller.css:197) | `.k-field--chip`: no entra. Ver «Pendientes» |
| `.ob5-tri button` cuadrado 44px (perfil:56) | **no entra, confirmado por la migración 11**: es la píldora, con «Sirve» y «No» escritos en vez de ✓/✕ |
| `.ob5-tri button.si[data-on="true"]` (perfil:58) | `[data-selected="true"]` |
| `.ob5-tri button.no[data-on="true"]` (perfil:59) | **no entra, decidido por la migración 11**: papel apagado + tinta baja se leía como *deshabilitado*, no como *elegido*. Cuál de los dos está pulsado lo dicen la posición y el rótulo; una segunda manera de estar pulsado sobraba |
| `.qcard__leg` + `::before` (finish.css:497, :510) | `.k-chip k-chip--static` + `.k-chip__dot` |
| `.qcard__leg[data-tone="good"\|"ok"\|"bad"]` (:515-517) | `[data-tone]` sobre el chip; los tres literales pasan a `--score-*` |
| `.fin-sched__tag` (finish.css:826) | `.k-chip k-chip--static`; pierde el radio de 3px y el fondo `--accent-wash`, gana la píldora |
| `.k-feedback__pill` + `[data-tone]` (sentence-view.css:467, :485-487) | `.k-chip k-chip--static` + `.k-chip__dot` |
| `.k-hint kbd` (sentence-view.css:307) | `.k-chip k-chip--static` sobre `<kbd>`; el radio de 3px pasa a `--r-pill` |
| `.taller .kbd` (taller.css:288) | `.k-chip k-chip--static` sobre `<kbd>` |
| `.kc-turn__fix` + `[data-tone="clear"]` (speak.css:214, :192) | `.k-chip k-chip--static` (es un acuse, no una nota); el estado base en acento nunca se ve hoy y se pierde sin pérdida real (ver «Trampas conocidas») |
| `.kc-foco` + `__dot`/`__cap`/`__sound`/`__ipa` (speak.css:263-275) | `.k-chip k-chip--static` + `.k-chip__dot` + contenido; el sonido en serif itálica de 20px se pierde y pasa a la tipografía del chip |

**Nota de cascada (migración 11):** el hover se escribe `.k-chip:not(.k-chip--static, [data-selected="true"]):hover`. Sin excluir el seleccionado, el hover (0,3,0) le ganaba a `[data-selected]` (0,2,0) y le ponía `color: var(--ink)` a un chip con fondo de tinta: **rótulo negro sobre negro, o sea el chip pulsado desapareciendo bajo el cursor**. No se ve en el teléfono (no hay hover) ni en la hoja de componentes (nadie pasa por encima); lo enseñó una captura del triaje del cuestionario. Aquí el orden no basta —como sí bastaba en el `:disabled` del átomo 1—: manda la especificidad.

**Notas:** el chip tocable es `<button>` con `aria-pressed`; el estático es `<span>` (o `<kbd>`). El salto de 33 a 44px de alto es deliberado y es la única excepción a la regla 7 de la gramática: §7.2 no admite excepciones y `hoja.check.mjs:96-101` lo mide. Con alemán largo el chip no trunca: envuelve, porque su contenedor es `.k-wrap` (gramática 12). El punto de tono nunca es la única señal: siempre va con texto.

---

### 9. Hoja inferior — `.k-sheet` (+ `.k-scrim`)

**Reemplaza:** mobile3.css:154 `.m3-sheet` con `@keyframes m3-up` (:155), `.grab` (:156), `.fila1` (:157), `.lemma` (:158), `.art` (:159), `.trad` (:160), `.k-btn` (:161) · mobile3.css:151 `.m3-scrim`, su variante oscura (:152) y `@keyframes m3-fade` (:153) · mobile3.css:31 `.m3-menu` + `@keyframes m3-menu-in` (:32) y `.m3-menu-item` (:33-37) (ver átomo 10: el menú es elemento de la barra de pestañas, pero comparte el velo).

**Elementos:** `.k-sheet__grab` — el tirador de 34×3px. `.k-sheet__head` — la primera fila (lema + acción). `.k-sheet__body` — el contenido.

**Variantes:** ninguna.

**Estados:**
- **entrando**: `animation: k-sheet-in var(--dur-med) var(--ease-page) both` — `translateY(24px)` + `opacity 0` → reposo. El velo entra a la vez con `k-scrim-in`.
- **en reposo**: sin transformación.
- Bajo `prefers-reduced-motion` las dos animaciones son `none` y la hoja aparece ya en reposo: no se pierde información porque el velo, el borde y la sombra bastan para leerla como capa.

**Medidas:** `position: absolute; left: 0; right: 0; bottom: 0; z-index: 21`, fondo `--paper`, `border-top: 1px solid var(--rule)`, radio `var(--r-lg) var(--r-lg) 0 0`, sombra `var(--shadow-pop)`, `padding: 10px 22px 24px` con `padding-bottom: calc(24px + env(safe-area-inset-bottom))`. `.k-scrim`: `position: absolute; inset: 0; z-index: 20`, fondo `var(--scrim)`. `__grab`: 34×3px, radio `var(--r-xs)`, fondo `--rule`, `margin: 0 auto var(--space-4)`.
Literales justificados: **10px 22px 24px** y **34×3px** son los valores de `mobile3.css:154-156`; **z-index 20/21** son los que ya conviven con el menú (22) y hay que mantener el orden. El ancestro posicionado es `.k-app` (gramática 12), no `.m3-app`.

**Tokens:** `--paper`, `--rule`, `--scrim`, `--r-lg`, `--r-xs`, `--space-4`, `--shadow-pop`, `--dur-med`, `--ease-page`.

**Markup canónico:**
```html
<div class="k-scrim" data-role="cerrar"></div>
<div class="k-sheet" role="dialog" aria-modal="true" aria-label="Palabra">
  <span class="k-sheet__grab" aria-hidden="true"></span>
  <div class="k-sheet__head">…</div>
  <div class="k-sheet__body">…</div>
</div>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-sheet` (mobile3.css:154, muerta) | `.k-sheet` |
| `@keyframes m3-up` (mobile3.css:155) | `@keyframes k-sheet-in` |
| `.m3-sheet .grab` (:156) | `.k-sheet__grab` |
| `.m3-sheet .fila1` (:157) | `.k-sheet__head` |
| `.m3-sheet .lemma` / `.art` / `.trad` (:158-160) | `.k-card__word` / `.k-card__article` / `.k-card__tx` (átomo 3: el contenido de la hoja es una ficha plana) |
| `.m3-sheet .k-btn` (:161) | `.k-btn k-btn--block` |
| `.m3-scrim` (:151) y su variante oscura (:152) | `.k-scrim` con `var(--scrim)`; la regla `[data-theme="dark"]` desaparece porque el token ya cambia |
| `@keyframes m3-fade` (:153) | `@keyframes k-scrim-in` |
| `.m3-art-der/-die/-das` (mobile3.css:162, muertas) | `.k-card__article[data-gender]` con `--art-*` |
| `.m3-app` como ancestro posicionado (mobile3.css:10) | `.k-app` (gramática 12) |

**Notas:** la hoja es `role="dialog" aria-modal="true"` con foco atrapado y cierre por `Escape`; el velo es un `<div>` sin rol al que el `.tsx` engancha el `onClick` de cerrar, con el botón de cerrar real dentro de la hoja para que el teclado tenga salida. `env(safe-area-inset-bottom)` es obligatorio: sin él la acción principal queda bajo la barra de gestos con `targetSdk 36`, que es el bug del commit 18cc68e. El velo es un bloque propio y no `.k-sheet__scrim` porque lo comparten la hoja inferior y el menú de la barra de pestañas.

---

### 10. Barra de pestañas — `.k-tabs`

**Reemplaza:** mobile3.css:23 `.m3-tabbar`, `.m3-tab` (:24), `.ic` (:25), `.lbl` (:26), `[data-active="true"]` (:27-28) · mobile4.css:6 `.m3-tabbar.m4` · mobile3.css:31 `.m3-menu` + `@keyframes m3-menu-in` (:32), `.m3-menu-item` (:33), `+ .m3-menu-item` (:34), `.ch` (:35), `:active` (:36), `[data-active="true"]` (:37) · mobile3.css:7 `:root{--tb:58px}`.

**Elementos:** `.k-tabs__tab` — un destino. `.k-tabs__ic` — el icono. `.k-tabs__lbl` — el rótulo en mono. `.k-tabs__menu` — el desplegable «más». `.k-tabs__menu-item` — una entrada del desplegable. `.k-tabs__menu-ch` — el galón `›`.

**Variantes:** `.k-tabs--2`, `.k-tabs--3`, `.k-tabs--4` — número de columnas de la rejilla.

**Estados:**
- `.k-tabs__tab[data-active="true"]` (**activo**): color `--ink` y el rótulo con `border-bottom-color: var(--ink)`.
- `.k-tabs__menu-item[data-active="true"]`: fondo `--paper-3`. Es `--paper-3` y no `--paper-2` porque `--paper-2` sobre el `--paper` del menú da 1,06:1 en claro y 1,11:1 en oscuro —o sea, el destino actual no se distinguía del resto en ninguno de los dos temas.
- `.k-tabs__menu-item:active`: fondo `--paper-2`, un paso por debajo del actual: el pulsado es momentáneo y va con el dedo encima.
- **con menú desplegable**: presencia de `.k-tabs__menu`, que entra con `k-menu-in` y se acompaña de `.k-scrim`.
- **2, 3 y 4 destinos**: las tres variantes de rejilla.

**Medidas:** `.k-tabs`: `flex: 0 0 auto`, `display: grid`, `border-top: 1px solid var(--rule)`, fondo `--paper`, `height: calc(var(--tb) + env(safe-area-inset-bottom))`, `padding-bottom: calc(4px + env(safe-area-inset-bottom))`, con `box-sizing: border-box` para que el inset crezca el alto en vez de aplastar el tab; y `.k-app:has(.k-tabs__menu) .k-tabs { position: relative; z-index: 22 }`, porque con el menú desplegado la barra es la que lo sostiene y sin eso queda bajo el velo (20) con sus rótulos a ~1,5:1 y la pestaña «Más» leyéndose deshabilitada —acotado con `:has` para que la hoja inferior (21), que sí tiene que taparla, siga tapándola; el menú, hermano y también en 22, se pinta encima por orden de DOM. `.k-tabs__tab`: columna centrada, `gap: 3px`, `min-height: 44px`, color `--ink-3` (marginalia por la gramática §9; en `--ink-4` la navegación entera daba 2,7:1 en claro y 2,4:1 en oscuro a 11px y se leía deshabilitada, y el contraste con el destino actual lo sigue diciendo el salto `--ink-3` → `--ink` más el subrayado). `.k-tabs__ic`: 20px de alto. `.k-tabs__lbl`: mono 11px, `letter-spacing: var(--tracking-mark)`, versalitas, `border-bottom: 1px solid transparent`, `padding-bottom: 2px`. `.k-tabs__menu`: `position: absolute; right: 10px; bottom: calc(var(--tb) + env(safe-area-inset-bottom) + var(--space-2)); z-index: 22`, `min-width: 196px`, fondo `--paper`, borde 1px `--rule`, radio `var(--r-md)`, sombra `var(--shadow-pop)`, `padding: 5px`. `.k-tabs__menu-item`: `min-height: 44px`, `padding: var(--space-3)`, radio `var(--r-sm)`, **sans 15px** (los controles son sans: es el mismo argumento con el que muere el serif de `.k-tool--mic`).
Literales justificados: **`--tb: 58px`** se declara en `:root` dentro de `sistema.css` (gramática 12) porque el menú se posiciona desde fuera del bloque (TabBar.tsx:39-41 lo renderiza como hermano del `<nav>`) y necesita el mismo número; **11px** del rótulo es el escalón mono único (sube desde los 10px de `mobile3.css:26`, y el `0.1em` pasa a `--tracking-mark`); **196px** y **5px** son los de `mobile3.css:31-33`; **44px** del ítem de menú sustituye a los 46px de `mobile3.css:33`, que eran 2px sin razón sobre el mínimo táctil; **15px** del ítem es el cuerpo de control del sistema.

**Tokens:** `--paper`, `--paper-2`, `--paper-3`, `--rule`, `--ink`, `--ink-3`, `--ink-4`, `--r-md`, `--r-sm`, `--space-2`, `--space-3`, `--shadow-pop`, `--font-mono`, `--font-sans`, `--tracking-mark`, `--dur-fast`, `--dur-med`, `--ease-out`, `--ease-page`.

**Markup canónico:**
```html
<nav class="k-tabs k-tabs--2" aria-label="Secciones">
  <button type="button" class="k-tabs__tab" data-active="true" aria-current="page">
    <span class="k-tabs__ic" aria-hidden="true"><svg …/></span><span class="k-tabs__lbl">Biblioteca</span>
  </button>
  <button type="button" class="k-tabs__tab"><span class="k-tabs__ic" aria-hidden="true"><svg …/></span><span class="k-tabs__lbl">Más</span></button>
</nav>

<div class="k-tabs__menu" role="menu" aria-label="Más">
  <button type="button" class="k-tabs__menu-item" role="menuitem" data-active="false">Perfil <span class="k-tabs__menu-ch" aria-hidden="true">›</span></button>
</div>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-tabbar` (mobile3.css:23) | `.k-tabs k-tabs--4` |
| `.m3-tabbar.m4` (mobile4.css:6) | `.k-tabs k-tabs--2` |
| `.m3-tab` (mobile3.css:24) | `.k-tabs__tab` |
| `.m3-tab .ic` (:25) | `.k-tabs__ic` |
| `.m3-tab .lbl` (:26) | `.k-tabs__lbl`; sube de 10 a 11px y su `0.1em` pasa a `--tracking-mark` |
| `.m3-tab[data-active="true"]` (:27-28) | `.k-tabs__tab[data-active="true"]` (atributo conservado textual: es navegación) |
| `.m3-menu` (:31) | `.k-tabs__menu` |
| `@keyframes m3-menu-in` (:32) | `@keyframes k-menu-in` |
| `.m3-menu-item` (:33) | `.k-tabs__menu-item`; el serif de 17px pasa a sans 15px y el alto de 46 a 44px |
| `.m3-menu-item + .m3-menu-item` (:34) | igual, con `.k-tabs__menu-item` |
| `.m3-menu-item .ch` (:35) | `.k-tabs__menu-ch` |
| `.m3-menu-item:active` / `[data-active="true"]` (:36, :37) | idénticos sobre el nombre nuevo |
| `:root{--tb:58px}` (mobile3.css:7) | `:root{--tb:58px}` en `sistema.css`, junto a `.k-app` |
| `.m3-scrim` bajo el menú (TabBar.tsx:39) | `.k-scrim` (átomo 9) |

**Notas:** el `<nav>` lleva `aria-label` y el destino activo `aria-current="page"`, para que el color no sea la única señal. El menú es `role="menu"` con sus `role="menuitem"`, cierra con `Escape` (ya implementado en TabBar.tsx:28-35) y devuelve el foco al tab que lo abrió. La safe-area es obligatoria en el alto y en el `bottom` del menú. Con reduced-motion el menú aparece sin la entrada de `k-menu-in`. El menú se posiciona contra `.k-app` (gramática 12).

---

### 11. Línea superior — `.k-topline`

**Reemplaza:** mobile3.css:17 `.m3-top` + `.marca` (:18) + `.wordmark` (:19) · mobile3.css:102 `.m3-sess-top` + `.titulo` (:103) + `.der` (:104) y su safe-area (:137) · mobile4.css:30 `.m4-backrow` + `.der` (:31) · finish.css:743 `.fin-back-row` · onboarding.css:15 `.ob__chrome`, `__chrome-mark` (:32), `__chrome-label` (:37), `__chrome-spacer` (:45) · sentence-view.css:18 `.k-chapter` + `__title` (:38) + `__name` (:40) · recall-review.css:48 `.rr-head` + `__title` (:62) + `__name` (:64) + `__meta` (:71) · taller.css:36 `.taller .masthead` + `h1` (:43) + `.tally` (:51) + `.tally a` (:55, selector inerte) · speak.css:79 `.kc-top` + `__time` (:80) · perfil-aprendizaje.css:20 `.ob5-top` + `.bloque` (:21) + `.cuenta` (:22) · gender-review.css:12 `.gr__head` + `.gr__title` (:19) + `.gr__progress` (:28) · landing.css:115 `.landing__footer` + `a` (:127), :42 `.landing__login` + `-q` (:48/53) + `-a` (:56).

**Elementos:** `.k-topline__exit` — la celda de salida (izquierda). `.k-topline__mark` — el lockup marca + wordmark (centro o izquierda). `.k-topline__title` — el título de la sesión. `.k-topline__meta` — el contador o el reloj (derecha).

**Variantes:** `.k-topline--session` — rejilla `1fr auto 1fr` con salida · título · contador. `.k-topline--foot` — la misma tira al pie, con el filete arriba y la tinta un paso más apagada.

**Estados:**
- base (**marca**): `justify-content: space-between`, marca a la izquierda y meta a la derecha.
- `--session` (**sesión con progreso**): tres celdas; la barra de progreso va en una fila hermana, no dentro, para que el título pueda crecer.

**Medidas:** `display: flex`, `justify-content: space-between`, `align-items: baseline`, `flex: 0 0 auto`, mono 11px, `letter-spacing: var(--tracking-mark)`, versalitas, color `--ink-3`, **sin inset propio** —lo pone el contenedor, y desde la migración 10 solo hay uno: `.k-page` (gramática 12). El otro era la portada (`landing.css:13`), que ahora cuelga de la misma página. Declararlo también aquí lo sumaba dos veces en todo teléfono con muesca. `--session`: `display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: var(--space-3); padding: 14px 22px; padding-top: calc(14px + env(safe-area-inset-top))`. `__mark`: `inline-flex`, `align-items: baseline`, `gap: 7px`, color `--ink`. `__mark .wordmark`: serif itálica 17px `500`, `letter-spacing: -0.02em`, sin versalitas. `__title`: mono 11px itálica, versalitas, `--ink-3`, centrado, con `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` (aquí sí se trunca: es un rótulo de orientación, no contenido). `__meta`: mono 11px `--ink-3`, `tabular-nums`, `flex-shrink: 0`.
Literales justificados: **17px** y **-0.02em** del wordmark y **7px** de gap son los de `mobile3.css:18-19`; **14px 22px** los de `mobile3.css:102`. El cuerpo mono **sube de 10 a 11px**: `mobile3.css:17` declara 10px, y la gramática 10 lo unifica con el resto de la marginalia —incluido `.k-tabs__lbl`, que sube con él, para que la marginalia de arriba y la de abajo midan lo mismo.

**Tokens:** `--font-mono`, `--font-serif`, `--tracking-mark`, `--ink`, `--ink-3`, `--rule`, `--space-3`.

**Markup canónico:**
```html
<header class="k-topline">
  <span class="k-topline__mark"><span class="klara-mark">…</span><span class="wordmark">Klara</span></span>
  <span class="k-topline__meta">Miércoles</span>
</header>

<header class="k-topline k-topline--session">
  <button type="button" class="k-btn k-btn--text k-topline__exit">Salir</button>
  <span class="k-topline__title">Beim Arzt</span>
  <span class="k-topline__meta">03 / 12</span>
</header>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-top` (mobile3.css:17) | `.k-topline`; sube de 10 a 11px |
| `.m3-top .marca` (:18) | `.k-topline__mark` |
| `.m3-top .marca .wordmark` (:19) | `.k-topline__mark .wordmark` (nombre conservado) |
| `.m3-sess-top` (mobile3.css:102) | `.k-topline k-topline--session` |
| `.m3-sess-top .titulo` (:103) | `.k-topline__title`; sube de 10 a 11px |
| `.m3-sess-top .der` (:104) | `.k-topline__meta`; sube de 10 a 11px y su `0.06em` pasa a `--tracking-mark` |
| `.m3-sess-top` safe-area (:137) | integrado en `--session` |
| `.m4-backrow` + `.der` (mobile4.css:30-31) | `.k-topline` con `.k-btn--text` a la izquierda y `.k-topline__meta` |
| `.fin-back-row` (finish.css:743) | `.k-topline` con dos `.k-btn--text` |
| `.ob__chrome` (onboarding.css:15) | `.k-topline k-topline--session` |
| `.ob__chrome-mark` / `__chrome-label` (:32, :37) | `.k-topline__mark` / `.wordmark` |
| `.ob__chrome-spacer` (:45) | se pierde: la rejilla `1fr auto 1fr` centra sin ranura fantasma |
| `.k-chapter` (sentence-view.css:18) | `.k-topline k-topline--session` |
| `.k-chapter__title` / `__name` (:38, :40) | `.k-topline__title` (el serif itálico en mayúsculas se pierde: mono para la marginalia) |
| `.k-chapter__k` (:39) | `.klara-mark` dentro de `.k-topline__mark` |
| `.k-chapter__level` (:48) | `.k-level k-level--bare` en `.k-topline__meta` |
| `.rr-head` (recall-review.css:48) | `.k-topline k-topline--session` |
| `.rr-head__title` / `__name` / `__meta` (:62, :64, :71) | `.k-topline__title` / idem / `.k-topline__meta` |
| `.rr-head__k` (:63) | `.klara-mark` |
| `.taller .masthead` (taller.css:36) | `.k-topline` |
| `.taller .masthead h1` (:43) | `.k-hero--quiet` (átomo 12): un título de 40px no es marginalia |
| `.taller .tally` (:51) | `.k-topline__meta`; **gana la mono** que hoy no tiene (`className="tally mono"` apunta a una clase inexistente) |
| `.taller .tally a` (:55) | selector inerte contra un `<button>`: se borra; la acción pasa a `.k-btn--text` |
| `.kc-top` (speak.css:79) | `.k-topline k-topline--session` |
| `.kc-top__time` (:80) | `.k-topline__meta` |
| `.ob5-top` (perfil:20) | `.k-topline k-topline--session` |
| `.ob5-top .bloque` / `.cuenta` (:21, :22) | `.k-topline__title` / `.k-topline__meta` |
| el `style={{justifySelf:"start"}}` del botón atrás (perfil/views.tsx:183-196) | `.k-topline__exit`, que ya alinea |
| ~~`.gr__head` → `.k-topline k-topline--session`~~ | **enmendado por la migración 12: `.k-topline` a secas.** `--session` es la tira que cuelga del cascarón —tres pistas y su propio relleno con inset— y `.gr__head` es de dos piezas dentro de una página que ya trae relleno: es el bloque base declaración por declaración (`flex`, `space-between`, `baseline`). Aquí no hay salida que colocar en una tercera pista |
| `.gr__title` (:19) | `.k-topline__title` cuando encabeza la sesión; `.k-hero--quiet` cuando va suelto en las otras cuatro fases |
| `.gr__progress` (:28) | `.k-topline__meta`; su `font-size: 12px` era letra muerta porque `.k-mono` gana la cascada |
| `.landing__footer` + `a` (landing.css:115, :127) | `.k-topline k-topline--foot` con `.k-link` dentro; sube de 10 a 11px y el enlace pasa de `--ink-3` con `:hover` en `--ink` a `--ink-2` con subrayado |
| `.landing__login` (landing.css:42) | se pierde el envoltorio: la tira ya reparte con `space-between` y el hueco de 6px lo da el espacio del texto |
| `.landing__login-q` / `-a` (:48, :56) | `.k-topline__meta` con un `.k-link` dentro (ver el mapa del átomo 1, que corrige el destino de los dos) |

**Notas:** la línea superior es `<header>`; la variante al pie, `<footer>`. Un `.k-link` dentro de la tira —arriba o al pie— lleva `min-height: 44px` con el contenido al fondo (`align-items: flex-end`): el suelo lo pone la tira porque `.k-link` es una utilidad de `global.css` y no declara altura, y el contenido va al fondo porque el subrayado del enlace es el canto de su caja — centrado en los 44px, la raya se despega 12px de la palabra y se lee como un filete del encabezado (medido en la migración 10, que estrenó el de arriba). El botón de salir es un `.k-btn--text` con su área de 44×44px, no un texto suelto de 16px como hoy en cinco hojas. `env(safe-area-inset-top)` es obligatorio en toda ruta de alto completo, y lo pone el contenedor: la tira solo lo lleva en `--session`, la única que cuelga de `.k-app` sin `.k-page` de por medio (Story.tsx:232-234). El título se trunca con elipsis a propósito —es la única pieza del sistema que lo hace— porque es orientación y no contenido; el contenido alemán nunca se trunca.

---


### 12. Bloque héroe — `.k-hero`

**Reemplaza:** mobile3.css:56 `.m3-hero`, `:active` (:57), `:disabled` (:58), `.tag` (:59), `.fila` (:60), `h2` (:61), `.dek` (:62), `.arrow` (:63) y su compresión (:92-93) · mobile4.css:58 `.m3-hero .dek{display:none}` · mobile3.css:40 `.m3-saludo` (muerta) y :66 `.m3-mapa-h1` (muerta) · mobile4.css:7 `.m4-saludo`, :32 `.m4-h1` · finish.css:102 `.fin-hero` + `__cap` (:108), `__cap-text` (:119), `__title` (:126), `__meta` (:136), `__sep` (:153) · finish.css:202 `.quiz-hero` + `__title` (:207), `__sub` (:217) · onboarding.css:257 `.ob-welcome` + `__hello` (:272), `__lede` (:290), `__sub` (:324), `__cta` (:331), `__tip` (:339) · onboarding.css:626 `.ob-done` + `__title` (:637), `__name` (:649), `__sub` (:655) · onboarding.css:153 `.ob-prompt` + `__title` (:158, y su `@media max-860` de :170), `__sub` (:172), `__rule` (:180) · landing.css:24 `.landing__tagline`, :34 `.landing__support` · pages.css:36 `.home__feature` y :315 `.story-end` (muertas).

**Elementos:** `.k-hero__tag` — la tira mono de arriba. `.k-hero__title` — el titular serif. `.k-hero__dek` — la bajada en serif itálica. `.k-hero__arrow` — la flecha de afordancia. `.k-hero__meta` — la línea de cifras.

**Variantes:** `.k-hero--quiet` — editorial: solo tipografía, sin superficie ni afordancia; es el titular de una pantalla de lectura y de la landing.

**Estados:**
- reposo (**activo**): fondo `--ink`, texto `--paper`, radio `var(--r-md)`, tocable entero.
- `:active`: `transform: scale(0.985)`.
- `:disabled` (**deshabilitado**): `opacity: 0.45`, `transform: none`, `cursor: default`.
- `--quiet` no tiene estados: no es tocable, y la acción va en un `.k-btn` hermano.

**Medidas:** `display: grid`, `grid-template-columns: 1fr auto`, `align-items: baseline`, `column-gap: var(--space-3)` —la rejilla es la que reparte título y flecha en la misma línea de base, y por eso muere `.m3-hero .fila`; `__tag`, `__dek` y `__meta` cruzan las dos columnas con `grid-column: 1 / -1`—, `width: 100%`, `text-align: left`, `padding: 18px 20px`, `margin-top: 18px`, `flex: 0 0 auto`, radio `var(--r-md)`, y dos juntas hacia lo que venga detrás: `margin-top: var(--space-3)` sobre una `.k-bar` inmediatamente posterior (`.k-hero + .k-bar`) y `var(--space-4)` sobre un `.k-wrap` (`.k-hero + .k-wrap`, la migración 10: el botón que sigue al titular de la portada, con los 16px que traía el `margin-bottom` de `.landing__support`; ninguna de las dos piezas trae margen y sin esto el botón se pegaba a la bajada) —el bloque no trae margen inferior y la barra no trae ninguno, así que sin esa junta el filete se lee como subrayado del titular; 12px son los de `.m4-h1` bajo la misma barra en la portada de curso. `__tag`: flex `space-between`, mono 11px, `letter-spacing: var(--tracking-mark)`, versalitas, `opacity: 0.6`, `margin-bottom: var(--space-2)`. `__title`: serif `clamp(22px, 6.6vw, 25px)`, `line-height: 1.12`, `letter-spacing: var(--tracking-tight)`, peso 600. `__dek`: serif itálica `var(--t-mark)`, `opacity: 0.72`. `__arrow`: serif itálica 24px, `grid-column: 2` (no se encoge ni baja de línea). `__meta`: serif itálica `var(--t-body)` —los 18px de `finish.css:145` caen en el token—, flex con `flex-wrap: wrap`, `align-items: baseline`, `gap: var(--space-2)`, `margin-top: var(--space-2)`, `opacity: 0.72`, y su `strong` redondo en peso 500 con `font-variant-numeric: tabular-nums`. `--quiet`: **`background: none; color: var(--ink); padding: 0`** —el bloque base es tinta sólida sobre papel, y sin este reset el titular saldría papel sobre papel—, `__title` en serif `clamp(28px, 8vw, 40px)`, peso 500, `__dek` y `__meta` en `--ink-3` sin `opacity` (y el `strong` del `__meta` en `--ink`).
Literales justificados: **18px 20px**, **25px/22px**, **24px** de la flecha y **0.6/0.72** de opacidad son los valores de `mobile3.css:56-63`; **`opacity`** se usa en vez de un token de tinta porque el bloque es sólido y `--ink-3` sobre `--ink` no existe. **40px** del techo de `--quiet` se escribe **literal y no como `var(--t-h2)`**: `pages.css:776-781` redefine `--t-h2` a 28px bajo `max-width: 600px`, o sea en el teléfono, donde el techo colapsaría contra el piso del `clamp` (ver «Trampas conocidas»). Bajo viewport corto el bloque comprime por la gramática 13, que sustituye a los dos recortes de hoy.

**Tokens:** `--ink`, `--ink-3`, `--paper`, `--r-md`, `--space-1`, `--space-2`, `--space-3`, `--t-mono`, `--t-mark`, `--t-body`, `--tracking-tight`, `--tracking-mark`, `--font-serif`, `--font-mono`, `--dur-fast`, `--ease-out`.

**Markup canónico:**
```html
<button type="button" class="k-hero">
  <span class="k-hero__tag"><span>Hoy</span><span>12 min</span></span>
  <span class="k-hero__title">Beim Arzt</span>
  <span class="k-hero__arrow" aria-hidden="true">→</span>
</button>

<header class="k-hero k-hero--quiet"><h1 class="k-hero__title">El taller</h1><p class="k-hero__dek">Tus textos, tus tarjetas.</p></header>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-hero` (mobile3.css:56) | `.k-hero`. Es la fila 1 del §5 del brief (BRIEF.md:189), que lo lista como botón: no lo es |
| `.m3-hero:active` / `:disabled` (:57, :58) | idénticos sobre `.k-hero` |
| `.m3-hero .tag` (:59) | `.k-hero__tag`; sube de 10 a 11px y su `0.1em` pasa a `--tracking-mark` |
| `.m3-hero .fila` (:60) | se pierde: la rejilla del bloque ya reparte título y flecha |
| `.m3-hero h2` (:61) | `.k-hero__title` |
| `.m3-hero .dek` (:62) | `.k-hero__dek` |
| `.m3-hero .arrow` (:63) | `.k-hero__arrow`; el `<span className="arrow">` de Inicio.tsx:94 es este, no el del botón |
| `.m3-hero` @720 (mobile3.css:92-93) y `.dek{display:none}` (mobile4.css:58) | el bloque `@media` único de la gramática 13; la bajada deja de esconderse |
| `.m3-saludo` / `.m4-saludo` (mobile3.css:40, mobile4.css:7) | `.k-hero--quiet` + `.k-hero__title` |
| `.m3-linea` (mobile3.css:42) | `.k-hero__dek` |
| `.m3-mapa-h1` / `.m4-h1` (mobile3.css:66, mobile4.css:32) | `.k-hero--quiet` + `.k-hero__title` |
| `.m3-mapa-frase` (mobile3.css:68) | `.k-hero__dek` |
| `.fin-hero` (finish.css:102) | `.k-hero k-hero--quiet` |
| `.fin-hero__cap` / `__cap-text` (:108, :119) | `.k-cap` con `.klara-mark` delante (átomo 6 + 16) |
| `.fin-hero__title` (:126) | `.k-hero__title`; los 80px bajan al techo de 40px del `clamp` |
| `.fin-hero__meta` + `strong` + `__sep` (:136-153) | `.k-hero__meta` |
| `.quiz-hero` + `__title` + `__sub` (finish.css:202-217) | `.k-hero k-hero--quiet` + `__title` + `__dek` |
| `.ob-welcome` / `.ob-done` (onboarding.css:257, :626) | `.k-hero k-hero--quiet` |
| `.ob-welcome__hello` (112px) / `.ob-done__title` (64px) | `.k-hero__title` con el `clamp`; los dos tamaños fuera de escala mueren |
| `.ob-welcome__lede` / `__sub` / `.ob-done__sub` | `.k-hero__dek` |
| `.ob-done__name` (:649) | `<em>` dentro de `.k-hero__title` |
| `.ob-welcome__cta` (:331) | contenedor de pantalla con `.k-btn--lg` dentro |
| `.ob-welcome__tip` (:339) | `.k-cap` |
| `.ob-prompt` (onboarding.css:153) | `.k-hero k-hero--quiet` mientras no exista el candidato 21 |
| `.ob-prompt__title` (:158) y su `@media max-860` (:170) | `.k-hero__title`; el `clamp` sustituye a los dos tamaños y el bloque `@media` de la hoja desaparece |
| `.ob-prompt__sub` (:172) | `.k-hero__dek` |
| `.ob-prompt__rule` (:180) | `.k-hairline` (global.css) |
| `.landing__tagline` (landing.css:24) | `.k-hero--quiet` + `.k-hero__title`. ~~Conserva la itálica~~: **no la conserva**, y es la tercera enmienda de la serie. La itálica es la voz de Klara y el titular de la portada no es Klara hablando, es el cartel de la puerta; conservarla habría pedido una variante nueva del átomo para una frase en una pantalla. No desaparece de la portada: se muda del titular al cuerpo, que va entero en ella (`__dek` y las cuatro `.k-note`). El tamaño baja de `--t-h1` —56px, 40 en el teléfono por `pages.css:692`— al `clamp` del sistema |
| `.landing__support` (landing.css:34) | `.k-hero__dek` |
| `.home__feature` y familia (pages.css:36-92, muertas) | `.k-hero`; es la implementación de escritorio del mismo bloque, se lee y se borra |
| `.story-end*` (pages.css:310-386, muertas) | `.k-hero k-hero--quiet` + `.k-hero__meta`; se leen y se borran |

**Notas:** el héroe tocable es `<button>` y ocupa 44px de sobra; el `--quiet` es `<header>` con `<h1>` dentro y no es tocable. `--quiet` apaga la superficie explícitamente (`background: none; color: var(--ink)`), porque el bloque base es tinta sólida. Las coreografías de entrada escalonada de onboarding (200/400/500/600/800ms) no son del átomo: son de la pantalla, y hoy incumplen §7.6 porque van en ms literales. Con alemán largo el título parte palabra; la flecha no se encoge.

---

### 13. Nota al margen — `.k-note`

**Reemplaza:** mobile3.css:117 `.m3-gloss` · mobile3.css:131 `.m3-fb .nota` (la de `role="status"`) + `.nota em` (:132) · mobile3.css:169 `.m3-corr` + `.linea` (:170), `.mal` (:171), `.bien` (:172), `.nota` (:173) (muertas) · mobile3.css:168 `.m3-turno .es` (muerta) · finish.css:572 `.qcard__rule`, :563 `.qcard__after`, :397 `.qcard__klara-line`, :414 `.qcard__en`, :617 `.qcard__hint`, :191 `.fin-souvenir__en`, :914 `.fin-l1__hint`, :936 `.fin-l1__word` · onboarding.css:105 `.ob__whisper` + `__whisper-text` (:117) y `.ob__margin` (:100) · sentence-view.css:106 `.k-stage__es`, :300 `.k-hint`, :443 `.k-feedback__verdict` + `em` (:450), :451 `.k-diagnose-tip`, :462 `--loading` · speak.css:168 `.kc-note` + `__line` (:181) / `__cap` (:182) / `__lead` (:183) / `__actions` (:185) / `__tip` (:187) / `__tip-cap` (:188) / `__legend` (:189) · perfil-aprendizaje.css:33 `.ob5-whisper`, :81 `.ob5-dicho`, :82 `.ob5-leyenda`, :87 `.ob5-pie` · landing.css:107 `.landing__wl-note`, :80 `.landing__bloque p`, :99 `.landing__wl-body` · pages.css:559 `.wpop__example-es` (muerta).

**Elementos:** `.k-note__cap` — el rótulo mono de la nota. `.k-note__body` — el texto. `.k-note__wrong` — lo dicho mal (tachado). `.k-note__right` — el acierto. `.k-note__actions` — la fila de controles dentro de la nota.

**Variantes:** `.k-note--mono` — la misma nota en mono, para traducciones y metadatos (es el registro de `m3-gloss`). `.k-note--bare` — sin filete a la izquierda, para notas al pie de un formulario.

**Estados:**
- base (**glosa**): `border-left: 1px solid var(--rule)`, `padding-left: var(--space-3)`, serif itálica `--ink-3`.
- `data-state="fix"` (**corrección**): `border-left: 2px solid var(--accent)`, con `.k-note__wrong` tachado en `--ink-4` y `.k-note__right` en `--accent-ink` peso 500.

**Medidas:** `margin: 18px 0 0` (0 cuando sigue a una `.k-cap`, que es su rótulo — ver átomo 6; y `var(--space-4)` de junta hacia un `<form>` que la siga, `.k-note + form`, hermana de la que cierra el formulario en el átomo 17: ni el párrafo que lo presenta trae margen abajo ni `.k-field` lo trae arriba, y el rótulo del primer campo se pegaba al texto), `padding-left: var(--space-3)`, `border-left: 1px solid var(--rule)`, serif itálica 15px, `line-height: 1.45`, color `--ink-3`, `max-width: 64ch`, `text-wrap: pretty`. `--mono`: `var(--font-mono)` 11px, `line-height: 1.6`, `letter-spacing: var(--tracking-mark)`, **sin versalitas** (excepción declarada en la gramática 9), sin itálica. `__cap`: mono 11px versalitas, `--accent-ink` en la corrección y `--ink-3` en la glosa. `__wrong`: `text-decoration: line-through; text-decoration-thickness: 1px`. `__right`: `--accent-ink`, peso 500.
Literales justificados: **1px/2px** de filete son la firma en cinco hojas; **15px** de cuerpo está entre `--t-mark` 14 y `--t-body` 17 y es el valor de `qcard__rule`, `ob5-whisper` y `kc-note__lead`; **64ch** de medida es el tope que ya usa `finish.css:572`; **11px** de `--mono` y de `__cap` es el escalón mono único (sube desde los 12px de `mobile3.css:117` y los 10px de `speak.css:182`). El margen de 18px baja a 12px bajo viewport corto (gramática 13).

**Tokens:** `--rule`, `--accent`, `--accent-ink`, `--ink-3`, `--ink-4`, `--space-3`, `--font-serif`, `--font-mono`, `--tracking-mark`.

**Markup canónico:**
```html
<p class="k-note">La preposición pide dativo.</p>

<div class="k-note" data-state="fix">
  <span class="k-note__cap">Corrección</span>
  <p class="k-note__body"><span class="k-note__wrong" lang="de">Ich habe gegangen</span> <span class="k-note__right" lang="de">Ich bin gegangen</span></p>
</div>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-gloss` (mobile3.css:117) | `.k-note k-note--mono`; baja de 12 a 11px |
| `.m3-fb .nota[role="status"]` (mobile3.css:131, EstudiarView.tsx:335) | `.k-note` — es el veredicto de pronunciación, un aviso, no un error |
| `.m3-fb .nota em` (mobile3.css:132) | `.k-note__right` (ya está en `--accent-ink` y peso 600 → 500) |
| `.m3-fb .nota[role="alert"]` (mobile3.css:131, EstudiarView.tsx:323) | `.k-error` (átomo 15): es la distinción error/aviso que el sistema impone |
| `.m3-turno .es` (mobile3.css:168, muerta) | `.k-note k-note--mono` |
| `.m3-corr` (mobile3.css:169, muerta) | `.k-note[data-state="fix"]` |
| `.m3-corr .linea` (:170) | `.k-note__body` |
| `.m3-corr .mal` (:171) | `.k-note__wrong` |
| `.m3-corr .bien` (:172) | `.k-note__right` |
| `.m3-corr .nota` (:173) | `.k-note__body` (segundo párrafo) |
| `.qcard__rule` (finish.css:572) | `.k-note`; el filete baja de 2px a 1px (los 2px quedan para la corrección) |
| `.qcard__after` (finish.css:563) | `.k-note k-note--bare` |
| `.qcard__klara-line` (finish.css:397) | `.k-note__cap` |
| `.qcard__en` (finish.css:414) | `.k-note` |
| `.fin-souvenir__en` (finish.css:191) | `.k-note k-note--mono` |
| `.qcard__hint` (finish.css:617) | `.k-note k-note--bare` |
| `.fin-l1__hint` / `__word` (finish.css:914, :936) | `.k-note` / `.k-note__right` |
| `.ob__whisper` + `__whisper-text` (onboarding.css:105, :117) | `.k-note` con `.klara-mark` dentro |
| `.ob__margin` (onboarding.css:100) | columna de la pantalla, no del átomo; y deja de desaparecer bajo 860px |
| `.k-stage__es` (sentence-view.css:106) | `.k-note` |
| `.k-hint` (sentence-view.css:300) | `.k-note k-note--bare`; deja de ocultarse por `pointer: coarse` |
| `.k-feedback__verdict` + `em` (:443, :450) | `.k-note` + `.k-note__right` |
| `.k-diagnose-tip` (:451) | `.k-note__body`; la `opacity: .72` se sustituye por `--ink-3` |
| `.k-diagnose-tip--loading` (:462) | no entra el estado cargando de la nota. Ver «Pendientes» |
| `.kc-note` (speak.css:168) | `.k-note[data-state="fix"]`; pierde la caja (`--paper-2`, borde, radio) y se queda con el filete de acento |
| `.kc-note__line` (speak.css:181) | `.k-note__body` (es el renglón flex que agrupa lo dicho y lo correcto; la nota ya reparte con `gap`) |
| `.kc-note__cap` / `__lead` / `__tip` (:182, :183, :187) | `.k-note__cap` / `.k-note__body` / `.k-note__body` |
| `.kc-note__actions` (:185) | `.k-note__actions` |
| `.kc-note__tip-cap` / `__legend` (:188, :189) | `.k-note__cap` / `.k-note__body` |
| `.taller .kbd` (taller.css:288) | `.k-chip k-chip--static` sobre `<kbd>` (átomo 8) |
| `.ob5-whisper` (perfil:33) | `.k-note` |
| `.ob5-dicho` (perfil:81) | no entra el filete punteado de procedencia. Ver «Pendientes» |
| `.ob5-leyenda` (perfil:82) | `.k-note k-note--mono` |
| `.ob5-pie` (perfil:87) | `.k-note k-note--bare` |
| `.landing__wl-note` (landing.css:107) | `.k-note k-note--mono k-note--bare` |
| `.landing__bloque p` (landing.css:80) y `.landing__wl-body` (:99) | `.k-note k-note--bare`. Son el hallazgo de la migración 10: **la portada es la única pantalla de Klara con prosa de interfaz**, o sea texto que no es contenido alemán (`.k-stage`, serif recto a `--t-read`) ni marginalia (mono) ni la voz de Klara al margen. El sistema, derivado de las pantallas de dentro, no tiene registro para ella, así que la prosa de la puerta entra en el que más se le parece — y de paso la portada queda entera en la voz de Klara, que es quien está hablando ahí |
| `.wpop__example-es` (pages.css:559, muerta) | `.k-note k-note--mono` |

**Notas:** la corrección no depende del color: lo dicho mal va tachado y lo correcto va con su rótulo, así que un daltónico y un lector de pantalla leen lo mismo. Cuando la nota lleva controles (`__actions`), esos controles son `.k-btn`/`.k-rbtn` y cumplen sus 44px. La nota nunca se oculta por capacidad de puntero: hoy `k-hint` desaparece en táctil y `ob__margin` bajo 860px, y las dos cosas son pérdida de información en el caso principal, que es el teléfono. `role="status"` sí, `role="alert"` no: lo que alerta es `.k-error`.

---

### 14. Palabra puntuada — `.k-word`

**Reemplaza:** mobile3.css:115 `.m3-w`, `:active` (:116), `[data-active="true"]` (:144) · mobile3.css:146-148 `.m3-oracion [data-score="good"|"ok"|"bad"]` · sentence-view.css:115 `.k-tok`, `:disabled` (:128), `[data-matched="true"]:hover` (:129), `[data-breakdown="true"]:hover` (:130), `[data-active="true"]` (:131), `[data-score]` (:132-134), `.k-tok-space`/`.k-tok-punct` (:138) · finish.css:476 `.qcard__shadow-tok` + `[data-score]` (:480-482), `.qcard__shadow-sentence` + `[data-played="true"]` (:465, :475), `.qcard__blank` + `[data-state="correct"|"revealed"]` (:421, :441, :446), `.qcard__blank-rule` (:432) · speak.css:161 `.kc-live-focus`.

**Elementos:** ninguno. Los espacios y la puntuación son `<span>` sin clase, para que el subrayado no cruce los blancos.

**Variantes:** ninguna.

**Estados:** El puntaje **se ancla al contenedor `.k-stage`** (gramática 12), no a `.k-word`: `EstudiarView.tsx:295` emite `<span data-score={band}>` sin clase cuando la palabra no es clicable, y por eso el selector vivo de `mobile3.css:145-148` ya es `.m3-oracion [data-score]`. El sistema conserva esa decisión textual: `.k-stage [data-score="…"]`. Todo lo demás cuelga de `.k-word`.
- `.k-stage [data-score="good"]` (**bien**): `box-shadow: inset 0 -3px 0 var(--score-good)`.
- `.k-stage [data-score="ok"]` (**regular**): `inset 0 -3px 0 var(--score-ok)`.
- `.k-stage [data-score="bad"]` (**mal**): `inset 0 -3px 0 var(--score-bad)` **más** fondo `var(--accent-wash)`; es el único de los tres que se rellena, y por eso «mal» se distingue sin depender del matiz.
- `.k-word[data-active="true"]` (**activa**): fondo `--paper-3`. Cubre las dos semánticas vivas —la palabra que suena y la palabra con el diccionario abierto— porque son la misma cosa para el ojo: «de esta estamos hablando».
- `.k-word[data-matched="true"]`, `[data-breakdown="true"]`: en `:hover`, color `--accent-ink` (afordancia de que se puede tocar).
- `.k-word:disabled`: `cursor: default`, sin señal visual, igual que hoy.

**Medidas:** `display: inline`, botón reseteado (`background: none; border: 0; font: inherit; color: inherit`), `padding: 11px 2px; margin: -11px -2px` (el patrón de la gramática 6: el área táctil llega a 44px de alto sin mover la línea base), `border-radius: var(--r-xs)`, `transition: box-shadow var(--dur-med), background var(--dur-med)`. El subrayado es siempre `box-shadow` interior de 3px, nunca `border-bottom`, para no desplazar la línea. El contenedor `.k-stage` aporta el serif de 25-30px, el `line-height: 1.5` y el recorte a siete líneas.
Literales justificados: **3px** del subrayado es la firma en las tres hojas que lo implementan; **11px/2px** de padding es lo que hace falta sobre el serif de 22-30px de `.k-stage` para llegar a 44 de alto —la cuenta se rehace aquí, no se hereda de `mobile3.css:143` (gramática 6).

**Tokens:** `--score-good`, `--score-ok`, `--score-bad`, `--accent-wash`, `--accent-ink`, `--paper-3`, `--r-xs`, `--dur-med`.

**Markup canónico:**
```html
<p class="k-stage" lang="de">
  <button type="button" class="k-word" data-score="good">Guten</button><span> </span><button type="button" class="k-word" data-score="bad" data-matched="true">Morgen</button><span>.</span>
</p>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.m3-oracion` (mobile3.css:114) | `.k-stage` (gramática 12), con su `--fscale` en línea |
| `.m3-w` (mobile3.css:115) | `.k-word` |
| `.m3-w:active` (:116) | se pierde el `--accent-wash` de pulsación: lo cubre `data-active` |
| `.m3-w[data-active="true"]` (:144) | `.k-word[data-active="true"]` (atributo conservado textual) |
| `.m3-oracion [data-score="good"\|"ok"\|"bad"]` (:146-148) | `.k-stage [data-score]`; los tres literales pasan a `--score-*` y el ancla al contenedor se conserva |
| `.k-stage` / `.k-stage__de` (sentence-view.css:81, :96) | `.k-stage` (el nombre se conserva; la definición se muda a `sistema.css`) |
| `.k-tok` (sentence-view.css:115) | `.k-word` |
| `.k-tok[data-score]` (:132-134) | `.k-stage [data-score]` |
| `.k-tok[data-active="true"]` (:131) | idéntico sobre `.k-word` |
| `.k-tok[data-matched]:hover` / `[data-breakdown]:hover` (:129, :130) | idénticos |
| `.k-tok:disabled` (:128) | idéntico |
| `.k-tok-space` / `.k-tok-punct` (:138) | `<span>` sin clase: `.k-stage` no fija `white-space`, y un espacio que es el único contenido de su nodo no se colapsa |
| `.qcard__cloze` (finish.css:404) | `.k-stage` (átomo 3, mismo destino) |
| `.qcard__shadow-tok` + `[data-score]` (finish.css:476-482) | `.k-stage [data-score]` |
| `.qcard__shadow-sentence[data-played="true"]` (finish.css:475) | estado del contenedor, no de la palabra. Ver «Pendientes» |
| `.qcard__blank` + `[data-state]` + `.qcard__blank-rule` (finish.css:421-446) | el hueco rellenable es la misma gramática visual en otro momento; migra con StoryFinish. Ver «Pendientes» |
| `.kc-live-focus` (speak.css:161) | `.k-word[data-active="true"]`; la pantalla de Hablar renuncia hoy a la rúbrica de tres colores (comentario de speak.css:159) y con el átomo unificado esa decisión pasa a ser del `.tsx`, que simplemente no emite `data-score` |

**Notas:** el «activa (sonando)» que pide §5 **no existe hoy en ninguna hoja** —lo más parecido es el popover abierto de `k-tok[data-active]`—, así que este átomo lo estrena. La única excepción del sistema a §7.2 vive aquí: el **alto** táctil llega a 44px con padding y margen negativo, pero el **ancho** es el de la palabra, y una palabra corta («es», ≈20px) no puede llegar a 44 sin romper la línea que §6.2 declara «la pantalla». `hoja.check.mjs:96-101` mide ancho y alto, así que hay que exceptuar `.k-word` en el chequeo o medir solo el alto en elementos `display: inline` (ver «Trampas conocidas»). Cada palabra es `<button>` con el texto como nombre accesible; el veredicto se dice además en `.k-note`, nunca solo con el subrayado.

---

### 15. Error — `.k-error`

**Reemplaza:** global.css:402 `.k-error` · onboarding.css:710 `.ob-error` · onboarding.css:605 `.ob-field__hint` (ver átomo 17) · taller.css:299 `.taller .rejected` + `li` (:307) · recall-review.css:37 `.rr__empty`, :298 `.rr-done__note` · speak.css:258 `.kc-hint` cuando lleva `role="alert"` · mobile3.css:131 `.m3-fb .nota` cuando lleva `role="alert"` (EstudiarView.tsx:323) · gender-review.css `.gr__empty`.

**Elementos:** ninguno.

**Variantes:** ninguna.

**Estados:** **en línea** — bloque con filete de acento a la izquierda y lavado de fondo. Es el único estado, y es el único registro: un error se ve distinto de un estado vacío, siempre.

**Medidas:** `var(--font-mono)` `var(--t-mono)`, `letter-spacing: 0.02em`, color `--accent-ink`, `padding: 10px var(--space-3)`, `border-left: 2px solid var(--accent)`, fondo `var(--accent-wash)`, `line-height: var(--lh-read)`.
Literales justificados: son los valores textuales de `global.css:402-410` salvo el cuerpo, que baja de 12px a `var(--t-mono)` por la gramática 10 (regla 7d). El `0.02em` es menor que `--tracking-mark` a propósito, porque el texto no va en versalitas (gramática 9b).

**Tokens:** `--font-mono`, `--space-3`, `--accent`, `--accent-ink`, `--accent-wash`.

**Markup canónico:**
```html
<p class="k-error" role="alert">No se pudo guardar. Vuelve a intentarlo.</p>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.k-error` (global.css:402) | `.k-error` (idéntico) |
| `.ob-error` (onboarding.css:710) | `.k-error` — es un clon exacto salvo el `var(--space-3)` horizontal |
| `.ob-field__hint` (onboarding.css:605) | `.k-field__hint` (átomo 17): es la pista del campo, no el mensaje de error de la pantalla |
| `.ob-input[data-error="true"]` (onboarding.css:623) | `.k-field[data-error="true"]` (átomo 17) |
| `.taller .rejected` (taller.css:299) | `.k-error` |
| `.taller .rejected li` (taller.css:307) | `<li>` dentro de `.k-error`; la variante lista no entra. Ver «Pendientes» |
| el aviso de pegado truncado (Taller.tsx:248) | **no** es error: pasa a `.k-note k-note--mono`, sin acento y sin `role` |
| `.m3-fb .nota[role="alert"]` (mobile3.css:131, EstudiarView.tsx:323) | `.k-error`; hoy comparte pintura exacta con el aviso de `role="status"`, que es justo el hueco que este átomo cierra |
| `.rr__empty` (recall-review.css:37) | dos destinos distintos: el fallo de carga pasa a `.k-error` con `role="alert"`; el vacío pasa a `.k-note k-note--mono` — hoy son indistinguibles y ese es el hueco real del átomo |
| `.rr-done__note` (recall-review.css:298) | `.k-error` cuando cuenta repasos sin guardar; `.k-note` cuando es la nota de cierre |
| `.kc-hint` con `role="alert"` (Speak.tsx:643) | `.k-error` |
| `.kc-hint` sin rol (Speak.tsx:842) | `.k-note` |
| `.gr__empty` (gender-review.css) | `.k-error` para el fallo de red; ~~`.k-note k-note--mono`~~ **`.k-note` a secas** para el vacío (migración 12): la doctrina que fijó Repaso —«el vacío es `.k-note`, el fallo de carga es `.k-error`»— no le pone mono, y el vacío de género es una frase de Klara, no un metadato |

**Notas:** siempre `role="alert"` cuando el mensaje aparece como consecuencia de una acción del usuario, y nunca `role="alert"` en un estado vacío. La regla que este átomo impone y que hoy se rompe en cuatro hojas: **un error se distingue de un vacío y de un aviso**. El error no lleva icono; el acento y el filete bastan, y el texto dice qué pasó y qué hacer.

---


### 16. La marca — `.klara-mark`

**Reemplaza:** global.css:263 `.klara-mark`, `[data-speaking="true"]::after` (:275), `@keyframes klara-breath` (:284), `.glyph` (:288) · onboarding.css:32 `.ob__chrome-mark`, :264 `.ob-welcome__mark`, :633 `.ob-done__mark`, `@keyframes welcome-mark-in` (:268) · finish.css:113 `.fin-hero__k`, :965 `.fin-note__sign` · sentence-view.css:39 `.k-chapter__k` · recall-review.css:63 `.rr-head__k` · pages.css:284 `.snew__klara`, :682 `.kp-sign`, :688 `.kp-sum__sig`, :689 `.kp-sum__k` · perfil-aprendizaje.css:78 `.ob5-esperando` · speak.css:83 `.kc-presence` y su escenario (ver «Pendientes»).

**Elementos:** `.klara-mark .glyph` — la K, por encima del halo (nombre conservado de global.css:288).

**Variantes:** ninguna. El tamaño lo pasa el componente `KlaraMark` por prop, no una clase.

**Estados:**
- reposo (**quieta**): serif itálica en `--ink`, sin halo.
- `data-speaking="true"` (**hablando**): halo circular de `--accent` a `opacity: 0.18` en `::after`, latiendo con `klara-breath` a `--dur-breath`.
- Bajo `prefers-reduced-motion`: el halo **se queda visible y quieto** a `opacity: 0.18`. Es el punto más delicado de la regla 4 de la gramática: hoy la regla global de `recall-review.css:333-337` mata el latido que §3.4 declara intocable, y además lo deja invisible en el 0 % del keyframe.

**Medidas:** `display: inline-flex` centrado, `var(--font-serif)` itálica 400, color `--ink`, `position: relative`, `user-select: none`, `line-height: 1`. `::after`: `inset: -10%`, `border-radius: 50%`, fondo `--accent`, `opacity: 0.18`.
Literales justificados: **-10%** y **0.18** son los valores de `global.css:275-283`, intocables por §3.4.

**Tokens:** `--font-serif`, `--ink`, `--accent`, `--dur-breath`, `--ease-out`.

**Markup canónico:**
```html
<span class="klara-mark" style="font-size:18px"><span class="glyph">K</span></span>

<span class="klara-mark" data-speaking="true" style="font-size:64px"><span class="glyph">K</span></span>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.klara-mark` + `::after` + `.glyph` (global.css:263-295) | idénticos, mudados a `sistema.css` |
| `.ob__chrome-mark` (onboarding.css:32) | `.k-topline__mark` (átomo 11) con la marca dentro |
| `.ob-welcome__mark` / `.ob-done__mark` (:264, :633) | envoltorios de pantalla; la animación de entrada no es del átomo. Ver «Pendientes» |
| `.fin-hero__k` (finish.css:113) | `.klara-mark` (hoy es una «K» de texto que no puede respirar) |
| `.fin-note__sign` (finish.css:965) | firma «— K»: no entra. Ver «Pendientes» |
| `.k-chapter__k` (sentence-view.css:39) | `.klara-mark` |
| `.rr-head__k` (recall-review.css:63) | `.klara-mark` |
| `.kp-sum__k` (pages.css:689) | `.klara-mark` |
| `.snew__klara` / `.kp-sign` / `.kp-sum__sig` (pages.css:284, :682, :688) | tres envoltorios distintos de la misma firma: pasan a `.k-topline--foot` con la marca dentro. **La migración 15 gastó el último (`snew__klara`) y no con la tira sino con `.k-note k-note--bare`**, que es el pie que la 7 y la 3 ya usaban para una frase firmada por Klara: no es una tira de navegación, es una nota al margen con una K delante |
| `.ob5-esperando` (perfil-aprendizaje.css:78, perfil/views.tsx:367) | la marca usada como **spinner de espera**: no entra. Va al candidato 19/22 (píldora de proceso / carga de pantalla), porque `data-speaking` decorativo está prohibido por las Notas de este átomo |
| `.kc-presence` y su escenario (speak.css:83-134) | no entra: es el escenario de la pantalla de Hablar, con cuatro estados que la marca no tiene. Ver «Pendientes» |

**Notas:** la marca es decorativa (`aria-hidden="true"`) salvo cuando es el enlace al inicio, y entonces el nombre accesible lo pone el enlace, no el glifo. `data-speaking` se usa **solo** cuando Klara está sonando de verdad; hoy StepWelcome y StepDone lo dejan encendido de adorno y `perfil/views.tsx:367` lo usa de spinner, y eso convierte la única señal viva de la interfaz en decoración. Cinco hojas reimplementan la K como texto suelto: todas pasan por aquí.

---

### 17. Campo de texto — `.k-field`

**Reemplaza:** auth.css:42 `.auth-input` + `:focus-visible` (:55), `.auth-label` (:33), `.auth-form` (:27) · onboarding.css:611 `.ob-input`, `:focus` (:621), `[data-error="true"]` (:623) · onboarding.css:600 `.ob-field` + `__label` (:604) + `__hint` (:605) · onboarding.css:565 `.ob-context__textarea` + `:focus` + `::placeholder` · onboarding.css:351 `.ob-name__input` · pages.css:190 `.snew__input` + `::placeholder` + `:focus` + `.snew__input-rule` (:205) · taller.css:145 `.taller textarea` + `::placeholder` (:164) · mobile4.css:36 `.m4-input` + `::placeholder` (:37) (muerta) · perfil-aprendizaje.css:47 `.ob5-otra` + `:focus` + `::placeholder`, :66 `.ob5-area` + `::placeholder`.

**Elementos:** `.k-field__label` — el rótulo en mono. `.k-field__input` — el control (`<input>`, `<textarea>` o `<select>`). `.k-field__rule` — el filete inferior de la variante manuscrita. `.k-field__hint` — la pista o el motivo del error.

**Variantes:** `.k-field--area` — el control es un `<textarea>`. `.k-field--rule` — manuscrito: sin caja, con filete inferior que pasa de `--rule` a `--ink` al enfocar.

**Estados:**
- **reposo**: fondo `--paper`, borde 1px `--rule`, radio `var(--r-sm)`. En `--rule`: fondo transparente, sin borde salvo el inferior.
- `:focus` / `:focus-within` (**foco**): `border-color: var(--ink)` (o el filete a `--ink` en `--rule`). El anillo global de `:focus-visible` **no se anula**.
- `data-error="true"` en el bloque (**error**): borde (o filete) en `--accent`, `.k-field__hint` en `--accent`, y el `.tsx` pone `aria-invalid="true"` y `aria-describedby` apuntando a la pista.
- `:disabled` en el control (**deshabilitado**): `opacity: 0.45`, `cursor: not-allowed`, fondo `--paper-3`. Es nuevo: hoy hay 13 inputs con `disabled={submitting}` y ninguna hoja los pinta.

**Medidas:** `.k-field`: columna flex, `gap: 6px`. `.k-field__label`: mono 11px versalitas `--ink-3`, `letter-spacing: var(--tracking-mark)`. `.k-field__input`: `width: 100%`, `min-height: 44px`, `padding: var(--space-3) 14px`, **`var(--font-sans)`**, **16px**, `line-height: 1.4`, color `--ink`, `transition: border-color var(--dur-fast)`, `hyphens: auto` (con `-webkit-hyphens` para Safari): con el `lang="de"` del control, el compuesto alemán parte con guion y no deja un jirón suelto en la última línea. `--area`: `min-height: 140px`, `resize: vertical`, `field-sizing: content`, y **serif** —excepción declarada en la gramática 9c: lo que se teclea en un área es el pasaje alemán, o sea contenido, y es el valor vivo en `taller.css:145` y `onboarding.css:565`. `--rule`: `padding: 10px 0`, `border: 0`, `border-bottom: 1px solid var(--rule)`, `border-radius: 0`, cuerpo `var(--t-read)`. `::placeholder`: `--ink-4`, itálica. `.k-field__hint`: serif itálica `var(--t-meta)`.
Literales justificados: **16px** de cuerpo es deliberado y viene con su comentario en `onboarding.css:612` — por debajo de 16px, iOS hace auto-zoom al enfocar un campo, lo que rompe el ancho de 430px de la sesión. **11px** del rótulo es el escalón mono único; **140px** del área es el mínimo de `ob-context__textarea` (96px bajo viewport corto, gramática 13); **44px** el mínimo táctil; **6px** de gap y **14px** del padding horizontal son los valores vivos de `onboarding.css:600` y `:611`.

**Tokens:** `--paper`, `--paper-3`, `--rule`, `--ink`, `--ink-3`, `--ink-4`, `--accent`, `--r-sm`, `--space-3`, `--t-read`, `--t-meta`, `--font-sans`, `--font-serif` (`--area`), `--font-mono`, `--tracking-mark`, `--dur-fast`.

**Markup canónico:**
```html
<label class="k-field">
  <span class="k-field__label">Correo</span>
  <input class="k-field__input" type="email" autocomplete="email">
</label>

<label class="k-field k-field--rule" data-error="true">
  <span class="k-field__label">Contraseña</span>
  <input class="k-field__input" type="password" aria-invalid="true" aria-describedby="pw-hint">
  <span class="k-field__rule" aria-hidden="true"></span>
  <span class="k-field__hint" id="pw-hint">No coinciden.</span>
</label>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo (hoja) | nuevo |
|---|---|
| `.auth-form` (auth.css:27) | `<form>` con `.k-field` dentro; el contenedor no es átomo |
| `.auth-label` (auth.css:33) | `.k-field__label` |
| `.auth-input` (auth.css:42) | ~~`.k-field k-field--rule`~~ → **`.k-field` a secas** + `.k-field__input`. **Enmienda de la migración 9**, contra este mismo mapa: el comentario que justifica `--rule` dice «cuerpo grande porque lo que se escribe ahí es la respuesta, **no un dato de formulario**», y un correo y una contraseña son exactamente un dato de formulario. La contradicción estaba dentro del propio átomo. Con la caja, la contraseña de `/signup` y la del capítulo V del onboarding —el mismo acto— se ven por fin igual. A `--rule` le queda un consumidor vivo, y es el que la doctrina describe: el nombre propio de `StepName` |
| `.auth-input:focus-visible` (auth.css:55) | `:focus` del átomo; **deja de anular el anillo global** (hoy es una degradación de accesibilidad heredada por copia) |
| `.ob-field` / `__label` / `__hint` (onboarding.css:600, :604, :605) | `.k-field` / `__label` / `__hint` |
| `.ob-input` + `:focus` (onboarding.css:611, :621) | `.k-field__input` (caja); el serif pasa a sans por la gramática 9 |
| `.ob-input[data-error="true"]` (:623) | `.k-field[data-error="true"]` (el atributo sube al bloque para poder teñir también la pista) |
| `.ob-name__input` (onboarding.css:351) | `.k-field k-field--rule` con el cuerpo grande que pida la pantalla |
| `.ob-context__textarea` (onboarding.css:565) | `.k-field k-field--area`; conserva el serif |
| `.ob-context__count` | `.k-cap__count` |
| `.snew__input` (pages.css:190) | `.k-field k-field--rule`. **La migración 15 lo partió, y por la misma doctrina que la 9 usó en auth**: en Nuevo relato es `--rule` (lo que se teclea es la respuesta a «¿de qué quieres que vaya?»), y en Ajustes y en el panel de invitaciones es la caja (nombre, correo, nota, idiomas, contexto: datos de formulario). La misma clase pintaba las dos cosas |
| `.snew__input-rule` + `:focus +` (pages.css:205) | `.k-field__rule` + `:focus-within` |
| `select.snew__input option` (pages.css:~221) | se conserva: los colores explícitos del popup nativo siguen haciendo falta en oscuro |
| `.taller textarea` (taller.css:145) | `.k-field k-field--area`; conserva el serif y se pierde el cuelgue óptico de -17px, que era layout de esa pantalla |
| `.m4-input` (mobile4.css:36, muerta) | `.k-field k-field--area` |
| `.ob5-otra` (perfil:47) | `.k-field k-field--rule` |
| `.ob5-area` (perfil:66) | `.k-field k-field--area k-field--rule` |
| `.taller .chip-input` (taller.css:197) | `.k-field--chip`: no entra. Ver «Pendientes» |
| `.snew__range` (pages.css:229) | deslizador CEFR: no es campo de texto. Ver «Pendientes» |

**Notas:** el campo es `<label>` envolviendo al control, así que el rótulo siempre está asociado sin `for`. El error se anuncia con `aria-invalid` + `aria-describedby`, no solo con el borde en acento. Todo control llega a 44px de alto. El cuerpo es sans porque §4 del brief lo dice («Sans = los controles. Botones, campos») y la gramática 9 lo repite; el área es la excepción escrita. El estado `:disabled` es la pieza que cierra el hueco más viejo de la app: 13 campos se deshabilitan durante el envío y hoy el usuario no ve que la app está esperando la red.

---

## Orden de borrado seguro

### Se puede borrar ya, sin migrar nada

Bloques 100 % muertos según `auditoria-css.md` y verificados con `grep` sobre `frontend/src/**/*.tsx`. Las filas de `mobile3.css`, `mobile4.css`, `recall-review.css`, `taller.css` y `speak.css` ya son historia: esas cinco hojas están borradas enteras (migraciones 1 a 5):

| hoja:líneas | qué es | comprobación |
|---|---|---|
| `pages.css:5-156` | el bloque `home*` entero (23 clases) | la home real es `m4-*`; 0 usos |
| `pages.css:310-386` | `story-end*` (10 clases) + `@keyframes step-in-fwd` | sustituido por `fin-*`/`qcard*`; 0 usos |
| `pages.css:388-472` | `story__new*` (11 clases) + `.story__foot` | 0 usos |
| `pages.css:559-563` | `.wpop__example-es` | 0 usos |
| `mobile3.css:40-42` | `.m3-saludo`, `em`, `.m3-linea` | 0 usos (la vive `m4-saludo`) |
| `mobile3.css:66-67` | `.m3-mapa-h1` | 0 usos (la vive `m4-h1`) |
| `mobile3.css:154-162` | `.m3-sheet` + `@keyframes m3-up` + `.grab`/`.fila1`/`.lemma`/`.art`/`.trad` + `.m3-art-*` | 0 usos. **Ojo: `mobile3.css:151-153` (`.m3-scrim` + `m3-fade`) está VIVO** — TabBar.tsx:39 lo usa para el menú |
| `mobile3.css:164-180` | bloque «Hablar»: `.m3-carta`, `.m3-turno`, `.m3-corr`, `.m3-dock.hablar`, `.miclbl`, `.micgrande`, `.m3-lado` | 0 usos (`.m3-dock` a secas, línea 118, sigue vivo en EstudiarView.tsx:361) |
| `mobile3.css:182-201` | bloque «Repaso»: `.m3-rep`, `.m3-repbar`, `.m3-ficha` y sus siete hijos, `.m3-srs` | 0 usos |
| `mobile4.css:36-49` | `.m4-input`, `.m4-chips`, `.m4-o`, `.m4-upload`, `.m4-pensando`, `.m4-modo` | 0 usos |
| `mobile4.css:57` | `.m4-input{min-height:76px}` del bloque `@media` | huérfana de la anterior |
| `recall-review.css:89-94` | `.rr-prog__slash`, `__track`, `__pip` (con su `data-state="again"`) | 0 usos |
| `recall-review.css:138,148,152,186,197,198,240,270` | `__folio`, `__front-folio`, `__pos`, `__back-folio`, `__eg-tx`, `__src`, `.rr-flip__hint`, `.rr-rate__key` | 0 usos |
| `recall-review.css:327-328` | reglas de la fase `done` que nunca disparan (esa rama devuelve otro árbol) | inertes |
| ~~`speak.css:36`~~ | ~~`.kac-tri--lg`~~ | 0 usos; se fue con la hoja (migración 5) |
| `perfil-aprendizaje.css:92-97` | `.ob5-fila` + `.tit`/`.est`/`.ch`/`[data-hot]` | 0 usos. **El brief §5 fila 4 se equivoca al nombrarla**: Perfil pinta con `m3-rowbtn` |
| `global.css:81` | `.k-rule` | 0 usos |
| `taller.css:55` | `.taller .tally a` | selector inerte: el `.tsx` renderiza un `<button>` |
| `taller.css:141` | `.taller .col {}` | regla vacía |

Dos cosas que **no** se borran aunque la auditoría las marque muertas:

- **~~`speak.css:67-70` `.kac-feedback__btn--strong`~~ y `global.css:327-330` `.k-btn--accent`.** Eran variantes diseñadas y nunca montadas: la primera se traducía a `.k-btn` sólido y murió sin estrenarse —la migración 5 montó su hermana normal, `.k-btn k-btn--ghost`, en el «Dilo otra vez» del apunte— y la segunda es el acento del sistema, que sí se estrenó, en `.rr-rate__btn--again`.
- **`path.css:16-65`.** Está muerto, sí, pero es la implementación **más completa** de dos átomos: la fila con sus cinco estados (`--locked` opacity .55, `--current` título en itálica, `--completed` meta en acento, `.path__num`, `.path__check`, `.path__cta`) y la barra **dual** (`--fast` = visto, `--slow` = dominado, superpuestas). Se lee antes de escribir los átomos 4 y 5, y solo entonces se borra.

### Se borra al migrar cada pantalla

**Ya cumplido:** `mobile4.css` (migración 1), `mobile3.css` (migración 2), `recall-review.css` (migración 3), `taller.css` (migración 4), `speak.css` (migración 5), `sentence-view.css` (migración 6), `finish.css` (migración 7), `onboarding.css` (migración 8), `auth.css` (migración 9), `landing.css` (migración 10), `perfil-aprendizaje.css` (migración 11), `gender-review.css` (migración 12), `path.css` (migración 13) y `pages.css` (migración 15, después de que la 14 se llevara su bloque `wpop*`) están borradas, con sus `import`. **CATORCE MUERTAS; NO QUEDA NINGÚN DIALECTO DE PANTALLA VIVO.** Lo único que queda del CSS viejo es el cascarón de escritorio de `global.css:87-254`, que no es un dialecto de pantalla sino el armazón que las sostenía. Las filas siguen aquí como referencia de qué se llevó cada una.

| pantalla que se migra | qué muere con ella |
|---|---|
| Biblioteca (`routes/Inicio.tsx`, `routes/Portada.tsx`) | `mobile4.css` entero salvo lo ya muerto: `.m4-saludo`, `.m4-sec`, `.m4-lib`, `.m4-tema` y sus hijos, `.m4-bar`, `.m4-add`, `.m4-backrow`, `.m4-h1`, `.m3-tabbar.m4` (mobile4.css:6-34) y su `@media` de las líneas 51-58 |
| Lectura (`routes/Story.tsx`, `components/EstudiarView.tsx`) | `mobile3.css:112-148` (lectura, dock, `m3-rbtn`, `m3-gloss`, `m3-fb` con sus dos `nota`, `data-score`) y `mobile3.css:101-110` (chrome de sesión + `m3-prog`); con ella muere el alias `data-done` del segmento de barra |
| Hablar (`routes/Speak.tsx`) | `speak.css` entera (277 líneas, consumidor único), **escenario incluido**: `kc-presence` acabó siendo armazón (`.k-presence`), no átomo |
| Repaso (`components/RecallReviewSession.tsx`) | `recall-review.css` entera (351 líneas, consumidor único), incluida su regla global de reduced-motion de las líneas 333-337 |
| Taller (`routes/Taller.tsx`) | `taller.css` entera (309 líneas, consumidor único) |
| ~~Lectura de escritorio~~ **Pronunciar** (`components/SentenceView.tsx`) | `sentence-view.css` entera (577 líneas, consumidor único) **y el componente**: no era una pantalla de escritorio sino la sesión de Práctica, y desde la migración 2 su gemelo migrado (`EstudiarView`) ya hacía el mismo trabajo con el mismo hook. La migración 6 no la re-vistió: la borró y conectó Práctica al gemelo. Se lleva además `lib/waveform.ts`, que se quedó sin consumidor |
| ~~Fin de historia~~ **Cierre** (`components/StoryFinish.tsx`, `GenderPicker.tsx`) | `finish.css` entera (1.021 líneas) **y** `lib/audioBars.ts`, que se quedó sin consumidor al morir el VU de las tres fichas. La migración 7 la mató entera y de paso sacó el cierre del cascarón viejo: `StoryFinish` pinta su propio `.k-app`, así que `Story.tsx` deja de escribir `kapp`/`kframe` |
| Onboarding (`onboarding/**`) | `onboarding.css` entera (718 líneas). La migración 8 se llevó además la rejilla de tres columnas —el numeral romano de la izquierda y la marginalia de Klara de la derecha, que `@media (max-width: 860px)` escondía, o sea que ningún teléfono las vio nunca— y sacó la ruta de `LegacyShell`: `/onboarding` pinta su propio `.k-app` |
| Auth (`Login`, `Signup`, `Forgot`, `Reset`, `VerifyEmail`) | `auth.css` entera (76 líneas). La migración 9 se llevó además el trozo de la portada que se colgaba de ella: el formulario de la lista de espera de `Landing.tsx` era el único consumidor de `.auth-form`/`.auth-label`/`.auth-input`/`.auth-actions` fuera de `/login`, y por eso `auth.css` no podía morir sin tocar `landing.css`… salvo que ese formulario pasara al vocabulario, que es lo que hizo |
| Landing (`routes/Landing.tsx`) | `landing.css` entera (128 líneas). Los dos `padding` con `env(safe-area-inset-*)` de las líneas 13 y 17 —el arreglo del pie bajo la barra de gestos, commit 18cc68e— reaparecen en el contenedor nuevo, que es el del cascarón: el de arriba ya lo traía `.k-app > .k-page` y el de abajo entra como regla nueva con `:last-child` (gramática 12). Se lleva además el `<div className="landing" />` con que `RootGate` (App.tsx:74) pintaba la espera de la sesión, hoy un `.k-app` vacío |
| Perfil de aprendizaje (`perfil/views.tsx`) | `perfil-aprendizaje.css` entera (110 líneas), incluido su `@media (max-height: 720px)`: lo cubre entero el bloque único de la gramática 13. La migración 11 se llevó además el `style={{justifySelf:"start"}}` de `views.tsx:183` (lo pone `.k-topline__exit`, escrito para esto) y los dos `data-speaking` decorativos de la marca, que las Notas del átomo 16 prohíben |
| Género (`components/GenderReviewSession.tsx`) | `gender-review.css` entera (58 líneas) **y su `import` desde el componente**, que era el último que quedaba fuera de `main.tsx`: con él muere la mitad viva de la trampa 2 (el orden de carga de las hojas importadas desde componentes) y el `font-size: 12px` que era letra muerta. Se lleva además el `k-mono` que `GenderReviewSession.tsx:105` pintaba a mano sobre el contador: lo pone la tira |
| Mapa de curso (`routes/Module.tsx`) | `path.css` entera (87 líneas). **De las 87, 62 ya estaban muertas**: el bloque `.path__*` —el camino del curso con sus cinco estados de fila y su barra dual— no tenía un solo consumidor en el árbol; lo habían sustituido `.k-row` y `.k-bar` en migraciones anteriores y la hoja se quedó de pie sosteniendo dos supervivientes: `.path__kicker` (un uso) y el bloque `.mod__*`. Se lleva además los dos `.k-link` de `Module.tsx:76` y `:85`, que pasan a `.k-btn k-btn--text` siguiendo el mapa del átomo 1 (ver decisión 17) |
| El popover de palabra (`components/WordPopover.tsx`, `BreakdownPopover.tsx`) | **Hecho en la migración 14**: el bloque `wpop*` entero (118 líneas) fuera de `pages.css`, que baja de 705 a 587 |
| Práctica y Ajustes (`routes/Practice.tsx`, `Settings.tsx`, `NewStory.tsx`) | **Hecho en la migración 15: `pages.css` borrada entera.** De sus 587 líneas restantes, **382 ya estaban muertas** —`home*`, `story-end*`, `story__new*`, `ph*`, `.placeholder`, `.story`: cero consumidores en el árbol—. Lo vivo era `snew*` (cuatro ficheros), `.story__back` (uno), `.story-loading` (dos), `kp-*` (uno) y la redefinición de `:root` de las líneas 776-781, que muere con la hoja. Se llevó además a `InvitationsPanel` y a `PasswordSetForm`, que consumían `snew*` |
| Cascarón antiguo de escritorio (`components/Masthead.tsx`, `App.tsx`) | `global.css:87-254`: `kapp`, `kframe`, `k-masthead` y familia, `k-page`; el armazón pasa a `.k-app`/`.k-page` de `sistema.css`. **BLOQUEADO — no es una migración de CSS, es la arquitectura de navegación de la v4.** Ver la decisión 18 |
| Cascarón móvil (`.m3-app`, `.m3-page`) | `mobile3.css:7-14` y su `@media (max-height:720px)` de las líneas 87-98, cuando la última pantalla haya pasado a `.k-app`/`.k-page` |

Cuando `pages.css` muera hay que quitar además su `@import` de `global.css:7`, y cuando muera la última hoja de función, su `import` de `main.tsx:8-17`.

---

## Pendientes

Cada entrada dice qué es, dónde vive hoy y qué migración de pantalla la decide. Ninguna entra en la v1 del sistema.

**Átomos candidatos (17–22 de `faltantes.md`; el 17 sí entró):**

| # | candidato | evidencia | lo decide |
|---|---|---|---|
| 18 | **Capa flotante anclada** (con ancla y cola) | `pages.css:485 .wpop` (+`__tail`, dos consumidores) · ~~`onboarding.css:444 .ob-isel__menu`~~ · primo móvil `mobile3.css:154 .m3-sheet` | la migración de Lectura: el popover de palabra y la hoja inferior son el mismo componente con dos anclajes. Hoy se cubre con `.k-card--anchored` y `.k-sheet` por separado. **La migración 8 gastó el consumidor del onboarding sin necesitar el átomo**: el menú anclado a una palabra de la frase es, en un teléfono de 430px, la hoja inferior de siempre (`.k-scrim` + `.k-sheet` + `.k-row`), y el ancla se dice con el fondo de «de esta estamos hablando» sobre la propia palabra. **Cerrado por la migración 14, y la respuesta es que no:** los dos popovers son `.k-card k-card--flat k-card--anchored` sin una clase propia, y lo único que la variante tuvo que aprender es su **métrica**. Los 26/22 de relleno y los 16 de hueco de la ficha plana están pensados para una ficha que ES la pantalla; encima de un pasaje que se está leyendo, esa misma caja tapa el texto que el globo viene a explicar. Dos declaraciones (`padding: var(--space-4)`, `gap: var(--space-3)`) y `--anchored` deja de ser solo «dónde flota» para ser también «cuánto ocupa». **Un átomo nuevo habría sido la misma superficie con otro nombre** |
| 19 | ~~**Píldora de proceso**~~ (grabando · evaluando · spinner · VU) | ~~`finish.css:656/696`~~ · ~~`sentence-view.css:320/377`~~ · ~~estados de presencia de `speak.css`~~ · `perfil-aprendizaje.css:78 .ob5-esperando` (la marca usada de spinner) | **Cerrado.** Hablar decidió que no, la migración 6 lo confirmó al segundo consumidor y la 7 gastó el último: las tres píldoras de `finish` (grabando con VU de 16 barras, evaluando con spinner) son una `.k-cap` con el rótulo vivo en `.k-cap__count[data-tone="live"]`, aquí en el pie de la ficha en vez del dock, porque en el quiz el pie de la ficha ES el dock. Mueren con ellas `lib/audioBars.ts` y los tres `recBarsRef` |
| 20 | ~~**Bloque de cifra / ledger**~~ | ~~`pages.css:698 .kp-stat*` y `:650 .kp-source*`~~ · ~~`recall-review.css:305 .rr-done__ledger`~~ · `finish.css:136 .fin-hero__meta` · `perfil-aprendizaje.css:12 .ob5-meta` · ~~`speak.css:277 .kp-stat__of`~~ | **Cerrado.** Repaso decidió que no y la migración 6 gastó la otra mitad: las dos cifras del preparar (`kp-source`) y las tres del cierre (`kp-stat`) son `.k-hero__meta` con `<strong>`, y las tres filas de «cuándo vuelven» (`kp-returns__item`, una rejilla propia) son `.k-row k-row--quiet` con `__title`/`__meta`/`__sub`. Ni una regla nueva |
| 21 | ~~**Encabezado de pantalla**~~ (kicker + h1 + bajada + filete) | `pages.css` ×4 (`snew__head`, `kp-setup__head`, `kp-sum__head`, `ph__head`) · `auth.css:8` · ~~`onboarding.css:153 .ob-prompt`~~ · `landing.css:24` · `gender-review.css:19` | **La migración 8 decidió que no entra.** `ObPrompt` es hoy `.k-hero k-hero--quiet` (`__title` + `__dek`) seguido de un `.k-hairline`, sin una sola regla nueva y en las cinco pantallas del onboarding. Si tres átomos puestos en fila cubren el encabezado, el encabezado no es un átomo — es una composición, y como tal vive en el `.tsx` de quien lo usa. **La migración 9 gastó el consumidor de `auth.css:8`** con la misma composición y sin componente intermedio: cinco pantallas más, escrita a mano, y ninguna pidió nada. **La migración 10 gastó `landing.css:24`, y de una manera que confirma la decisión por el otro lado**: la portada resultó tener dos niveles de encabezado —el tagline y los cuatro rótulos de sección— y el sistema tiene uno, así que si el encabezado hubiera sido un átomo, los cuatro rótulos habrían salido del tamaño del titular. Lo que los cubre no es un encabezado de pantalla: es la cinta del átomo 6. **La migración 12 gastó `gender-review.css:19`** con el mismo par (`.k-hero k-hero--quiet` + `__title`), salvo en la fase de sesión, donde el título deja de encabezar y pasa a orientar (`.k-topline__title`), que es lo que ya hacen Lectura, Repaso y el cierre: cuando la pantalla ES una ficha, el titular sobra. **CERRADO del todo por la migración 15**, que gastó los cuatro de `pages.css` de una vez: `snew__head` (Nuevo relato y la puerta de contraseña), `kp-setup__head` (Práctica) y su gemelo de Ajustes son todos `.k-hero k-hero--quiet` con `__tag` + `__title` + `__dek`, y los otros dos (`kp-sum__head`, `ph__head`) estaban muertos. **Seis pantallas más, ninguna regla nueva, y la decisión aguantó los ocho consumidores.** El caso interesante es el encabezado de SECCIÓN dentro de una página —«Cuenta», «Seguridad», «Invitaciones»—: el sistema tiene un solo nivel de titular y ya lo gasta la página, así que lo que encabeza una sección es la cinta del átomo 6 (`.k-cap k-cap--rule`) y el rótulo de lo que se va a hacer ahí es el `.k-note__cap` de su propia nota. Es la misma salida que la 13 dio a los hechos del módulo |
| 22 | **Estado de carga de pantalla** (~~incluido el esqueleto~~) | `pages.css:475 .story-loading` · ~~`recall-review.css:22`~~ · ~~`gender-review.css:51`~~ · ~~`finish.css:887/973`~~ · `mobile4.css:45 .m4-pensando` · `perfil-aprendizaje.css:78 .ob5-esperando` | **El esqueleto queda descartado por la migración 7**, que era su único consumidor: los dos de `finish` (cuatro renglones para el apunte, uno para la nota de Klara) pasan a una `.k-note` con la copia de carga, que es lo mismo que la migración 6 decidió para la «nota cargando». Una caja gris que late es la píldora de proceso otra vez. Lo que sigue abierto es el **estado de carga de pantalla entera** (hoy `.k-spinner` suelto en el `.k-fill`), y lo decide Biblioteca. **La migración 11 gastó `perfil-aprendizaje.css:78`** sin necesitar el átomo: la espera de la síntesis es la copia de carga dentro de una `.k-note k-note--bare` con `role="status"`, que es lo que ya decidieron la 6 y la 7. **La 12 gastó `gender-review.css:51`** con el `.k-spinner` suelto que sus vecinas del mismo cascarón ya usan (`Module.tsx:119`, `Pronunciar.tsx:215`, `Repaso.tsx:104`), y de paso el rótulo se va del centro de la pantalla al `aria-label`: la carga no es texto que leer. **La 13 gastó el tercer sitio donde `.story-loading` se escribía** (`Module.tsx:67`) con el mismo spinner suelto. **La 15 gastó los dos últimos** (`ProtectedRoute.tsx:15` y `Settings.tsx:73`) con el mismo `.k-spinner` suelto y el rótulo en el `aria-label`. **Cerrado: el estado de carga de pantalla entera NO es un átomo.** Cuatro migraciones seguidas llegaron a la misma respuesta sin ponerse de acuerdo, y las dos formas que hay son las dos que ya existían: spinner suelto cuando no hay nada que leer todavía, y copia de carga dentro de una `.k-note` cuando lo que se espera es texto |
| — | ~~**Deslizador CEFR**~~ | ~~`pages.css:229 .snew__range`~~ | **Cerrado por la migración 15, y no hizo falta el átomo.** Ajustes sobrevive, pero el nivel no se elige con un deslizador: se elige con seis rótulos cortos de los que solo uno queda pulsado, que es exactamente `.k-wrap` de `.k-chip` con `role="radio"`. El onboarding ya elegía el mismo dato con el mismo vocabulario (`StepLevel` usa `.k-row--boxed`, porque allí cada nivel trae su frase); aquí no hay frase, así que es la nube. **Mueren con él sus dos `::-webkit-slider-thumb` / `::-moz-range-thumb`, que eran la única pieza de la app que se pintaba con pseudo-elementos de proveedor**, y de paso el control sube de 18px de pulgar a seis objetivos de 44 |

**Estados fuera del brief que no entraron:**

| estado | evidencia | pantalla que lo decide |
|---|---|---|
| ~~Los cuatro `data-state` de la opción de quiz~~ (correcta · incorrecta · revelada · atenuada), con barra `inset 3px`, y su **insignia de letra** circular de 26px | ~~`finish.css:362-394 .qcard__opt`, `:334 .qcard__opt-letter`~~ | **La migración 7 decidió que no entran, ninguno.** La opción respondida dice tres cosas y las tres ya tienen átomo: la buena lleva `.k-row[data-state="selected"]` (el canto de 3px, que ES la barra `inset` de esta hoja), el veredicto lo pone un `.k-chip k-chip--static[data-tone="good"\|"bad"]` con su punto y su glifo —color **y** forma, no solo color— y el resto van `[data-state="locked"]`. La insignia circular pasa a `.k-row__n`: la letra queda, el círculo no (regla 5) |
| ~~Hueco rellenable~~ (`empty` · `correct` · `revealed`) | ~~`finish.css:421-446 .qcard__blank` + `__blank-rule`~~ | **La migración 7 decidió que no.** Relleno, el hueco es una palabra puntuada del pasaje y nada más: `good` acertada, `bad` revelada, con el subrayado del átomo 14. Vacío es el `___` literal que `GenderPicker` ya escribía; el filete dibujado de `__blank-rule` no hacía falta para eso |
| ~~Contenedor apagado hasta oírlo~~ (`data-played`) | ~~`finish.css:465-475 .qcard__shadow-sentence`~~ | **La migración 7 decidió que no.** Antes de tocar «reproducir» no hay pasaje que leer: hay una instrucción («toca para escuchar»), y eso es una `.k-note`. Atenuar la oración era decir con tinta lo que la copia ya decía, y encima con la oración a la vista |
| ~~Fila negativa / excluyente y fila «otra cosa» que abre un campo~~ | ~~`perfil-aprendizaje.css:46 [data-nega]`/`[data-otra]`~~ | **La migración 11 decidió que SÍ, como una sola variante: `.k-row--aside`.** Los dos atributos pintaban lo mismo, y lo que dicen es lo mismo: «esta opción no es una respuesta, es la salida». La itálica no es un adorno nuevo — es la que el sistema ya usa en `.k-row__sub`, `.k-note` y `.k-topline__title` para decir «al lado del contenido». Variante y no `data-` porque lo decide el catálogo, no el uso |
| ~~Fila que recuerda que costó~~ (`data-struggled`) | ~~`finish.css:857 .fin-sched__item[data-struggled]`~~ | **La migración 7 decidió que no**, como ya prescribía el mapa del átomo 4: el punto de acento y la tinta subida se van, y «se atascó hoy» pasa a `.k-chip k-chip--static[data-tone="bad"]` con su punto. El chip **dice** lo que el punto solo teñía |
| ~~Segmento **saltado** (hueco con anillo) y grupos con peso `--w`~~ | ~~`perfil-aprendizaje.css:27`, `:24`~~ | **La migración 11 partió la decisión: el saltado entra, los grupos no.** El saltado es información —una pregunta en blanco no es una pregunta por responder— y cabe en la escala de tinta que el átomo ya tiene, sin anillo. Los grupos con peso no: el sistema tiene una barra de segmentos, y el bloque en el que vas lo dice el título de la tira |
| Segmento **again** (la tarjeta que vuelve en la misma sesión) | `recall-review.css:94` (diseñado y muerto; la hoja ya no existe) | Repaso lo dejó fuera a propósito: la barra de sesión dibuja `done`/`now` como en lectura. Vuelve si algún día el SRS reencola dentro de la sesión y hay que verlo |
| Cinta con aviso en acento junto al contador | ~~`taller.css:223 .preview-head .flag`~~ | **Taller decidió que no**: el aviso pasa a `.k-chip k-chip--static[data-tone="bad"]` con su punto, y el acento de la marginalia sigue siendo uno solo (el «grabando» del dock) |
| Chip **añadir** (borde discontinuo) y chip en **edición** (`chip-input`) | ~~`taller.css:192 .chip.add`, `:197 .chip-input`~~ | **Taller decidió las dos**: el discontinuo no entra (igual que `.m4-add` en la migración 1) y el chip en edición **es** el chip —`<input class="k-chip">`—, así que `.k-field--chip` no llega a existir |
| ~~Chip **cuadrado** de 44px y **seleccionado negativo**~~ | ~~`perfil-aprendizaje.css:56-59`~~ | **La migración 11 decidió que no, ninguno de los dos.** El chip es la píldora, y el triaje lo dice con palabras («Sirve» / «No») en vez de con dos glifos bajo un encabezado de columnas. El seleccionado negativo —papel apagado y tinta baja— se leía como deshabilitado: un chip elegido es un chip elegido, y cuál de los dos es lo dice su rótulo |
| ~~Nota con **regla punteada = procedencia** (dicho vs. observado)~~ | ~~`perfil-aprendizaje.css:81` + `:82`~~ | **La migración 11 decidió que no hace falta filete nuevo: la distinción ya existe y es `--bare` contra el filete normal.** Lo que Klara observó va a plomo; lo que dices de ti va al margen, que es exactamente como el sistema atribuye lo tuyo en Hablar (`.k-live__turn[data-who="you"]`, `border-left: 2px`). Y la leyenda lo decía ya con esas palabras —«Arriba, lo que hiciste. Al margen, lo que dices de ti»— antes de que nadie la tradujera: la copia describía el sistema, no la hoja vieja. La leyenda además pierde su propio filete (`--bare`): explica el margen, no está en él |
| ~~Nota **cargando**~~ | ~~`sentence-view.css:462 .k-diagnose-tip--loading`~~ | **La migración 6 decidió que no.** «Buscando la corrección…» es texto que aparece y se sustituye dentro de la misma `.k-note` del veredicto —así lo hacía ya `EstudiarView` desde la migración 2—, no un estado de la nota. Una nota que se atenúa mientras espera es la píldora de proceso otra vez, y por la puerta de atrás |
| ~~Error **de pantalla completa** y error **en lista con número de línea**~~ | ~~`recall-review.css:37 .rr__empty` · `taller.css:307 .rejected li`~~ | **Cerrada.** Repaso: no hacía falta un estado nuevo sino distinguir dos tonos —el vacío es `.k-note`, el fallo de carga es `.k-error`—. Taller: la lista es `<ul class="k-error">` y solo pedía `list-style: none` |
| ~~Botón redondo **destructivo** (salir, hover en acento)~~ | ~~`speak.css:248 .kc-ctrl--end`~~ | **Hablar decidió que no.** «Terminar» es un `.k-rbtn` normal con su aspa: lo que se pierde es el hover en acento, y con razón —el acento del sistema es uno solo y es el de grabar—. Terminar no destruye nada: cierra la charla, guarda las palabras y enseña el cierre |
| ~~Marca **entrando**~~ (`scale .88→1`) y ~~**firma «— K»**~~ | ~~`onboarding.css:268`~~ · ~~`finish.css:965 .fin-note__sign`~~ | **Cerrado: la migración 8 decidió que la marca no entra animada.** Era la coreografía de la bienvenida, y la bienvenida ya no tiene una K de 140px que presentar: la marca vive en la línea superior, del tamaño que tiene en toda la app. Una animación de entrada para una sola aparición no es un estado del átomo. La **firma no entra**: la migración 7 la escribe «— » + `<KlaraMark>` dentro de una `.k-note k-note--bare`, que es el mismo pie que Repaso ya usaba desde la 3; la K de texto de `.fin-hero__k` pasa también a la marca de verdad, que sí puede respirar. Los ~~tres puntos de «pensando»~~ **no son de la marca**: Hablar los dejó en `.k-presence__think`, o sea en el escenario, porque `.klara-mark` no tiene ese estado y sus Notas prohíben el `data-speaking` decorativo |
| ~~Escenario de presencia (disco + anillo de ticks, cuatro estados)~~ | ~~`speak.css:83-134 .kc-presence`~~ | **Resuelto: era layout de pantalla.** Entra como armazón (`.k-presence`, gramática 12), no como átomo 18: la hoja de componentes sigue con 17 y `hoja.check.mjs` no cambia |
| ~~Animación de entrada de la ficha y coreografía escalonada del héroe~~ | ~~`finish.css:257-264 .qstage`~~ · ~~`onboarding.css:281-336`~~ | **Cerrado.** La 7 decidió que la ficha no entra animada: lo que cambia entre pregunta y pregunta ya lo dicen la barra de segmentos y el contador, y donde hay pasaje `page-in` de `.k-stage` lo anima al remontar. La 8 cerró la otra mitad: las seis animaciones escalonadas del onboarding (`ob-step-in` y sus dos direcciones, `welcome-mark-in`, `welcome-text-in` con cinco retardos, `whisper-in`, `isel-in`) mueren enteras. Iban en ms literales contra §7.6, y ninguna decía nada que el paso de capítulo no diga ya con el contador y la barra |
| Borde **discontinuo** como afordancia de «añadir» (subir archivo, mosaico de tema nuevo) | `mobile4.css:25 .m4-add .tile`, `:42 .m4-upload` | Biblioteca |

**Deuda de tokens:**

- Los tres colores de puntaje (`--score-good`, `--score-ok`, `--score-good-ink`) **no tienen variante oscura**. El verde de `oklch(0.62 0.13 145)` sobre papel oscuro `#16181C` funciona, pero no está ajustado. Lo decide la migración de Lectura, que es donde más se ven.
- ~~La escala tipográfica no tiene paso por debajo de `--t-meta`~~ **Resuelto:** `--t-mono: 11px` existe en `tokens.css` y la gramática 10 lo hace obligatorio.
- **No hay tokens de tamaño de control.** El sistema usa exactamente dos alturas, 44 y 56px (más 72px para el redondo grande), escritas literales. Merecen dos tokens (`--ctl: 44px`, `--ctl-lg: 56px`) cuando la primera pantalla migre y se vea que no cambian.

---

## Trampas conocidas

1. ~~**La regla global de reduced-motion vive en el sitio equivocado y hace daño.**~~ **Resuelta en la migración 3.** `recall-review.css:333-337` declaraba `*, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important }`, y como `App.tsx` importa las rutas de forma estática (cero `lazy`), esa hoja se cargaba siempre y la regla se aplicaba en toda la app: **mataba `--dur-breath`** —el latido de la marca que §3.4 declara intocable— y además lo congelaba en el 0 % del keyframe, donde la opacidad es 0, o sea sin halo. Murió con la hoja. La lección que queda: una regla `*` con `!important` dentro de una hoja de pantalla es global aunque su nombre diga lo contrario; `sistema.css` apaga sus animaciones con `animation: none` átomo por átomo y conserva el halo visible.

2. **Orden de carga: `main.tsx:5` importa `App` antes que `global.css` (main.tsx:6).** `global.css` mete `tokens.css` y `pages.css` por `@import` (global.css:6-7), pero las hojas que se importaban desde componentes se inyectaban **antes** que `global.css`. Efecto verificado en su día: `.k-mono` ganaba a `.gr__progress` con la misma especificidad, y el `font-size: 12px` de `gender-review.css:28` era letra muerta. **Cerrada en la migración 12**, que borró la última (`recall-review.css` murió en la 3, `taller.css` en la 4 y `gender-review.css` en la 12): hoy no queda ninguna hoja importada desde un componente, así que todas las de pantalla entran por `main.tsx`, después de `global.css`, y en el orden en que están escritas. `sistema.css` se importa en `main.tsx` justo después de `global.css`, así que **gana a todas las hojas de función** y esa es exactamente la posición que se quiere durante la migración: el átomo pisa al dialecto, no al revés.

3. **`pages.css:776-781` redefine `:root` dentro de `@media (max-width: 600px)`** y cambia `--t-h1` (a 40px), `--t-h2` (a 28px) y `--t-display` (a 64px) para toda la app. §3.1 del brief («no se tocan los valores de `tokens.css`») ya está roto desde una hoja de página, y el caso afectado es el principal: el teléfono. Ningún átomo del sistema se apoya en `--t-h1`, `--t-h2` ni `--t-display`; por eso `.k-hero__title` usa `clamp()` con el techo de **40px escrito literal** (con `var(--t-h2)` el techo colapsaría a 28px, o sea al piso del clamp). **Cerrada en la migración 15**, que borró `pages.css` y con ella la redefinición. Comprobado antes de borrar: los tres tokens no los consume nadie en `frontend/src` —ni una hoja ni un `.tsx`—, y el único consumidor vivo de `--t-h2` en todo el repo es `hoja.html:27`, el titular de la propia hoja de componentes. Los tres se quedan declarados en `tokens.css` por eso. El literal de 40px también se queda: el clamp del titular no debe depender de un token que ningún átomo consume.

4. **className fantasma: el `.tsx` pinta clases que ninguna hoja declara.** Verificados con grep: ~~`.k-tool`~~ y ~~`.kac-tool`~~ (0 declaraciones base; el de Hablar murió con la migración 5 y el de SentenceView con la 6, igual que `.kp-stat__of`), `.mono` (Taller.tsx:142 escribe `className="tally mono"` y la clase real es `.k-mono`), ~~`.fin-difficulty`~~ (StoryFinish.tsx:985), ~~`.k-wave__time`~~, ~~`.k-stepnav__btn--prev`~~ (SentenceView.tsx:621), ~~`.ob-isel__opt-label`~~ (ObInlineSelect.tsx:72), `.wpop__freq` (WordPopover.tsx:110), ~~`.story--audio` y `.story__pron-error`~~ (Practice.tsx:458 y 501). La migración 6 se llevó cinco de los diez de un tirón, y no por buscarlos: al borrar el componente y su hoja, sus fantasmas se fueron con ellos. La 7 se llevó el sexto (`.fin-difficulty`: la pregunta de dificultad es una `.k-cap` con tres `.k-btn` en un `.k-wrap`, y el `aria-pressed` que ya tenía) y la 8 el séptimo (`.ob-isel__opt-label` → `.k-row__title`). Quedan dos: `.mono` de Taller y `.wpop__freq`. La auditoría dice «108/108 clases usadas» porque cuenta CSS sin consumidor, no TSX sin CSS. Al migrar cada pantalla, cada uno de esos ganchos se borra del markup o se convierte en el nombre real del átomo; el mapa de arriba dice cuál.

5. **`hoja.check.mjs` conoce los 17 átomos y exige también las variantes.** Su tabla `ESTADOS` lista, por slug de átomo, cada `data-estado` que la hoja debe mostrar: los del §5 del brief más las variantes del contrato (`texto`, `tinta`, `plana`, `seleccionada`, `con-caja`, `con-regla`, `sin-caja`, `estatico`, `quieto`, `area`, `manuscrito`…). El slug del átomo 17 es `campo-texto`. La barra repite `segmentos`/`continua`/`hitos` como estados porque el chequeo los pide así.

6. **`hoja.check.mjs` mide ancho y alto, salvo en elementos `display: inline`.** La comprobación exige `width ≥ 44` y `height ≥ 44` en todo control; para los de `display` computado `inline` —solo `.k-word`— mide únicamente el alto, porque ensanchar la palabra rompe la línea que §6.2 declara «la pantalla». `.k-btn--text` **no** necesita excepción: lleva `min-height: 44px` y `min-width: 44px` con márgenes compensados.

7. ~~**`.taller .tally a` y `.taller .col {}` son reglas inertes, no clases muertas.**~~ **Sin efecto desde la migración 4**, que borró la hoja. La auditoría marcaba 0 clases muertas en `taller.css` y a nivel de clase era cierto; el selector de la línea 55 apunta a un `<a>` y el `.tsx` renderiza un `<button>` (Taller.tsx:149), y la regla de la línea 141 está vacía. Un recuento de clases no las ve.

8. ~~**`.kc-turn__fix` base nunca se ve.**~~ **Cumplido en la migración 5**, tal cual estaba previsto: sus dos únicos consumidores pasaban `data-tone="clear"`, el override de `speak.css:192` ganaba siempre, y el estado en acento se perdió sin que nadie lo notara. El acuse es hoy un `.k-chip k-chip--static[data-tone="good"]` con su punto. La lección que queda: una clase que **sí** aparece en el `.tsx` puede estar muerta igual, y un recuento de clases no lo ve.

12. **Dentro de `@media (prefers-reduced-motion: reduce)` la especificidad sigue mandando.** La consulta no eleva nada: apagar con `.k-presence__tick i { animation: none }` (0,1,1) lo que enciende `.k-presence[data-state="listening"] .k-presence__tick i` (0,3,1) no apaga nada. Medido en la migración 5: el anillo seguía oscilando con `reduce`, y `hoja.check.mjs` no lo veía porque el escenario es armazón y no sale en la hoja. La regla que apaga se escribe con el mismo ancestro y el mismo atributo que la que enciende. Es la trampa 11 otra vez, en su versión temporal.

9. **`--art-der/die/das` viven en `tokens.css`.** Están en `tokens.css:54-56` y `:118-120`. Salieron de `mobile3.css` antes de que esa hoja muriera del todo en la migración 2; `faltantes.md` §3 describe el estado anterior. Quien escriba `sistema.css` consume los tokens.

10. **El contenedor posicionado no es opcional.** `.k-scrim`, `.k-sheet`, `.k-tabs__menu` y `.k-card--anchored` se posicionan contra el ancestro relativo más cercano. Hoy ese ancestro es `.m3-app` (mobile3.css:10) y `hoja.html` no lo carga, así que sin el `.k-app` de la gramática 12 los cuatro se anclarían al viewport y la hoja de componentes mentiría.

11. **Acotar un selector protege solo lo que ese bloque nombra.** Es la trampa que costó la migración 2. `.k-page` y `.k-stage` se escriben con ancestro porque colisionan con clases vivas (gramática 12), pero la especificidad decide **por propiedad**: lo que el bloque acotado no declara sigue cayendo del homónimo global. Verificado: `.k-app .k-stage` heredaba `flex: 1`, `padding: 8px 0` y `text-align: center` de `sentence-view.css:81` y `:560`, y el pasaje crecía hasta el pie con la glosa descolgada al fondo. **La migración 6 cerró esa colisión** y con ella las tres declaraciones defensivas, que existían solo para tapar lo que el bloque acotado no nombraba; el ancestro se queda, pero ya como sitio, no como escudo. Quedan **cinco** nombres `k-*` de `sistema.css` declarados también en otra hoja —`.k-btn` (native, perfil-aprendizaje; taller salió en la migración 4), `.k-chip` (perfil-aprendizaje), `.k-page` (global), y `.k-link` y `.k-spinner`, que son utilidades de `global.css` que el sistema consume a propósito—. Antes de dar por buena una pantalla migrada hay que comparar la lista de propiedades del bloque acotado con la del homónimo, no solo mirar la captura. `.k-app > .k-page` hereda hoy `animation` y `min-width: 0` de `global.css:246`: es inocuo y se queda, pero es el mismo mecanismo.

14. **Una rejilla `auto 1fr auto` NO centra la pista del medio.** La línea superior de sesión se escribió así para que el título pudiera truncar, y con el contador vacío —la bienvenida y el cierre del onboarding— la pieza central queda medida contra el hueco que sobra a la derecha de «Salir»: 19,7px descolgada, medidos. `justify-self: center` no salva nada, porque centra dentro de la pista, no dentro de la tira. Solo se centra de verdad si las dos pistas laterales son iguales (`1fr auto 1fr`), y eso solo se puede hacer cuando el centro es corto —el lockup de la marca, el chip de foco—, no cuando es un título que trunca. De ahí las dos reglas con `:has()`. La lección general: **centrado ≠ `justify-self: center`**; hay que medir el centro de la pieza contra el centro del contenedor, que es una línea de sonda y ninguna captura la delata.

15. **Los `.js` compilados que quedan en `src/` tapan a los `.tsx`, y la sonda mide código viejo.** Medido en la migración 9: 112 ficheros `.js` (+ `.js.map`) sueltos junto a sus fuentes, ignorados por git y por eso invisibles en `git status`, sellados ese mismo día por algún `tsc` sin `--noEmit`. `main.tsx:5` escribe `import App from "./App"` sin extensión y el orden de resolución de Vite pone `.js` **antes** que `.tsx`: el build entero se ensambló contra el árbol viejo. El síntoma fue que la primera corrida de `probe-auth.mjs` devolvió `auth-input` en pantallas que ya no lo pintan; el `dist/` llevaba las dos versiones a la vez. Ni el typecheck lo ve (lee los `.tsx` que dice `tsconfig`) ni el build falla (el `import` muerto de `auth.css` vivía en `main.js`, que no es la entrada). La comprobación barata antes de creerle a una sonda: `grep` de una clase que la migración acaba de matar contra `dist/assets/*.js`. Se limpian con un borrado de los `.js` **no rastreados** bajo `src` —`src/lib/pcmWorklet.js` sí está en git, es un AudioWorklet y tiene que seguir siendo JS plano—.

    **Causa encontrada en la migración 12, y arreglada:** no era «algún `tsc` sin `--noEmit`» suelto — era **el propio gate**. `npm run build` es `tsc -b && vite build` y `tsc -b` EMITE, así que cada corrida del gate volvía a sembrar los 108 ficheros. Se cierra con una línea en `frontend/tsconfig.json` (`"noEmit": true`): el chequeo de tipos es lo único que se le pide a `tsc` ahí, el bundle lo hace Vite. Verificado: `npm run build` sigue produciendo `dist/` y deja **cero** `.js` bajo `src`. La lección general: **antes de tratar un artefacto raro como accidente, hay que preguntarse qué comando del repo lo produce** — este llevaba tres migraciones re-sembrándose después de cada verificación.

16. **Un literal portado se mide contra su vecino nuevo, no contra el viejo.** `.auth-actions` traía `margin-top: var(--space-4)` (16px) y portarlo tal cual parecía lo fiel. Pero aquel 16 convivía con campos separados 12px (`.auth-form` era una columna con `gap: var(--space-3)`), y en el sistema los campos van a 18px (`.k-field + .k-field`): el mismo número que separaba pasó a acercar, y el botón de enviar quedaba **más cerca del último campo que los campos entre sí**. Es una inversión de jerarquía que ninguna captura grita y que la aritmética delata en un segundo. Al portar un hueco hay que comparar los dos vecinos de la junta después de la migración, no el valor consigo mismo.

17. **Un suelo en `:where()` no pisa un átomo que trae su propio margen.** Las juntas del sistema se escriben con especificidad 0 a propósito —son suelos, no mandatos— y eso funcionó dos veces (`.k-hero + .k-bar`, `.k-field ~ .k-wrap`) porque `.k-bar` y `.k-wrap` no declaran margen: no hay nada que pisar. La tercera falló en silencio: `:where(.k-cap) + :where(.k-note)` contra `.k-note { margin: 18px 0 0 }` (0,1,0) no anula nada, y la sonda midió los 18px de siempre donde la regla prometía 2. Ni el build ni el typecheck ni la captura lo dicen; lo dijo la medida de la junta, que existe precisamente para eso. **La regla: antes de escribir una junta, mirar si el átomo de destino declara ese margen.** Si lo declara, la junta es un mandato y va con dos clases, como `.k-band > .k-note`.

18. **Una captura `fullPage` no ve nada bajo el pliegue cuando el scroll es interno.** `.k-app` mide `100dvh` con `overflow: hidden`, así que el documento nunca crece y `fullPage: true` devuelve exactamente el viewport: 844px. Todo lo que viva en un `.k-live` más abajo —el resumen del cierre, el pie de la portada— está fuera del encuadre y **un diff de capturas verde no dice nada sobre él**. Medido en la migración 10: la regla del átomo 6 cambia dos rótulos del cierre de historia (18px → 2px, verificado) y las capturas de `cierre-resumen` salieron byte-idénticas en los dos temas. Para ver bajo el pliegue hay que scrollear a la pieza antes de disparar, y por eso el arnés tiene ahora una ruta `cierre-apuntes` que solo existe para eso.

19. **Un estado que solo aparece con el cursor encima no lo ve nadie: ni el teléfono, ni la hoja, ni el diff de capturas.** `.k-chip:not(.k-chip--static):hover` es (0,3,0) y `.k-chip[data-selected="true"]` es (0,2,0), así que el hover **ganaba** y le ponía `color: var(--ink)` a un chip con fondo de tinta: el rótulo del chip pulsado desaparecía bajo el puntero, negro sobre negro. Llevaba ahí desde la hoja de componentes. No lo ve el arnés de rutas (Playwright no deja el cursor encima), no lo ve `hoja.check.mjs` (mide tamaños y estados declarados, no combinaciones), y en el teléfono no existe. Lo enseñó **una captura de la sonda, por accidente**: el clic de la sonda deja el puntero donde pulsó. **La lección:** un `:hover` que declara color tiene que excluir a los estados que ya lo declaran, y no por orden de escritura —eso basta cuando la especificidad empata, como en el `:disabled` del átomo 1— sino con `:not()`. Y la segunda: hay estados que solo se ven en escritorio, y la única herramienta que los pilla es mirar una captura tomada después de un clic.

20. **Una pseudo-clase de posición en el selector base convierte el `@media` en letra muerta.** `.k-app > .k-page` reponía su `padding-top` con el inset dentro de `@media (max-height: 720px)`, y al pasar ese `padding-top` a `.k-app > .k-page:first-child` (migración 11) la reposición comprimida se quedó en (0,2,0) contra un (0,3,0): la página comprimida seguía con los 16px del bloque normal. Es la trampa 12 otra vez —`@media` no eleva la especificidad— pero por un cambio que parecía inocuo: **añadir una pseudo-clase a un selector obliga a revisar todas sus reposiciones**, empezando por las que viven dentro de una consulta.

21. **Una consulta que reposiciona una propiedad le gana a la variante que la apaga, y la variante ni se entera.** El bloque de compresión (`@media (max-height: 720px)`) declaraba `.k-hero { padding: var(--space-3) var(--space-4) }` para que el bloque sólido encogiera en pantallas bajas. Pero `.k-hero--quiet { padding: 0 }` es también (0,1,0) y está escrita **540 líneas antes**, así que la consulta se lo devolvía: en todo teléfono de ≤720px de alto —los de 667px y cualquiera en horizontal— **los 31 héroes apagados de 22 ficheros salían con 12px arriba y 16 a los lados que su propia variante había apagado**. Es la trampa 12 por tercera vez, y la más cara de las tres porque no la delata nada de lo que se mira normalmente: el arnés de rutas fotografía a 390×844 y ahí la consulta ni entra; `hoja.check.mjs` mide la hoja de componentes, no las pantallas; y el rectángulo del propio héroe **no cambia**, porque un `--quiet` no tiene fondo: lo único que se mueve es dónde empiezan sus hijos. La encontró la sonda del mapa midiendo el borde izquierdo de una pieza **hija** del héroe en un viewport de 667px. **Dos lecciones. Una:** cuando una consulta reposiciona una propiedad de un bloque, hay que preguntarse qué variantes de ese bloque la apagan, y excluirlas (`​.k-hero:not(.k-hero--quiet)`). **Y otra, de método:** el arnés de rutas no cubre viewport corto, así que la compresión de la gramática 13 solo la ve quien la mide a propósito — y hasta ahora ninguna sonda medía una pieza interior de un héroe apagado.

22. **`overflow` recorta a los hijos que viven FUERA de la caja, y en una capa anclada eso es la cola.** El globo del popover necesitaba scroll propio para el caso en que no cabe (un lema compuesto pasa de 550px), y `overflow-y: auto` lo resolvía — y de paso se comía el rombo de `.k-card__tail`, que está en `bottom: -6px`, o sea fuera del borde. **La captura lo enseñó y la medida no**: `getBoundingClientRect` de la cola devuelve sus 14px tan contenta porque el elemento existe y tiene caja; lo que no existe es su pintura. La salida es no declarar el `overflow` siempre sino solo cuando de verdad desborda (`[data-scroll="true"]`, que pone el `.tsx` después de medir), así el caso normal conserva la cola. **La lección general: un `overflow` distinto de `visible` es incompatible con cualquier decoración que asome del borde** —cola, muesca, halo, canto negativo—, y ninguna medida de caja lo delata.

13. **Un átomo con margen negativo necesita un contenedor con relleno.** `.k-btn--text` hace crecer su área táctil hacia afuera (`margin: -12px calc(-1 * var(--space-3))`), y eso funciona en la línea superior, en el dock y en el pie de la ficha, que traen 22px de relleno propio. `.k-row` no tiene relleno lateral: ahí el voladizo se sale. Medido en la migración 7 —12px de scroll horizontal dentro de `.k-live`, en la agenda del cierre— y **no** lo veía ni `document.scrollWidth` (la columna viva se lo comía en scroll propio) ni la captura. Se cancela con `.k-row > .k-btn--text { margin-inline: 0 }`; los 44px de lado los sostiene el `min-width` del átomo, no el margen. La lección general: al medir desbordamiento hay que medirlo **por contenedor de scroll**, no solo contra el documento.

---

## Enmiendas que pidieron las pantallas reales

La hoja muestra átomos sueltos; la pantalla los compone. Cada migración deja aquí lo que la composición pidió y la hoja no sabía. Migración 1 (cascarón, TabBar, SessTop, Biblioteca, Mapa, Perfil, Nuevo — PR #173):

- `.k-row > .k-bar { flex: 1 0 100%; order: 2; margin-top: var(--space-2) }` — la barra dentro de una fila es línea propia (mapa del átomo 4: `.m4-tema .m4-bar` → `.k-bar` dentro de la fila). Sin esto la pista se colapsaba a 0px y la barra de progreso del curso desaparecía de Inicio.
- `.k-row:has(> .k-row__n) .k-row__sub { padding-left: calc(22px + var(--space-3)) }` — la bajada se sangra a la columna del título cuando hay numeral; si no, cae bajo el numeral.
- `.k-bar--milestones { position: relative }` + `.k-bar--milestones .k-cap { position: absolute; …; color: var(--accent) }` — «estás aquí» en acento sobre el punto (mapa del átomo 5: `.m3-cefr .aqui` → `.k-cap` en acento sobre el punto). Los hitos y el punto van **fuera** del nodo `role="progressbar"` (children presentational) para que el lector de pantalla los lea; la hoja se corrigió igual.
- `:where(.k-hero) + :where(.k-bar) { margin-top: var(--space-3) }` — junta héroe + barra (Portada): sin ella la barra se leía como subrayado del título.
- `.k-topline` deja de sumar `env(safe-area-inset-top)`: lo pone `.k-page` (gramática 12) y con los dos se duplicaba el hueco en el teléfono con muesca.

Migración 2 (lectura: EstudiarView y Story, lo último que quedaba en `mobile3.css`). La sesión no se compone con `.k-page`: es una columna de tres tramos —pasaje que crece, pie que no— y ninguno era un átomo, así que entran como armazón (gramática 12) y no como pantalla:

- `.k-fill` — el tramo que crece y centra el pasaje. Sin él, `.k-stage` se pegaba arriba y la glosa quedaba a la deriva; `.k-page` no sirve, porque paga padding de página y aquí el aire lateral es 28px, no 22.
- `.k-dock` (+ `.k-dock__status` y `.k-dock__row`) — el pie de transporte. La línea de estado reserva `min-height: 18px` para que encender y apagar el rótulo no salte la fila de redondos, y el área táctil del control de velocidad deja de ser un parche de la hoja (`mobile3.css:55`): la trae `.k-btn k-btn--text`.
- `.k-band` — el pie de respuesta, que sustituye al dock. `min-height: 130px` —lo que mide el dock— para que el pasaje no salte al cambiar un pie por otro; el `gap: var(--space-4)` reparte el aire, y por eso la nota pierde aquí su margen superior de glosa (`.k-band > .k-note { margin-top: 0 }`).
- `.k-app > .k-bar` — los 22px de sangrado y el `flex: 0 0 auto` de `.m3-prog`: la barra de sesión cuelga del cascarón, no de `.k-page`, así que nadie más le pone ese aire y sin la regla los segmentos salían a sangre mientras la línea superior y el dock seguían sangrados.
- Lo que encontró la revisión visual de esta ronda, y que la captura sí veía: el `.k-stage` de `sentence-view.css` colándose por las propiedades que el bloque acotado no nombra (ver «Trampas conocidas» 9); los 18px de margen del `.k-cap` escapándose por colapso y engordando el dock; el alto de la línea de estado, que tenía que ser fijo y no mínimo; y el veredicto de la banda, que con `--ink-3` se quedaba en 4.22:1 sobre papel oscuro y vuelve a `--ink-2`, la tinta que ya tenía en `mobile3.css:44`.
- Colateral de la misma migración: `.k-app .k-stage` gana el `page-in` que tenía `.m3-oracion`, y el alias `.k-bar__seg[data-done="true"]` **muere** —EstudiarView ya emite `data-state="done"|"now"`—. En viewport corto el dock y la banda se comprimen (gramática 13).

Migración 3 (repaso: la caja de fichas, lo último que quedaba en `recall-review.css`). El repaso deja de ser un segmento de Práctica y pasa a ser superficie suelta —`/repaso`, como `/estudiar/:id`—, porque el armazón de sesión es `.k-app` a `100dvh` y no se puede anidar dentro del `.kframe` del cascarón viejo. El paso «Repasar» de `courseView.ts` apunta ahí, y el selector de segmentos de Práctica navega en vez de montar. La composición pidió cinco cosas, todas del átomo, ninguna de la pantalla:

- `.k-btn svg { width: 16px; height: 16px; flex: 0 0 auto }` — el botón con icono que el mapa del átomo 1 prometía para `.rr-listen` («el triángulo por bordes se sustituye por trazo») y que no tenía medida. 16px es el cuerpo del rótulo redondeado al par.
- `.k-wrap > .k-btn--block { flex-basis: calc(50% - var(--space-2) / 2) }` — `--block` deja la base en 0, así que cuatro botones no envuelven nunca: se encogen por debajo de su rótulo (`white-space: nowrap`) y se salen. Con la base a media nube las cuatro calificaciones caen 2×2 y el par de la banda de lectura sigue midiendo exactamente un renglón.
- `.k-card__eg` y `.k-card__tx` ganan `overflow-wrap: anywhere` — **gramática 8**: `__word` lo traía y estos dos no, así que `Bundesausbildungsförderungsgesetz` dentro del ejemplo se salía de la cara por la derecha.
- `.k-card__rule { flex-shrink: 0 }` — cuando el contenido de la cara pasa de los 340px, el reparto flex encoge a todos y el único hijo de 1px desaparece: el filete se borraba justo en la ficha que más lo necesitaba. Verificado a nivel de píxel, no a ojo.
- `.k-card__face .k-card__answer { justify-content: center }` — el `text-align` de la cara no manda sobre las líneas de un flex, y una respuesta que envolvía dejaba el artículo solo y pegado a la izquierda. La ficha plana (el popover) se queda a la izquierda.

Y tres decisiones de composición que el contrato dejaba abiertas:

- **El vacío no es un error.** «No hay fichas por repasar hoy» va en `.k-note`; el fallo de carga, en `.k-error`. Cierra la fila «Error de pantalla completa» de los estados pendientes por la mitad que le tocaba a Repaso: no hacía falta el estado, hacía falta distinguir los dos tonos.
- **El candidato 20 (bloque de cifra / ledger) no entra por Repaso.** El cierre de sesión se compone con `.k-hero k-hero--quiet` —`__tag` (cinta), `__title` (la cifra), `__dek` (el rótulo) y `__meta` (el reparto vuelven/descansan, con `<strong>` en las cifras)—, que es exactamente lo que el mapa del átomo 12 ya prescribía para `.fin-hero__meta`. Los 88px de `.rr-done__count` bajan al techo de 40px del `clamp`. Queda pendiente solo por la mitad de Práctica.
- **La cara de espaldas se esconde del lector de pantalla.** `backface-visibility` no la quita del árbol de accesibilidad ni del tabulador: la respuesta se leía antes de voltear y se podía tabular al «Escuchar» invisible. `aria-hidden` en la cara inactiva + `tabIndex={-1}` en su único control. Sin movimiento la cara inactiva ya va en `display: none` y esto sobra sin estorbar. Es un defecto que venía de la hoja vieja, no de la migración.

Lo que se pierde, dicho: `recall.exit` («← Hoy») cede a `common.exit` de `SessTop`; `.rr-head__k` y `.rr-head__meta` (la K y el «REPASO · HOY» de la cabecera) se van con la línea superior de sesión, que es salida · título · contador; el segmento `again` de la barra sigue sin entrar (pendiente registrado); y `recall.rateHint` pierde su segunda cláusula —«esto agenda el próximo repaso»— en los seis idiomas, porque no cabía en la línea de estado en alemán y porque el `.k-btn__sub` de cada botón ya lo dice en concreto («1 día», «3 días», «1 sem», «2 sem»).

Migración 4 (el taller, lo último que quedaba en `taller.css`). Es la primera pantalla que **no** es teléfono: el taller se usa tecleando y pegando, vive a partir de 1024px y por debajo enseña una puerta. De ahí las cuatro piezas de armazón nuevas (`.k-desk`, `__gate`, `__rail`, `__col`, gramática 12) — el segundo cascarón. Lo demás salió de los átomos tal cual; solo hicieron falta cuatro reglas:

- `.k-topline > .k-hero { flex: 1 1 auto; width: auto }` — la cabecera del taller es título a la izquierda y recuento a la derecha en la misma línea de base, o sea un héroe dentro de una tira. El héroe nace `flex: 0 0 auto` con `width: 100%` porque su sitio normal es una columna, y en una fila eso sumaba su ancho **entero** al del contador: la página se salía 149px de ancho. Medido, no visto.
- `.k-row[data-empty="true"] .k-row__sub { color: var(--accent-ink) }` — la tarjeta a la que le falta el reverso, dicha en una lista. Es el mismo `data-empty` del átomo 3 y la misma decisión de `taller.css:254`: una sola señal, en la bajada, y las vecinas conservan su cuerpo.
- `input.k-chip { cursor: text }` — ver abajo.
- `ul.k-error { list-style: none }` — ver abajo.

Y cuatro decisiones que el contrato dejaba abiertas, las cuatro resueltas **sin vocabulario nuevo**:

- **El chip en edición ES el chip.** La etiqueta que se está escribiendo ya tiene la forma del chip en que se va a convertir, así que el `<input>` lleva `.k-chip` y no hace falta el `.k-field--chip` que el mapa del átomo 8 dejaba pendiente. Lo único que cambia es el cursor: en un campo la mano no dice nada y la barra sí.
- **El borde discontinuo de «añadir» no entra**, siguiendo lo que ya hizo la migración 1 con `.m4-add`: el chip de añadir es un `.k-chip` normal y lo que lo distingue es su rótulo.
- **La cinta con aviso en acento no entra.** El «2 incompletas» del recuento pasa a `.k-chip k-chip--static` con `data-tone="bad"` y su punto, que es el átomo que el sistema ya tiene para un acuse con tono, y así el acento de la marginalia sigue siendo uno solo (el «grabando» del dock).
- **El error que enumera líneas es un `<ul class="k-error">`** y lo único que hacía falta era quitarle la viñeta: el `padding` del bloque ya gana al del `<ul>`, y cada renglón se identifica por su número. Con esto cierra entera la fila «error de pantalla completa y error en lista» de los pendientes (Repaso cerró la otra mitad).

De las dos salidas que el mapa del átomo 3 ofrecía para la previsualización —`.k-card--flat` en una nube o `.k-row` en lista— entra **la lista**: veinte fichas pegadas se revisan leyendo hacia abajo, no mirando veinte cajas. Cuesta que el anverso baje de 22 a 17px y el reverso pase a la bajada (serif itálica de 13px): es lo que cobra tener una sola escala, y el filete que separa las filas lo pone el átomo.

Lo que se pierde, dicho: el cuelgue óptico de −17px del textarea (era layout de esa pantalla); el filete inferior de la cabecera de previsualización, que pasa a filete a la derecha (`.k-cap--rule`); la acción de guardar deja de ir alineada a la derecha —el sistema no tiene utilidad de alineación y no se inventa una por un caso—; y el riel gana filetes entre etiquetas, que son los del átomo 4.

Migración 5 (Hablar, lo último que quedaba en `speak.css`). Como Repaso, sale de `LegacyShell` y pinta su propio `.k-app`: es una sesión de voz, no una página con Masthead. La pantalla ya era «una sola superficie» —presencia arriba, conversación debajo, controles al pie— y ese reparto es exactamente el del armazón de sesión: línea superior · `.k-fill` · `.k-dock`. Lo que no cabía en ningún átomo entra como armazón (`.k-live` y `.k-presence`, gramática 12) y lo demás salió de los átomos tal cual. Cuatro reglas de composición:

- `.k-topline--session > .k-chip { justify-self: center }` — el foco de la sesión es un chip, no un rótulo, y la pista central de la rejilla lo estiraba de lado a lado: un elemento de rejilla se bloquifica y `justify-self` vale `stretch` por defecto.
- `.k-dock > .k-note, .k-dock > .k-error { margin-inline: auto; text-align: center }` — la guía se centra bajo la fila de redondos que comenta, como `.k-band > .k-note` ya hacía con el veredicto. El `margin-inline` es lo que centra la caja (la nota mide 64ch, no el ancho del dock); el `text-align`, lo de dentro.
- `.k-live__turn > .k-chip { margin-top: var(--space-2) }` — el acuse cierra el turno y el chip no trae aire propio.
- `.k-btn` y `.k-chip` declaran **`font-style: normal`** — y esto es un defecto del átomo, no de la pantalla: los dos declaraban `font-family` y no la inclinación, así que el «Dilo otra vez» del apunte salía en **serif cursiva** por herencia de `.k-note`. La gramática 9 dice que los controles son sans y derechos; ahora lo dice también el CSS. Cualquier botón dentro de una nota estaba mal desde el primer día.

Y cuatro decisiones que el contrato dejaba abiertas, otra vez **sin vocabulario nuevo**:

- **El candidato 19 (píldora de proceso) no entra.** «Quién actúa ahora» ya tiene sitio: `.k-dock__status` con una `.k-cap k-cap--center`, y el rótulo vivo en `.k-cap__count[data-tone="live"]` cuando escucha —el mismo acento del «grabando» de lectura, que sigue siendo el único de la marginalia—. El rótulo bajo el medallón se muda ahí y deja de haber dos líneas de estado en la misma pantalla.
- **El escenario es armazón, no el átomo 18.** Cuatro estados que ninguna otra pantalla compone: es la superficie de Hablar, igual que `.k-stage` es la de lectura. La hoja de componentes se queda en 17 átomos y `hoja.check.mjs` no cambia.
- **Los tres puntos de «pensando» no son de la marca.** `.klara-mark` no tiene ese estado y sus Notas prohíben el `data-speaking` decorativo: los puntos son `.k-presence__think` y solo ocupan el sitio de la K mientras dura el turno. La marca **entrando** y la firma «— K» siguen pendientes, y ahora son solo de Onboarding y StoryFinish.
- **El redondo destructivo no entra.** «Terminar» es un `.k-rbtn` normal con su aspa; pierde el hover en acento y no pierde nada más. Terminar no destruye: cierra la charla, guarda las palabras y enseña el cierre.

Un ritmo en vez de dos: el anillo oscilaba a 1s hablando y a 0,7s escuchando, dos literales sin token. Converge en `--dur-breath`, el latido de la marca, y la diferencia entre escuchar y hablar la lleva el color —acento y tinta—, que es donde ya vivía. Es la misma convergencia que redujo siete `color-mix` a uno y ocho tamaños de redondo a tres.

Lo que se pierde, dicho: la caja del apunte (`--paper-2`, borde, radio) se queda en el filete de acento de `.k-note[data-state="fix"]`, que es lo que el mapa del átomo 13 mandaba; el IPA pasa de mono a `.k-note__right` —serif itálica en acento— porque es «lo correcto» y eso es lo que ese elemento significa; el `.kc-em` del titular de cierre cede al `<em>` del héroe y pierde el acento; el IPA del foco se cae del chip de la línea superior porque las versalitas se lo comían (`/yː/` → `/Yː/`) y cada apunte lo dice donde importa; `speak.controls.exit` cede a `common.exit`; el acuse de «clara» deja de ser una frase de Klara («…clara. Sigamos.») y pasa a rótulo de chip en los seis idiomas, porque un chip va en versalitas y una frase en versalitas no se lee; y los tres rótulos de cifra del cierre bajan de versalitas a minúscula, porque ahora viven en `.k-hero__meta`, que es serif itálica.

Colateral verificado: `.ds-entry.tsx` seguía exportando `RecallReviewSession`, que la migración 3 había borrado — referencia colgada, arreglada aquí.

Migración 6 (Pronunciar, lo último que quedaba en `sentence-view.css`). Es la primera migración que **no re-viste una pantalla: la borra**. La tabla de arriba la llamaba «lectura de escritorio» y no lo era: `SentenceView` era la sesión de Práctica, y desde la migración 2 su gemelo migrado —`EstudiarView`— ya hacía el mismo trabajo, con el mismo `useSentencePractice`, para la lectura. La cabecera de `EstudiarView` lo decía por escrito desde entonces: «vive aparte del legacy porque Práctica comparte aquel archivo; el legacy muere cuando Práctica se re-vista». Se re-vistió. Mueren 639 líneas de `.tsx`, las 577 de la hoja y `lib/waveform.ts`, que se quedó sin consumidor.

Como Repaso y como Hablar, el flujo sale del cascarón viejo: `/pronunciar` es la tercera superficie de sesión suelta, y Práctica se queda con lo que siempre fue —el selector de tres puertas— navegando a las dos que ya son rutas. Preparar, sesión y cierre viajan juntos porque comparten la cola, el hook y el envío de la ronda; partirlos habría sido mover estado entre rutas para no mover markup.

**Cero reglas nuevas en `sistema.css`.** Es la primera migración que no pide ninguna enmienda de composición, y no por casualidad: la sesión ya estaba migrada (átomos de la 2), el preparar y el cierre son `.k-hero--quiet` + dock (la forma que fijó la 3) y la lista de «cuándo vuelven» es `.k-live` + `.k-row k-row--quiet` (la que fijó la 5 para el cierre de Hablar). Cuando el vocabulario aguanta una pantalla entera sin tocarlo, el sistema dejó de estar en obra.

Lo que sí cerró, todo por gasto y no por decisión nueva: el **candidato 19** en su segundo consumidor (las dos píldoras de `sentence-view` —grabando con VU, evaluando con spinner— son la línea de estado del dock); el **candidato 20 entero** (las cifras del preparar y del cierre son `.k-hero__meta`, las tres filas de reprogramación son `.k-row`); la **nota cargando** (es texto que se sustituye dentro de la nota del veredicto, no un estado); y la colisión `.k-stage` de la **trampa 11**, con las tres declaraciones defensivas que vivían en `sistema.css` esperando este día.

Lo que se pierde, dicho: Práctica paga ahora lo que la lectura pagó en la migración 2 —la onda de 64 barras con cabezal y tiempos, la píldora de grabación con sus 16 barras de RMS en vivo, el panel de puntaje `/100` con su leyenda de tres conteos, el «Escuchar a Klara» del feedback y los atajos de teclado impresos en pantalla—; todo eso sigue vivo en el hook y en el teclado, y lo que se ve es la línea de estado y el veredicto. Además: la K y el nivel de la barra de capítulo ceden a la línea superior de sesión (salida · título · contador); el contador `01 / 06` en mono con su barra de pips es ahora `.k-bar--segs` con el conteo en la línea superior; los rótulos `struggled`/`review` del preparar pierden su `<em>` y se acortan a rótulo de cifra en los seis idiomas —lo que se lleva por delante los dos `dangerouslySetInnerHTML` que quedaban en esa pantalla—; y las tres cifras del cierre bajan de versalitas a minúscula, por lo mismo que en Hablar: viven en `.k-hero__meta`, que es serif itálica.

Defecto encontrado y **no** arreglado, porque es de producto: los tres chips de «EMPEZAR POR» (`Todo · 3` / `Difíciles · 2` / `Repaso · 1`) nunca filtraron nada —son `<span>` sin manejador, con el primero marcado a mano—. La migración los conserva tal cual, en `.k-chip k-chip--static`, que es el átomo que el sistema tiene para un rótulo con forma de chip; así al menos dejan de parecer tocables. Queda como decisión abierta 14.

Del arnés: dos familias de capturas cambiaban solas entre corridas y costaban una investigación por migración —el saludo de Inicio depende de la hora (`dateLabel.ts`: <12 mañana, <19 tarde) y la línea superior de Hablar pinta hora y tiempo transcurrido—. Con `page.clock.setFixedTime` las dos quedan quietas: verificado con dos corridas seguidas del mismo build, byte a byte. Es la continuación de la lección de la migración 5: antes de llamar «ruido» a un diff, mídelo; y si es el arnés, arréglalo en el arnés.

Migración 7 (el cierre de historia: quiz + resumen, `finish.css` entera). Es la hoja más grande de todas —1.021 líneas, 1.448 de `.tsx`— y la que más estados guardaba en Pendientes: cinco de los ocho que quedaban abiertos los decide esta pantalla, y los cinco se cierran con átomos que ya existían.

**La historia entera vive en un solo cascarón.** Hasta hoy leer era `.k-app` (teléfono, 100dvh, nada scrollea) y al terminar la lectura se saltaba a `kapp`/`kframe` (el cascarón viejo de escritorio, sin Masthead) con un comentario que lo llamaba «interino hasta F2.4». Ya no: `StoryFinish` pinta su propio `.k-app` y `Story.tsx` deja de escribir las dos clases viejas. El quiz es una sesión más y se compone como Repaso —línea superior, `.k-bar k-bar--segs`, ficha en la zona de sesión—; el resumen es un informe largo y su columna es `.k-live`, que sí scrollea, con el dock abajo para lo que sigue. La columna viva también envuelve la ficha del quiz: una de opción múltiple con cuatro opciones no cabe siempre en un teléfono de 667px de alto, y ese es exactamente el seguro para el que `.k-live` existe.

**Una sola regla nueva en `sistema.css`**, y no es de la pantalla sino del sistema: `.k-row > .k-btn--text { margin-inline: 0 }` (trampa 13). Todo lo demás sale del vocabulario tal cual.

Lo que cerró, con su razón:

- **Los cuatro `data-state` de la opción** (candidato de estado): la respondida dice tres cosas y las tres tenían átomo —`selected` para la buena (el canto de 3px que ya venía de `finish.css:365`), un `.k-chip--static[data-tone]` con punto y glifo para el veredicto, `locked` para las descartadas—. Lo que gana: el acierto y el fallo dejan de ser **solo** color.
- **El hueco rellenable**: es una palabra puntuada del pasaje, `good` acertada y `bad` revelada. Vacío es el `___` que `GenderPicker` ya escribía.
- **`data-played`**: antes de tocar «reproducir» no hay pasaje, hay una instrucción — y una instrucción es una `.k-note`.
- **`data-struggled`**: chip estático con punto, como mandaba el mapa del átomo 4.
- **La firma «— K»**: `.k-note k-note--bare` con la marca de verdad, el mismo pie que Repaso usa desde la migración 3. La «K» de texto del héroe (`.fin-hero__k`) pasa también a `<KlaraMark>`.
- **La animación de entrada de la ficha**: no entra. El cambio de pregunta ya lo dicen la barra y el contador, y donde hay pasaje `page-in` lo anima al remontar.
- **El candidato 19 (píldora de proceso), completo**: era el último consumidor. Grabando y evaluando son una `.k-cap` con el rótulo vivo en `.k-cap__count[data-tone="live"]`, aquí en el pie de la ficha porque en el quiz el pie de la ficha ES el dock. Con las 16 barras de VU muere `lib/audioBars.ts`.
- **El esqueleto del candidato 22**: los dos de `finish` eran los únicos; pasan a una `.k-note` con la copia de carga, igual que la «nota cargando» de la migración 6.

Lo que se pierde, dicho: el sello de 3px sobre la ficha (regla 5); el círculo de la insignia de letra, que se queda en `.k-row__n` sin caja; la píldora de 999px del micrófono y del «grabando», que bajan a `.k-btn` con `--r-sm`; el lavado verde/bermellón que teñía la opción entera, que ahora vive concentrado en el punto del chip; las dos columnas del resumen (`1.4fr 1fr`), que en 430px se apilan y no eran nada más que eso; los 80px del titular del resumen y los 56 de la línea recordada, que bajan al techo del `clamp`; y el `.fin-back-row` con sus dos salidas, que pasa a la línea superior de sesión más un `.k-btn--text` en el dock.

Colateral: `GenderPicker` lo usan dos pantallas —el quiz y la sesión de género, que aún no migra—, así que sus acciones se quedan en el pie de la ficha y su respuesta se escribe con `.k-card__answer` + `.k-card__article` en vez de `.k-stage`, que va acotado a `.k-app` y allí no hay ninguno. De paso `GenderReviewSession` deja de pintar `.fin-btn`.

Del arnés, la segunda mitad de la lección de la migración 6: **el reloj fijo no congela las animaciones CSS**, que van con el reloj del compositor. `hablar-apunte` seguía dando bytes distintos entre dos corridas del mismo build —las 44 varillas del anillo de presencia, cada una con su retardo—. Con `screenshot({ animations: "disabled" })` las finitas se sientan en su fotograma final y las infinitas en el primero, que en este sistema es el de reposo. Verificado: dos corridas seguidas, 52 capturas, cero inestables.

Migración 8 (Onboarding, `onboarding.css` entera). La segunda hoja más grande y la única pantalla que todavía se diseñaba para una ventana de escritorio.

**El onboarding era una rejilla de tres columnas que ningún teléfono vio nunca.** `.ob__main` repartía 200px de numeral romano, el contenido y 280px de marginalia de Klara… y `@media (max-width: 860px)` escondía las dos columnas laterales. O sea: el numeral y los susurros existían solo para quien entrara desde un portátil. La migración los conserva pero los baja al sitio donde se leen siempre: el capítulo pasa a la línea superior (`02/05`) y a la barra de segmentos, y el susurro cierra la columna como la `.k-note` que el mapa del átomo 13 ya prescribía. La ruta sale además de `LegacyShell` —`.k-app` a 100dvh no se anida en `.kframe`, la cuarta vez que pasa— y de paso deja de asomar el Masthead de la app a quien todavía no ha entrado en ella.

Dos reglas nuevas en `sistema.css`, las dos del sistema y no de la pantalla:

- `.k-field + .k-field { margin-top: 18px }` — dos campos seguidos son la forma normal de un formulario y el átomo no trae margen: se tocaban. 18px es el hueco vivo de `.ob-pass__fields`, que muere. Auth lo va a necesitar igual.
- `.k-topline--session:has(> .k-topline__mark)` y `:has(> .k-chip)` pasan a `1fr auto 1fr` — la trampa 14: con el contador vacío, la marca quedaba 19,7px descolgada. El arreglo alcanza también al chip de foco de Hablar, que estaba descentrado desde la migración 5 y nadie lo había medido. Son las cuatro únicas capturas que cambian fuera del onboarding, y el diff es exactamente la fila del chip.

Lo que cierra: el **candidato 18** en su consumidor del onboarding —el menú anclado a una palabra es, en 430px, la hoja inferior de siempre, y el ancla la dice el fondo de «de esta estamos hablando» sobre la propia palabra—; el **candidato 21** entero (si `.k-hero--quiet` + `__dek` + `.k-hairline` cubren el encabezado en cinco pantallas sin una regla nueva, el encabezado no es un átomo, es una composición); la **marca entrando** y la **coreografía escalonada del héroe**, o sea las seis animaciones en ms literales del onboarding, que morían contra §7.6 y no decían nada que el contador y la barra no digan ya.

La frase que se rellena sobrevive, y es lo mejor de la pantalla: «Hablo **Español ▾** y quiero aprender **Deutsch ▾**» es un `.k-stage` con dos `.k-word[data-matched]`. El «▾» es la afordancia —sin `:hover` no hay otra manera de decir que se toca— y el desplegable es `.k-sheet`. Defecto encontrado midiendo: la hoja no puede vivir **dentro** del `<p class="k-stage">`, porque el pasaje es `display: -webkit-box` para recortar a siete líneas y ahí dentro cada hijo se vuelve un ítem vertical: la frase salía partida en pedazos. La hoja pasa a ser hermana del pasaje y el disparador se queda con la palabra.

Lo que se pierde, dicho: los 112px de «Hola.» y los 64 del «Bienvenido» bajan al techo de 40px del `clamp` (regla de §3.1: ningún átomo se apoya en `--t-display`); el numeral romano de capítulo se convierte en cifra; el menú anclado con su `min-width: 220px` y su sombra se convierte en hoja; la caja del área de contexto conserva el serif pero pierde su radio propio; y el `<form>` de la pantalla del nombre muere —no puede envolver `.k-fill` y `.k-dock`, que son hermanos—, así que Enter lo recoge el propio campo.

Del arnés: el escáner de culpables de desbordamiento tiene que **saltarse los subárboles fuera de flujo**. La hoja inferior se posiciona contra `.k-app` y por eso sale de la caja de `.k-live` a propósito; sin ese filtro delataba seis falsos culpables mientras `scrollWidth - clientWidth` decía cero. Es la contrapartida de la lección de la migración 7: medir por contenedor de scroll, pero solo lo que de verdad está en ese flujo.

Migración 9 (Auth: `Login`, `Signup`, `ForgotPassword`, `ResetPassword`, `VerifyEmail`, `auth.css` entera). La hoja más pequeña de las diez, y la que llegó medio hecha: el átomo 17 nació leyéndola.

**Casi no hubo nada que inventar, y ese era el examen.** Las cinco pantallas son encabezado + campos + acciones + un enlace al pie, o sea el candidato 21 puesto en fila (`.k-hero--quiet` + `__dek` + `.k-hairline`), `.k-field` con su rótulo, `.k-wrap` y `.k-topline--foot`. `.auth-title`, `.auth-sub`, `.auth-form`, `.auth-label`, `.auth-input`, `.auth-links` y `.auth-page` mueren sin sustituto propio: siete clases, cero átomos nuevos. La única cirugía real fue el cascarón: `.auth-page` existía solo para volver a encender el scroll que `.k-app > .k-page` apaga, y eso ya tiene nombre —la columna que scrollea es `.k-live`—, así que cada pantalla lo pinta y la línea superior con la marca se queda quieta arriba, que es lo que la tira promete desde la migración 1.

**`.k-topline--foot` deja de ser una variante escrita y sin usar.** Estaba en la hoja desde el contrato, con su filete arriba, su tinta un paso más apagada y —lo importante— el `min-height: 44px` que el mapa del átomo 2 exige para `.auth-links a`. Cero consumidores en `.tsx` hasta hoy. Las cinco pantallas la estrenan, y con ella se descubrió lo que le faltaba: el aire sobre el filete, que es del pie y no de quien lo precede (`margin-top: var(--space-5)`).

Dos reglas nuevas en `sistema.css`, las dos juntas y ninguna de pantalla:

- `:where(.k-field) ~ :where(.k-wrap) { margin-top: var(--space-5) }` — la fila de acciones que cierra un formulario. Hermano **general** y no adyacente porque entre el campo y los botones puede colarse un `.k-error` (la portada lo mete dentro del `<form>`). El valor **no** es el 16px portado: ver trampa 16.
- `.k-topline--foot { margin-top: var(--space-5) }` — arriba.

Colateral medido, y aceptado: la primera regla alcanza al taller, que es la misma forma (el área de pegar tarjetas y su «añadir»). Son las dos únicas capturas que cambian fuera de auth, el diff es exactamente ese hueco, y es el sistema haciendo su trabajo — dos pantallas que hacen lo mismo dejan de decidirlo por separado. La portada cambia también, pero por dentro: su formulario de lista de espera es hoy `.k-field` + `.k-wrap`, aunque `landing.css` siga viva para todo lo demás.

**Enmienda contra el propio contrato**, la primera de la serie: el mapa mandaba `.auth-input` → `.k-field--rule`, y el comentario que justifica `--rule` dentro del átomo dice que es para respuestas y **no** para datos de formulario. Ganó la doctrina. Con la caja, la contraseña de `/signup` y la del capítulo V del onboarding —literalmente el mismo acto— dejan de verse distintas, y `--rule` se queda con el único consumidor que su propia frase describe: el nombre propio.

Cierra además el `:disabled` del átomo 17, que era estado escrito y nunca pintado: el correo de una invitación llega precargado y bloqueado, y hasta hoy se veía igual que uno editable.

Del arnés, dos: la trampa 15 (los `.js` fantasma, que hicieron que la primera corrida de la sonda midiera el árbol viejo) obligó a rehacer la línea base entera desde `HEAD` en vez de fiarse de las capturas guardadas; y a la sonda hubo que añadirle un caso a 480px de alto, porque las cinco pantallas caben en 844 **y en 667**, así que sin él el scroll de `.k-live` no se ejercitaba en ninguna. A 480 la columna scrollea 124px y el cascarón no crece: es lo único que prueba que «crear cuenta» sigue siendo alcanzable en el teléfono más bajo.

Migración 10 (Landing, `landing.css` entera). La primera pantalla que **no** es la app: su cartel. Y la única que trajo dos preguntas de identidad en vez de una de traducción.

**La portada tenía dos niveles de titular y el sistema tiene uno.** El tagline iba a `--t-h1` (56px, 40 en el teléfono porque `pages.css:692` redefine el token) y los cuatro rótulos de sección a `--t-h3` (28px): una jerarquía de 1,43 medida. El mapa del contrato mandaba los dos a `.k-hero--quiet`, o sea los dos al mismo `clamp(28px, 8vw, 40px)` — 31,2px cada uno en 390px de ancho, con el rótulo de sección **subiendo** y el titular **bajando** hasta igualarse. La portada se quedaba sin titular. La salida no fue un tamaño nuevo (el sistema ya mató 112, 80, 64 y 52px de titulares; resucitar un quinto para una pantalla es justo lo que la doctrina prohíbe) sino reconocer qué son las otras cuatro piezas: **secciones**. Y las secciones de Klara se encabezan con `.k-cap`, en la biblioteca, en el taller, en Práctica y en el mapa. La portada deja de ser la excepción, y de paso se lee como la pantalla que promete.

**El segundo hallazgo es que a la portada le falta un registro que el sistema no tiene.** `.landing__bloque p` y `.landing__wl-body` son prosa: serif recto de 17px que no es contenido alemán, ni marginalia mono, ni la voz de Klara al margen. El sistema se derivó de las pantallas de dentro, donde todo el texto es una de esas tres cosas, así que no hay párrafo de cuerpo. La prosa de la puerta entra en `.k-note k-note--bare`, el registro que más se le parece — y con eso la portada queda entera en itálica bajo un titular recto. Que es también lo que resuelve la tercera enmienda: **el tagline no conserva la itálica** que el mapa le prometía. No se pierde, se muda del titular al cuerpo. El titular no es Klara hablando; es el cartel.

Cinco reglas nuevas en `sistema.css`, ninguna de pantalla: tres juntas entre átomos que no se habían encontrado nunca (`.k-hero + .k-wrap` a 16px, `.k-cap + .k-note` a 0 y `.k-note + form` a 16px), el inset de abajo del `.k-page` que es último hijo, y el suelo táctil del `.k-link` de la tira. Son más que en cualquier migración anterior por una razón de forma: la portada apila verticalmente más piezas distintas que ninguna pantalla de la app —titular, botón, cuatro secciones, formulario y pie—, y cada apilamiento nuevo es una junta que nadie había medido.

**La portada entra en el cascarón, y con eso el sistema se queda con un solo contenedor que pone el inset de arriba.** `landing.css:1` decía «scrollea (no vive en el cascarón)», y era verdad: 430px de ancho pero alto libre y scroll de documento. Lo que hace que quepa es que el scroll ya tiene nombre desde la migración 5 —`.k-live`, la columna que sí scrollea— y que auth lo estrenó fuera de una sesión en la 9. Así que la puerta entera, portada y login, cuelga hoy de `.k-app > .k-page`, la tira de la marca se queda quieta arriba y la columna scrollea debajo. El inset de abajo pedía la regla nueva, y esa regla **cierra además un hueco que dejó la migración 9**: las cinco pantallas de auth tampoco lo llevaban, y en el caso de 480px de alto —el que la sonda de auth añadió para ejercitar el scroll— el botón de «crear cuenta» acaba justo contra la barra de gestos.

Colateral medido, y beneficioso: la junta del átomo 6 alcanza al **cierre de historia**, donde «una cosa a notar» y «trampas de género» tenían su nota descolgada 18px del rótulo. Bajan a 2 y los 32px liberados hacen entrar dos líneas más de contenido. Es la misma forma —rótulo de sección y su párrafo— resuelta por fin en un solo sitio.

Lo que se pierde, dicho: los 56px del tagline y su itálica; los 28px del serif itálico de los cuatro rótulos, que bajan a mono de 11px en versalitas; el filete completo sobre cada sección, que pasa a continuar a la derecha del rótulo (`--rule`); los 17px rectos de la prosa, que bajan a 15 itálicos; los 12px del «¿ya tienes cuenta?», que suben a versalitas mono; y los 40px de aire bajo el pie, que pasan a los 14 de la página más el inset. `--t-h1` se queda sin su consumidor de la portada pero sigue vivo en `pages.css` (seis usos): no queda huérfano todavía.

Del arnés, dos lecciones y las dos nuevas: la **trampa 17** (un suelo en `:where()` no pisa un margen que el átomo declara) hizo que la primera versión de la junta `.k-cap + .k-note` no hiciera nada, y solo la delató la medida; y la **trampa 18** (`fullPage` no ve bajo el pliegue con scroll interno) explicaba por qué el diff de 66 capturas salía verde en el cierre mientras la regla sí lo cambiaba. Con la ruta `cierre-apuntes` añadida —scrollea a la pieza antes de disparar— el colateral se ve en vez de suponerse. La sonda de la portada (`probe-landing.mjs`, 14 escenarios) mide además el ancla del CTA, que con el scroll dentro de un div tenía que seguir llevando a la lista de espera, y lo hace.

Migración 11 (Perfil de aprendizaje: `perfil/views.tsx`, y con ella **muere `perfil-aprendizaje.css`**). La otra mitad del onboarding. La hoja lo decía en su segunda línea —«Del paquete de diseño Onboarding v5, integrado sin retoques»— y nadie lo había leído como lo que era: el mismo cuestionario que la migración 8 ya había pasado, viviendo en otro cascarón y en otro dialecto. Así que esta migración no inventa la forma, la copia de `ObStep`/`ObNav`: línea superior de sesión, barra de segmentos, columna que scrollea y una nube de transporte al pie. **Cero átomos nuevos, una variante y seis reglas.**

**La pregunta cuelga del cascarón; la entrada y la síntesis, no.** El cuestionario vive dentro de `V4Frame`, o sea con barra de pestañas, y ahí está bien: es el único sitio desde el que se sale de la pantalla de entrada cuando ya hay perfil guardado (`views.tsx:75` esconde «más tarde» en la reentrada). Pero su tira es la de una sesión —salir · bloque · contador—, y `--session` trae su propio relleno con inset porque cuelga de `.k-app` sin página de por medio. Dentro de `.k-page` eso sumaba el inset dos veces. La salida no fue partir la variante, sino mirar dónde va cada pieza: la tira y la barra pasan a colgar de `.k-app` (fragmento, como `ObStep`) y la página empieza debajo. Con eso **el inset de arriba se escribe con `:first-child`**, simétrico al `:last-child` que la 10 puso abajo, y el sistema queda diciendo lo mismo por los dos cantos: el inset lo pone quien toca el borde. Hasta hoy toda `.k-page` era la primera hija y la regla acertaba por descarte.

**Cuatro pendientes que este contrato dejaba a esta migración, decididos, y no todos igual.** Entran dos: la **fila «al lado»** (`.k-row--aside`) —las dos que había, negativa y «otra cosa», pintaban lo mismo y dicen lo mismo, así que son un nombre solo, y la itálica que usan es la que el sistema ya tiene para «esto está al lado del contenido»— y el **segmento saltado**, que es información: una pregunta en blanco no es una pregunta por responder, y sin él la barra miente. No entran: los **grupos con peso** de la barra (el bloque en el que vas lo dice el título de la tira, que es donde vive la orientación), el **chip cuadrado**, el **seleccionado negativo** (papel apagado y tinta baja se leía como *deshabilitado*, no como *elegido*) y la **regla punteada de procedencia**.

**La punteada es la que mejor sale.** La síntesis separa lo que Klara observó de lo que tú dices de ti, y la hoja vieja lo dibujaba con un filete discontinuo más una leyenda que lo explicaba. Pero la leyenda dice, literalmente, «Arriba, lo que hiciste. **Al margen**, lo que dices de ti» — o sea que la copia ya describía la distinción del sistema, no la de la hoja: lo observado va a plomo (`--bare`) y lo tuyo va al margen, con el filete de la nota, que es exactamente como Hablar atribuye tus turnos (`.k-live__turn[data-who="you"]`). Cero reglas nuevas, y de paso la leyenda pierde el filete que llevaba: explica el margen, no está en él.

**El triaje pierde su encabezado de columnas y gana claridad.** Los dos botones cuadrados de 46px pasan a chips, y los chips llevan «Sirve» y «No» escritos en vez de ✓ y ✕ bajo una fila de rótulos que ninguna disposición flexible puede alinear. Mueren `.ob5-trihead` y el tinte de `[data-set]` —que la fila está contestada lo dice el chip lleno— y no muere ninguna clave de i18n: las dos que rotulaban las columnas son ahora el texto de los chips.

Seis reglas nuevas en `sistema.css`, ninguna de pantalla: `.k-app > .k-page:first-child` (el inset de arriba), `.k-cap + .k-hero` (la hermana de `.k-cap + .k-note`, y con ella la cinta cumple por fin lo que promete sea nota o titular lo que la siga), `:where(.k-page) > :where(.k-wrap)` (la fila de acciones que cierra una página: hasta hoy todas vivían en un dock o dentro de un `<form>`), `:where(.k-wrap) + :where(.k-field)` (la tercera de la familia del campo: la nube de etiquetas y el escape a texto), `.k-page > .k-wrap > .k-btn--text { margin-block: 0 }` y la variante `.k-row--aside`. La quinta es la hermana vertical de `.k-row > .k-btn--text`: el voladizo de 12px del control en mono no cabe en los 10px de relleno inferior de una página comprimida y el área táctil se recortaba 2px contra el `overflow: hidden` del cascarón — **lo dijo la sonda, no la captura, porque lo que se sale es el área y no el rótulo**.

**Defecto del sistema encontrado por accidente y arreglado:** el `:hover` del chip le ganaba en especificidad a `[data-selected]` y le ponía tinta sobre tinta, o sea que un chip pulsado desaparecía bajo el cursor. Llevaba ahí desde la hoja de componentes y no lo veía nadie: no hay hover en el teléfono, el arnés no deja el puntero encima y `hoja.check` mide estados declarados, no combinaciones. Lo enseñó una captura de la sonda tomada justo después de un clic. Es la **trampa 19**; la **20** es su gemela de especificidad, la reposición del inset dentro de `@media` que dejó de aplicar al añadir `:first-child`.

Lo que se pierde, dicho: los 38px del titular de entrada y los 27 de la pregunta, que convergen en el titular único (`clamp(28px, 8vw, 40px)`); los 17px rectos de la bajada, que pasan a 14 en itálica; las tres cifras apiladas del pie de entrada, que pasan a la cifra del héroe en una línea (candidato 20); los 18px rectos de la prosa de síntesis, que bajan a 15 en itálica, que es la voz de Klara; la columna fija de 92px de las claves del ledger, que pasa a medirse por contenido (el átomo 4 lo decidió así a propósito: «die» y «Nivel objetivo» no caben en un fijo); el centrado vertical de las opciones dentro de su hueco; el ✓ dibujado dentro de la marca de la fila, que pasa a ser el cuadro lleno; los tres filetes que separaban entrada, pie y acciones; y el `outline: none` con que `.ob5-otra` degradaba su foco — el campo recupera el anillo del sistema, que es accesible y **se ve**: es la misma decisión 4 (`--focus` = acento) que sigue abierta, ahora con un consumidor más.

Migración 12 (Género: `components/GenderReviewSession.tsx`, y con ella **muere `gender-review.css`**). La hoja más pequeña de todas —58 líneas, cinco fases— y la única que se importaba desde un componente en vez de desde `main.tsx`. **Cero átomos nuevos y dos reglas**, las dos de sitio y no de pantalla.

**Enmienda contra el propio mapa, la cuarta de la serie: `.gr__head` → `.k-topline` a secas, no `--session`.** La variante de sesión son dos ideas en una: la rejilla de tres pistas (salir · título · contador) y el relleno con inset de una tira que cuelga del cascarón sin página de por medio. La cabecera de género no tiene salida que colocar en la tercera pista y vive dentro de una página que ya trae relleno; y es, declaración por declaración, el bloque base: `flex`, `space-between`, `baseline`. El mapa se escribió leyendo la hoja, donde las dos cabeceras se parecen; ejecutándola, la diferencia es dónde vive cada una.

**El título cambia de registro entre fases, y eso es lo que el mapa sí acertó.** Durante la sesión es orientación —`.k-topline__title`, mono en versalitas, junto al contador— porque lo que hay que leer es la ficha; en las otras cuatro fases la pantalla es solo el título y su frase, así que es titular (`.k-hero k-hero--quiet` + `__title`). Es exactamente lo que hacen Lectura, Repaso y el cierre: **cuando la pantalla ES una ficha, el titular sobra**.

**El vacío y el fallo comparten forma y no comparten tono**, que es la doctrina que fijó Repaso: no tener géneros que repasar hoy es una nota (`.k-note`), y no poder cargarlos es un error (`.k-error`, con `role="alert"`). El mapa mandaba `--mono` al vacío; la doctrina no, y el vacío de género es una frase de Klara, no un metadato. Y la carga deja de ser el título repetido en versalitas en mitad de la pantalla: es el `.k-spinner` suelto que sus tres vecinas del mismo cascarón ya usan, con el rótulo en el `aria-label` — **una pantalla que está cargando no tiene texto que leer**.

Dos reglas nuevas, las dos del armazón y las dos por el mismo motivo —esta pantalla es la primera que pone piezas sueltas en una página, sin dock, sin formulario y sin `.k-fill` que las centre—: `:where(.k-hero) + :where(.k-error)` (la tercera junta del par del titular, y la que faltaba: `.k-error` es el único átomo de bloque que no trae aire ninguno, porque nació dentro de un formulario) y `:where(.k-page) > :where(.k-card)` (la ficha suelta bajo una tira). La segunda la pidió la sonda: sin ella la ficha se pegaba a la cabecera, donde `.gr__head` traía 20px.

**Y de paso, la trampa 15 deja de existir.** Al borrar la hoja apareció un `GenderReviewSession.js` compilado tapando al `.tsx` — y con él otros 107. La causa no era «algún `tsc` suelto»: es el gate, `npm run build` = `tsc -b && vite build`, y `tsc -b` emite. Cada verificación de cada migración volvía a sembrarlos. Una línea en `tsconfig.json` (`"noEmit": true`) lo cierra, y `npm run build` sigue produciendo `dist/` y deja cero `.js` bajo `src`.

Lo que se pierde, dicho: el ancho máximo de 36rem de `.gr` —la pantalla pasa a medir lo que miden sus vecinas del mismo cascarón, o sea el ancho de `.k-page`, con la ficha topada en sus 560px—; los 20px de serif del título de sesión, que bajan a los 11 en mono de la tira; los 17px de la frase de vacío, que bajan a 15; el `2rem 1.25rem` de relleno propio, que pasa al de la página; y la fase de carga, que deja de decir el título para decir que carga.

Migración 13 (el mapa de curso: `routes/Module.tsx`, y con ella **muere `path.css`**). **Cero átomos nuevos y cuatro reglas**, tres de sitio y una de arreglo — la del arreglo no es de esta pantalla, es de las 22 anteriores.

**Lo primero que dijo la hoja es que ya estaba casi toda muerta.** El contrato la anunciaba como «la implementación más completa de los átomos 4 y 5, con la fila de cinco estados y la barra dual», y lo era: pero `.path__node`, `.path__bar` y sus doce hermanas **no tenían un solo consumidor en el árbol**. 62 de sus 87 líneas eran el camino del curso que `.k-row` y `.k-bar` ya habían sustituido en migraciones anteriores; la hoja seguía cargándose entera para sostener `.path__kicker` (un uso) y el bloque `.mod__*`. Leerlas antes de borrarlas era lo que el contrato pedía, y confirmó lo que se quería confirmar: los cinco estados de fila del átomo 4 salieron de aquí y no hizo falta cambiar ninguno.

**El nivel entra en la ranura del rótulo, y ahí está la única decisión de forma.** El héroe tiene un `__tag` —tira mono en versalitas— para lo que va encima del titular, y esta pantalla ya traía ahí un `.k-level`, que es el átomo 7. Dos átomos para el mismo sitio. Gana la insignia, porque cuando la pantalla **tiene** nivel el nivel ES el rótulo, y el sistema ya sabe dibujarlo; lo que se escribe es dónde se coloca (`.k-hero > .k-level`, una regla de rejilla). Anidarla dentro del `__tag` no valía: la tira lleva `opacity: .6` y la insignia trae su propio contraste, así que la lavaba.

**Las cifras y la prosa se separan, y cada mitad va donde ya se decidió que fuera.** Las tres cuentas (historias, palabras dominadas, géneros) son `.k-hero__meta`, que es lo que el candidato 20 cerró en la migración 6; los dos hechos con rótulo —qué vas a poder hacer, qué gramática— son una `.k-note` con dos `.k-note__body` y el rótulo en `.k-note__cap` inline, que es el precedente de `.ob5-fact` de la 11. **Sin `<strong>` en las cifras, y eso es una observación, no un descuido:** el `__meta` destaca la cifra cuando la cifra es una pieza aparte de su rótulo, y aquí las seis claves de i18n son frases enteras con el número interpolado dentro («3 de 5 historias completadas»). Partirlas en los seis idiomas para poder poner un `<strong>` es trabajo de copia, no de sistema.

**La sonda encontró un defecto que no era de esta pantalla sino de las 22 anteriores** (trampa 21): el bloque de compresión le devolvía a `.k-hero--quiet` el relleno que su variante apaga, en todo teléfono de ≤720px de alto. 31 héroes apagados en 22 ficheros llevaban meses saliendo con 12px arriba y 16 a los lados de más en los teléfonos bajos. No lo veía nada: el arnés de rutas fotografía a 844px de alto, `hoja.check` mira la hoja de componentes y el rectángulo del héroe **no se mueve** —un `--quiet` no tiene fondo—, así que lo único que delata el relleno es dónde empieza un hijo. Se arregla acotando la reposición a `.k-hero:not(.k-hero--quiet)`.

Lo que se pierde, dicho: los 26px de serif del título de módulo, que suben a los 28-40 del clamp del héroe; los tres `.mod__fact k-mono` de 12px, que pasan a serif itálica de 17 en el `__meta` —el mismo cambio de registro que hicieron la 6 y la 7 con las cifras de cierre—; el `gap: 10px` propio de la fila de acciones, que pasa a los 8 de `.k-wrap`; y el `:hover { color: var(--accent) }` de la fila de historia, que cede al fondo `--paper-2` del átomo 4, que es el gesto único del sistema.

Migración 14 (los dos popovers de palabra: `components/WordPopover.tsx` y `BreakdownPopover.tsx`, y con ellos **el bloque `wpop*` entero fuera de `pages.css`**, que baja de 705 a 587 líneas). **Cero átomos nuevos y siete reglas**, de las cuales cinco existen para resolver un problema que la hoja vieja nunca había resuelto.

**Cierra el candidato 18, y la respuesta es que no hace falta un átomo.** Los dos globos son `.k-card k-card--flat k-card--anchored` sin una sola clase propia. Lo único que la variante tuvo que aprender es su **métrica**: los 26/22 de relleno y los 16 de hueco de la ficha plana están pensados para una ficha que ES la pantalla, y encima de un pasaje que se está leyendo esa misma caja tapa el texto que el globo viene a explicar. Dos declaraciones —`padding: var(--space-4)`, `gap: var(--space-3)`— y `--anchored` deja de decir solo «dónde flota» para decir también «cuánto ocupa». Un átomo nuevo habría sido la misma superficie con otro nombre.

**Lo que sí cambia de registro es la palabra.** El lema sube de 22px a los 30 del clamp del átomo (`9cqw` sobre un globo de 320), porque la palabra es la razón por la que el globo existe y en el sistema una palabra de ficha se compone como palabra de ficha. Y el artículo pasa de un mono de 12px teñido desde JavaScript —`WordPopover.tsx:16-20` llevaba tres `oklch` literales en un objeto y un `style={{color}}` para aplicarlos— al `.k-card__article[data-gender]` de 24px en serif itálica, que es el mismo que la ficha de repaso.

**Y de ahí sale el trabajo de verdad de esta migración, que no estaba en el mapa.** El globo del sistema mide 320px fijos y trae dos botones de 44px (§7.2), así que es más alto que el viejo: 304px contra unos 190. Al medirlo aparecieron **dos recortes**, y el segundo es culpa de esta migración:

- **Por los lados, y venía de antes.** El globo se centra sobre la palabra con `translateX(-50%)`, así que una palabra a menos de 160px de un canto dejaba medio globo fuera del cascarón — que es `overflow: hidden`, o sea recortado y sin scroll que lo rescate. Se midieron **68px perdidos por la izquierda**. Nadie lo había medido nunca porque el arnés de rutas fotografía una sola palabra, y esa cae en el medio.
- **Por arriba, y es nueva.** Con 304px de alto, una palabra del primer renglón del pasaje se quedaba con la cabecera del globo fuera de la pantalla: el artículo, el lema y el botón de audio, o sea justo lo que se fue a mirar.

La salida son cinco reglas y un `useLayoutEffect`, y lo que las une es que **el globo se mueve y la cola se queda apuntando**: la caja se acota a la pantalla y `--k-tail-x` desplaza el rombo lo mismo en sentido contrario; si encima no cabe, el globo baja y la cola sube (`[data-abajo]`); y si no cabe a ningún lado —el compuesto alemán de tres renglones— se va al lado con más sitio y scrollea por dentro (`[data-scroll]`, con el tope de alto puesto en línea). Lo que se mueve es el globo, nunca lo que señala.

Lo que se pierde, dicho: el disco de tinta de 28px con su triángulo dibujado a base de bordes CSS, que pasa al contorno de 44 con el glifo de trazo 1.5 que la lectura ya usa dos centímetros más abajo; el filete discontinuo que separaba el ejemplo, que pasa al `.k-card__rule` sólido; los 22px del lema, que suben a 30; y el `min-width: 240px` del globo viejo, que deja de hacer falta porque el ancho ya no depende del contenido.

Migración 15 (Práctica, Ajustes y Nuevo relato — `routes/Practice.tsx`, `Settings.tsx`, `NewStory.tsx`, y con ellas `components/InvitationsPanel.tsx`, `OwnerPasswordGate.tsx`, `PasswordSetForm.tsx` y `ProtectedRoute.tsx`). **Muere `pages.css`, y con ella el último dialecto de pantalla.** Cero átomos nuevos y tres reglas, las tres juntas.

**De las 587 líneas que quedaban, 382 estaban muertas** —`home*`, `story-end*`, `story__new*`, `ph*`, `.placeholder`, `.story`: cero consumidores en todo el árbol—. Es la misma historia que `path.css` en la 13: una hoja se queda de pie sosteniendo una minoría de sus reglas mucho después de que el resto haya muerto, y nadie lo nota porque borrar CSS muerto no arregla nada visible. Lo vivo eran cinco familias en ocho ficheros.

**Tres candidatos cerrados de una vez, y ninguno necesitó un átomo.** El **21** (encabezado de pantalla) gastó sus cuatro últimos consumidores: seis pantallas más con `.k-hero k-hero--quiet`, y aguantó. El **22** (carga de pantalla) gastó los dos últimos con el `.k-spinner` suelto: cuatro migraciones seguidas llegaron a la misma respuesta sin ponerse de acuerdo. Y el **deslizador CEFR** resultó no ser un control que haya que diseñar: elegir uno de seis rótulos cortos es una nube de chips con `role="radio"`, que es lo que el sistema ya tenía. Mueren con él los dos `::-webkit-slider-thumb` / `::-moz-range-thumb` —la única pieza de la app pintada con pseudo-elementos de proveedor— y el control sube de un pulgar de 18px a seis objetivos de 44.

**El encabezado de SECCIÓN es lo único que esta pantalla trajo nuevo, y se resolvió sin registro nuevo.** Ajustes tiene tres secciones dentro de una página —Cuenta, Invitaciones, Seguridad— y el sistema tiene un solo nivel de titular, que ya lo gasta la página. Lo que encabeza una sección es la cinta del átomo 6 con su filete (`.k-cap k-cap--rule`), y el rótulo de lo que se va a hacer ahí es el `.k-note__cap` de su propia nota. Es exactamente la salida que la 13 dio a los hechos del módulo.

**El panel de invitaciones llevaba el sistema escrito a mano en `style={{}}`:** `border: 1px solid var(--ink-3)`, `borderRadius: 4`, `padding: .75rem` y `opacity: .6` para lo revocado. Eso es `.k-row k-row--boxed` con `data-state="locked"`, letra por letra. La única regla que hizo falta es `.k-row > .k-wrap`: una fila puede llevar su propia fila de acciones al pie, y sin `order: 2` los botones se metían en el primer renglón, entre el correo y su estado.

**Y la sonda encontró una pantalla que nunca se había estilado.** `PasswordSetForm` escribe `pw-set-form` y `pw-set-form__field`, y **esas clases no existen en ningún `.css` del repo**: sus dos campos de contraseña eran `<input>` desnudos de 224 × 32px y su enviar un `.k-link` de 149 × 28. Tres controles bajo el mínimo de §7.2 en la puerta que bloquea al owner. No era una decisión pendiente —era una pantalla sin migrar— y con ella se gasta el tercero de la decisión 17.

Lo que se pierde, dicho: el deslizador CEFR con su pista de 2px y su pulgar redondo; el `transition: transform` del `:hover` de `.home__feature` y compañía, que ya no tenían consumidor; los 26px de serif del campo de tema de Nuevo relato, que bajan a los 19 de `--rule`; el `border-top` que separaba la firma de Klara, que pasa al filete al margen de `.k-note`; y la caja del panel de invitaciones, que pasa de `--ink-3` a `--rule` porque es lo que el átomo 4 pinta.

## Decisiones abiertas para el dueño (tras la revisión visual)

La hoja renderizada pasó por tres lentes (fidelidad al contrato, roto/legibilidad, disciplina visual). Los defectos se corrigieron; estas son las opiniones que el orquestador **no** ejecutó porque son juicio de identidad, no de implementación. Cada una con su evidencia; ninguna bloquea el uso del sistema.

1. **Seis matices en circulación.** Acento bermellón, verde de acierto (`--score-good`), ámbar de regular, y los tres géneros `--art-der` (azul), `--art-die` (carmesí) y `--art-das` (verde). Dos rojos y dos verdes con significados distintos: a 11px «die» se confunde con «mal/ahora» y el verde de «das» con el de «bien». Opciones: que el género deje de ser color y sea posición (siempre en la columna del numeral, sin tinta), o alejar `--art-die` del acento en tono. Los seis valores ya existían; la hoja es lo primero que los pone lado a lado.
2. **`--focus` es el acento.** El anillo de foco y el borde de error de un campo son el mismo bermellón: un campo enfocado parece un campo mal rellenado (`card-campo-texto-light.png`, figures foco y error). Si el acento se reserva a pérdida o fallo, el foco pediría `--focus: var(--ink)`. Es un valor de `tokens.css` (§3.1). Nota: la revisión añadió `--focus: var(--accent)` al tema oscuro, que faltaba y dejaba el anillo en el bermellón claro sobre papel oscuro.
3. **`--score-bad` = acento** (objeción 4 de abajo, sigue abierta): «Klara te habla» y «lo dijiste mal» son el mismo color.
4. **El velo de la hoja inferior.** `--scrim` claro (0,35) deja el pasaje del fondo completamente legible; el oscuro (0,5) lo borra. Igualar la jerarquía en los dos temas (≈0,5 / ≈0,42) es tocar `tokens.css`.
5. **`:disabled` por opacidad.** El 0,45 unificado deja el rótulo de un botón sólido deshabilitado en ~1,7:1. Es lo habitual (los controles inactivos están exentos del mínimo) y es una sola regla; la alternativa es pintar el deshabilitado con tokens (`--paper-3` / `--ink-4` / `--rule`) átomo por átomo.
6. **El halo de la marca es una elipse**, no un círculo: `inset: -10%` sobre la caja alta y estrecha de la K. Cambiarlo toca §3.4.
7. **La pista del campo en serif itálica** quedó como cuarta excepción del reparto tipográfico (gramática 9d): es la voz de la nota al margen. Si se prefiere mono, es un cambio de una línea.
8. **El chip es la única píldora** y a 44px de alto es también la forma más iOS de la hoja. Se conserva porque el brief la exceptúa explícitamente.

**De la migración 2 (lectura).** La revisión de la sesión dejó tres opiniones más, ninguna bloqueante:

9. **La glosa perdió el paso de página.** En `mobile3.css:30` la traducción entraba con el mismo `page-in` que la oración; hoy el alemán entra con el gesto y la glosa aparece de golpe debajo. Es pérdida de gesto, no de información, y hay dos salidas legítimas: devolvérselo (`.k-fill > .k-note { animation: page-in var(--dur-med) var(--ease-page) both }`) o dejarla quieta a propósito —en cuyo caso sobra el `key={`g${index}`}` de `EstudiarView.tsx:357`, que hoy remonta el nodo en cada oración para nada—.

10. **El rótulo del micrófono cambia con el estado, y el estado ya lo lleva `aria-pressed`.** Grabando, el lector anuncia «Detener grabación, botón, presionado»: el nombre dice la acción de apagar y el estado dice que está encendido. La APG nombra el patrón; también es cierto que muchas apps reales lo hacen así a propósito. Si se cambia, es una línea (`aria-label={t("story.sentence.micAria")}` fijo en `EstudiarView.tsx:452`) y desde la migración 6 la cadena `micAriaRecording` se queda sin ningún otro consumidor: o se cambia el patrón y muere en los seis idiomas, o se queda como está.

11. **El acierto de la nota es un `<span>`, no un `<em>`.** Es lo que manda el markup canónico del átomo 15, así que la migración lo siguió; pero con eso el énfasis de la palabra a corregir deja de ser semántico y pasa a ser color más peso. Cambiar el elemento conservando la clase no mueve un píxel —el `.k-note` ya es itálico— y devuelve la marca a quien lee con lector de pantalla o con hoja de usuario propia. Toca el contrato, no solo la pantalla.

**De la migración 3 (repaso).** Una sola, y es de composición:

12. **La ficha salta 37px al voltear.** El pie de la sesión cambia de alto —un botón «Voltear» (114px) contra la rejilla 2×2 de calificaciones (188px)— y `.k-fill` centra lo que le queda, así que la ficha se recoloca en mitad del giro. Es exactamente lo que hacía el diseño original (`.rr-deck` centraba ficha y acciones como un grupo), y por eso la migración lo respetó; pero contradice la lección de la migración 2 —dos pies que se turnan miden lo mismo o el contenido salta— que el contrato ya escribió para el dock y la banda de lectura. Las tres salidas: reservar en el pie el alto del estado alto (cuesta un literal más, como los 130px de `.k-band`), anclar la ficha arriba en vez de centrarla (deja un hueco muerto bajo la ficha), o dejarlo así porque el volteo es una animación que enmascara el desplazamiento. No la decide el implementador.

**De la migración 5 (Hablar).** Una, y es de producto, no de vocabulario:

13. **Hablar tiene dos salidas y hacen cosas distintas.** «← Salir» (línea superior) abandona: navega y no guarda nada. «✕» (dock) termina: manda las palabras que costaron a Práctica y enseña el cierre. Las dos se ven como salidas y solo una deja rastro de la sesión. La migración las conservó las dos porque quitar una es cambiar el producto, no el CSS; pero el sistema ya tiene un solo sitio para salir de una sesión —el `.k-btn--text` de la línea superior— y las otras dos sesiones (lectura y repaso) tienen exactamente una. Las salidas: que «← Salir» termine también (una salida, siempre guarda, cuesta un toque más para irse), que el aspa se quede como única salida y la línea superior no lleve ninguna (rompe el patrón de las otras dos sesiones), o dejarlo así y distinguirlas por rótulo. No la decide el implementador.

**De la migración 6 (Pronunciar).** Una, y también de producto:

14. **Los tres chips de «empezar por» no filtran.** `Todo · 3`, `Difíciles · 2` y `Repaso · 1` son tres `<span>` sin manejador, con `data-selected="true"` escrito a mano en el primero: la sesión siempre arranca con la cola entera. No es algo que la migración rompiera —venía así del traspaso de diseño—, y la migración se limitó a que dejaran de parecer tocables (`.k-chip k-chip--static`, 26px de alto, sin `:hover` ni `:active`, y por eso mismo fuera del mínimo táctil, que solo rige para controles). Las salidas: hacerlos funcionar (es estado local sobre `items`, no toca el backend, y el átomo ya tiene `[data-selected]` y `:hover` para cuando sean botones), o quitarlos y que la cola sea la cola. Mientras tanto ocupan una línea del preparar diciendo algo que no es verdad.
15. **La pregunta del quiz se lee más alta que la oración alemana.** El mapa del átomo 3 manda `.qcard__prompt` a `.k-card__word`, y `.k-card__word` es el lema de una ficha: `clamp(30px, 9cqw, 44px)`. La frase con hueco y la de sombra, en cambio, son `.k-stage`, que tope 30px. Resultado medido en el quiz: el enunciado en español o alemán de la opción múltiple sale a 44px y el alemán que hay que producir, a 30 — al revés de la jerarquía que el resto del sistema defiende (el contenido en la lengua objetivo manda). Las salidas: que el enunciado sea `.k-card__cue` o una `.k-note` y la ficha se quede sin titular, o que `.k-card__word` distinga «lema» de «enunciado». No lo toqué porque el mapa del contrato dice literalmente `.k-card__word` y cambiarlo es cambiar el mapa, no la pantalla.
17. **El suelo táctil de `.k-link` depende de quién sea su padre**, y la migración 10 estrechó la pregunta sin cerrarla. `.k-link` vive en `global.css:263` entre «las utilidades que no son átomos» y **no declara altura**: son ~20px. La 9 le puso los 44px al `.k-topline--foot .k-link` porque el pie era el único sitio donde había uno; la 10 estrenó el de arriba —«¿ya tienes cuenta? entrar», que en `landing.css:60` traía su `min-height` escrito a mano— y ahí no había manera de dejarlo abierto: portarlo sin suelo era una regresión de accesibilidad medible en una pantalla que hoy cumple. Así que el suelo subió a `.k-topline .k-link`, o sea a la tira entera, y se tomó la tercera de las tres salidas que esta decisión listaba: **dejarlo en el contenedor**. Al medirlo apareció además el porqué del `align-items: flex-end` que la 9 había puesto solo en el pie: el subrayado del enlace es el canto de su caja, y con el texto centrado en los 44px la raya se despega 12px y se lee como un filete del encabezado. Vale para las dos tiras, y ahora está escrito así. **Lo que sigue abierto** son los tres `.k-link` que no viven en ninguna tira y por eso siguen a ~20px: los dos «volver» de `Module.tsx:76` y `:85` y, peor, el **botón de enviar** de `PasswordSetForm.tsx:75`, que es una acción primaria vestida de enlace de texto. Las dos salidas que quedan: que `.k-link` cargue el mínimo él mismo (y entonces es un control, o sea el átomo 18, con la decisión de dónde va el subrayado ya resuelta por la tira), o que `PasswordSetForm` pinte el `.k-btn` que es y `Module` un `.k-btn--text`, que es lo que el mapa del átomo 1 manda para «volver» en las otras cinco pantallas. La segunda no toca el sistema y arregla los tres. No la decide el implementador.

18. **El cascarón viejo de escritorio no se puede borrar todavía, y el motivo no tiene nada que ver con CSS: es el único sitio desde el que se llega a cuatro pantallas.** La migración 15 dejó `sistema.css` como la única hoja de pantalla del proyecto, así que lo que queda es `global.css:87-254` (`kapp`, `kframe`, `k-masthead` y familia, y el `.k-page` de escritorio). El contrato decía «el armazón pasa a `.k-app`/`.k-page`». Al ir a hacerlo, la cuenta de entradas dice esto:

    | ruta | quién enlaza a ella hoy |
    |---|---|
    | `/review` (Práctica) | **solo `Masthead.tsx:41`** |
    | `/chat` (Hablar) | **solo `Masthead.tsx:42`** |
    | `/repaso` · `/pronunciar` | solo Práctica, o sea solo a través de `/review` |
    | `/settings` | `Masthead.tsx:43` **y** `Perfil.tsx:79` |
    | `/module/:id` | `MapaCurso.tsx` |
    | `/gender` | `Portada.tsx:71` |
    | `/story/new` | `Story.tsx`, `Module.tsx` |

    Borrar el `Masthead` deja **Práctica y Hablar sin ninguna entrada**, y con Práctica caen Repaso y Pronunciar — cuatro pantallas que esta serie acaba de migrar. La `TabBar` de la v4 tiene **dos pestañas** (Inicio y «Más», que solo abre Perfil), y el árbol de la v4 llega a Portada → Mapa y Género, y a Perfil → Ajustes. No hay hueco para Repaso, Pronunciar ni Hablar.

    **La pregunta que hay que contestar antes de tocar el cascarón es de producto, no de sistema: ¿dónde viven Repaso, Pronunciar y Hablar en la información de la v4?** Tres salidas visibles, y la elige Samuel:
    (a) una pestaña más en la `TabBar` —«Practicar»— que lleve a un selector como el de `/review` ya migrado;
    (b) entradas desde Portada, junto a Mapa y Género, que es donde ya vive lo de un curso;
    (c) filas en el menú de «Más», junto a Perfil.

    Lo que sí es de sistema y se resuelve solo cuando esa pregunta esté contestada: las cinco rutas legacy pasan a `.k-app` + `.k-page` y su contenido a un `.k-live` (el cascarón nuevo es `100dvh` con `overflow: hidden` y el scroll lo pone cada pantalla, como en `AuthShell`), y con ello **la app entera baja a los 430px de `.k-app`**: hoy estas cinco crecen hasta los 1180 de `.kframe`. Se pierden además la fecha de edición del `Masthead` (`useMastheadDate`) y el enlace a GitHub, que no tienen hueco en ningún sitio de la v4.

    **La migración 13 gastó dos de los tres, y no por decidir sino por seguir el mapa.** El mapa del átomo 1 manda `.k-btn k-btn--text` para «volver» desde antes de que esta decisión existiera (`.snew__back`/`.story__back`, `.ob__exit`, `.k-chapter__exit`, `.rr-head__exit`, `.fin-back`), y los dos de `Module.tsx` son el mismo control en la misma posición. Portarlos como `.k-link` habría sido meter a mano una regresión de accesibilidad en una pantalla recién migrada, con la regla ya escrita al lado. Medidos en la sonda: 145,7 × **44px** en las 14 escenas. **Lo que sigue abierto es lo que de verdad no decide el implementador**: el botón de enviar de `PasswordSetForm.tsx:75` —que no es un «volver» y por tanto no tiene mapa— y, detrás de él, la pregunta de sistema: si `.k-link` debe cargar el suelo táctil él mismo y convertirse en átomo, o seguir siendo una utilidad de `global.css` que hereda el suelo de quien la envuelve.

    **La migración 15 gastó el tercero, y lo que lo decidió fue medirlo.** `PasswordSetForm` **no tenía estilos en ninguna hoja** —su `pw-set-form` y `pw-set-form__field` no existen en ningún `.css` del repo—, así que sus dos campos de contraseña eran `<input>` desnudos de **224 × 32px** y su enviar un `.k-link` de **149 × 28**. Eso no es una decisión pendiente: es una pantalla sin migrar, con tres controles bajo el mínimo de §7.2 en la puerta que bloquea al owner. Los campos van al átomo 17 y el enviar al `.k-btn` que ya era —«Establecer contraseña» es la acción primaria de ese formulario, no un enlace—. **Lo que sigue abierto y sí es de Samuel es solo la pregunta de sistema**: `.k-link` conserva sus ~20px y hoy vive únicamente dentro de tiras, que le ponen el suelo.

16. **El onboarding está en español y solo en español.** No pasa por `i18next`: los siete pasos escriben el castellano a mano en el `.tsx` («¿Cómo te llamas?», «Continuar», «Buena elección. El alemán recompensa la paciencia.»), mientras el resto de la app mantiene 746 claves en seis idiomas. Tiene una lógica —el idioma nativo se elige *dentro* del onboarding, así que al entrar todavía no se sabe cuál es—, pero el navegador sí lo dice, y hoy un francés que se registra lee su primera pantalla de Klara en español. No es de esta migración (la copia no cambió ni una palabra) y arreglarlo son ~60 claves × 6 idiomas, no CSS. Las salidas: traducirlo contra el locale del navegador, o declarar de una vez que el onboarding es en español y que la elección de idioma llega después.

## Objeciones a las decisiones del orquestador

Se registran, no se ejecutan. Cada una con su evidencia, para que el dueño decida.

1. **A la decisión 3 (criterio «≥2 hojas»), por el crítico de cobertura.** El `:active` del botón entró por ese criterio, pero el `:hover` del botón redondo aparece en cuatro hojas (sentence-view.css:234, finish.css:534, speak.css:27, speak.css:246) y el de la fila en dos (pages.css:748, onboarding.css:480), y el borrador no los recogía. *En esta versión sí entran*, así que la objeción queda satisfecha; lo que sigue abierto es si el criterio real debería ser «solo estados que el táctil puede mostrar», que era el argumento de fondo del `:active`.

2. **A la decisión 3 (botón `data-loading`), por el crítico de gramática.** `faltantes.md:3` verificó que «cargando» no existe como estado de botón en ninguna hoja: siempre es un bloque que lo sustituye (`qcard__eval`, `k-eval`). El estado es invención, no consolidación, y pisa el candidato 19 (píldora de proceso) que el propio contrato aparta a Pendientes. El único consumidor parecido ya resuelve sin atributo: NewStory.tsx:115-130 es un `.k-btn` con `disabled={loading}` que intercambia el rótulo. Contraargumento: §5 del brief lo pide como estado obligatorio y `hoja.check.mjs:34` lo exige con el slug `cargando`.

3. **A la decisión 3 (`.k-btn--text` en mono), por Iris Tane.** Es la variante más instanciada del contrato (unas veinte apariciones en los mapas) y pone controles en la voz de la marginalia, contra la gramática 9 que el propio documento escribe. El mono de esas siete hojas era un accidente de cada hoja, no una regla; sans 15px sin caja daría la misma discreción sin gastar un rol tipográfico. Aplicarlo también resolvería el aprieto de los 44px sin `min-width`.

4. **A la decisión 5 (`--score-bad: var(--accent)`), por Iris Tane.** Ahorra un cuarto color y paga con la única señal viva de la interfaz. En la pantalla de lectura, al terminar una lectura en voz alta, el acento aparece a la vez en el micrófono encendido (átomo 2), la etiqueta «grabando» (átomo 6), cada palabra mal con relleno (átomo 14), el filete de la corrección (átomo 13), el punto de la leyenda (átomo 8) y el halo de Klara hablando (átomo 16): seis portadores simultáneos. «Klara te habla» y «lo dijiste mal» quedan del mismo bermellón. `--accent-ink` para «mal» mantendría la familia de matiz y dejaría el acento pleno a lo que de verdad está pasando ahora.

5. **A la decisión 5, corte adicional de Iris Tane: un portador de acento por pantalla.** Quitar el acento de la etiqueta «grabando» (`.k-cap__count[data-tone="live"]`) y del relleno `--accent-wash` de la palabra mal (que conservaría su subrayado de 3px), dejando el acento vivo al micrófono encendido y a la corrección.

6. **A la decisión 8 (el patrón de área táctil), por los tres críticos.** La decisión cita `mobile3.css:139`, que es la safe-area de `.m3-fb`; el patrón real está en `mobile3.css:143`. Y ese patrón **no llega a 44px**: sobre mono de 14px da 30px de alto. *En esta versión la línea está corregida y la aritmética rehecha por átomo* (gramática 6), así que la objeción queda satisfecha; se deja anotada para que nadie vuelva a la línea equivocada.

7. **A la decisión 9 (compatibilidad), por el crítico de gramática.** «Se ven igual sin tocar ningún `.tsx`» no cubre dos estados de `.k-btn`: `:disabled` se atenúa por primera vez y `:active` pasa de `translateY(0)` a escala. *En esta versión la regla 7 lo declara*, así que la objeción queda satisfecha como redacción; sigue abierto si el cambio de `:active` en 42 consumidores es deseable.

8. **A la decisión 9 (congelar `k-error` y `k-level`), por Iris Tane.** *Resuelta por el orquestador:* `k-error` baja a `var(--t-mono)` (regla 7d). Los tres literales de `k-level` (`4px 10px`, `gap 6px`, punto de `5px`) se quedan: son la geometría propia de la insignia, no un paso de escala.

9. **A la decisión 9 (alturas de control), por Iris Tane.** *Resuelta por el orquestador:* `.k-btn` baja a 44px (regla 7b). El sistema queda con exactamente dos alturas de control, 44 y 56, más el redondo grande de 72.

10. **A la decisión 1 (`.k-btn .arrow` textual), por el crítico de gramática.** Renombrar a `.k-btn__arrow` rompe las flechas de ocho consumidores vivos que escriben `className="arrow"`. *En esta versión el selector viejo se conserva como alias hasta que cada pantalla migre*, así que la objeción queda satisfecha; el coste es una regla duplicada durante la migración.

11. **A la decisión 5 y a la regla 11 (los literales que quedan), por Iris Tane.** El contrato introduce unos veinte espaciados fuera de la escala de nueve y consume solo cuatro de los nueve pasos tipográficos. Cada literal tiene su coartada individual («es el valor vivo de tal hoja»); en conjunto, la coartada repetida es cómo un sistema nace con la deuda de lo que vino a sustituir. *En esta versión se tokenizó lo que tenía token exacto* (`--space-3`, `--space-2`, `--space-4`, `--r-xs`, `--t-mark`, `--t-body`) y se unificó el escalón mono; lo que sigue abierto es si los valores heredados de `mobile3.css` merecen redondearse a la escala en vez de conservarse por procedencia.

