# Klara en tres idiomas: el núcleo y una rebanada por idioma

**Fecha:** 2026-10-09 · **Estado:** diseño aprobado por secciones en chat; spec pendiente de revisión
**Pantallas:** `docs/design/tres-idiomas/pantallas.html`. Se abre en el navegador con el CSS real del repo, y el lienzo de trazo funciona con el mouse.

## Objetivo

Klara deja de ser una app de alemán para varias cuentas y pasa a ser la herramienta personal de Samuel, que habla español de nacimiento, para aprender alemán y japonés y mejorar su inglés. Cada idioma tiene su propio mapa de aprendizaje. Las lecciones se arman con **dinámicas**, que son componentes de ejercicio especializados en lo que enseñan: trazar un kana con el dedo, elegir el artículo alemán según el caso, distinguir *ship* de *sheep*. La app no solo sabe qué lecciones terminó Samuel: sabe qué domina, faceta por faceta.

Esta es la primera de cuatro specs. Cubre el núcleo y una rebanada de cada idioma, y al terminarla Samuel ya estudia los tres idiomas cada día. Las otras tres son los mapas completos de japonés, de alemán y de inglés, y cada una pasa por su propio ciclo de spec, plan e implementación.

**Lo que dijo Samuel (2026-10-09):**

- Niveles de partida: alemán A1, japonés desde cero e inglés B2. Los tres le urgen por igual.
- Metas, todas:
  - alemán: vida diaria en Alemania, trabajo, examen oficial (Goethe/telc) y entender medios;
  - japonés: viajar, anime/manga/juegos, leer y escribir de verdad, y el JLPT;
  - inglés: hablar con soltura, pronunciación y acento, sonar natural y escribir mejor.
- Tiempo: 45–60 min al día.
- Eligió el enfoque A (ítems con facetas, catálogo de dinámicas y mapas como datos) y la división en cuatro specs.
- Aprobó las cinco secciones del diseño en el chat; la sección 4, sobre las pantallas.

**Supuestos dichos en el chat que Samuel no corrigió:**

- Lo principal es el teléfono, porque el trazo se hace con el dedo. El escritorio queda en segundo plano.
- No se hace trabajo para otros usuarios, pero tampoco se rompe nada de lo que ya funciona.
- Inglés americano (en-US).
- El romaji solo aparece dentro de la unidad de hiragana.
- El contenido de las lecciones se prepara y se valida antes de usarlo; nada se improvisa en vivo.
- Lo que ya existe de alemán (historias, Pronunciar, Hablar, Repaso, taller) se queda como está. Lo integra la spec del mapa de alemán.

**Cómo sabremos que funciona:** Samuel abre Klara cinco días o más por semana, y la app muestra qué domina faceta por faceta. Se mide en el backup a las 2 y a las 4 semanas del deploy (sección 11).

## Fuera de alcance

- Onboarding, registro y cualquier trabajo para otras cuentas.
- Japonés más allá del hiragana: katakana, kana con dakuten, combinaciones (が, きゃ), kanji, vocabulario, partículas y furigana. Todo eso va en la spec del mapa de japonés.
- Alemán más allá de la unidad 1: convertir las historias, Pronunciar y Hablar en dinámicas, y retirar `user_cards`, `study_cards` y las columnas viejas de `users`. Va en la spec del mapa de alemán.
- Inglés más allá de los contrastes: phrasal verbs, registro, escritura con corrección y Hablar en inglés. Va en la spec del mapa de inglés.
- Elegir la dinámica con bandit (#129) y el estimador (#126). El diseño los deja posibles, pero no los hace.
- Una herramienta para producir contenido a escala.
- Recordatorios y notificaciones.
- Un diseño de escritorio más allá de la columna de 430 px.
- **El LLM en vivo.** Nada del flujo nuevo llama a un LLM: el contenido se escribe y se valida antes. Con DeepSeek en $0, el núcleo funciona igual.

## 1. Conceptos

| Concepto | Qué es |
|---|---|
| **Ítem** | Lo que se aprende. Tiene una clave natural `<idioma>:<tipo>:<id>`, por ejemplo `ja:kana:あ`, `de:sustantivo:Frau`, `de:caso:dativo` o `en:contraste:ɪ-iː`. |
| **Faceta** | Una forma de saber un ítem. FSRS agenda por separado cada combinación de usuario, ítem y faceta. |
| **Dinámica** | Un tipo de ejercicio registrado. Tiene un componente en el frontend y una declaración en el backend (sección 3). |
| **Actividad** | Una dinámica en un modo, sobre unos ítems y una faceta. |
| **Lección** | Una secuencia de actividades que presenta, practica y termina comprobando. |
| **Unidad** | Un grupo de lecciones con un nivel en la escala del idioma y sus objetivos «puedo…». |
| **Mapa** | Las unidades de un idioma en orden, con su escala. Hay un archivo por idioma. |

**Facetas por tipo de ítem.** Son las únicas válidas; el cargador rechaza cualquier otra. Los identificadores van en ASCII y la interfaz las nombra con tildes.

| Tipo | Facetas |
|---|---|
| `ja:kana` | `reconocer` (ves el kana y eliges su sonido), `oir` (oyes y eliges el kana), `escribir` |
| `de:sustantivo` | `genero`, `reconocer` (qué significa) |
| `de:caso` | `aplicar` |
| `en:contraste` | `oir`, `pronunciar` |

**Modos:**

| Modo | Qué hace | ¿Mueve FSRS? |
|---|---|---|
| `presentar` | Enseña lo nuevo. No hay respuesta. | no |
| `practicar` | Con ayuda: plantilla, pistas, corrección al momento. | no; la evidencia queda en el registro |
| `comprobar` | Sin ayuda. | **sí** |

Los repasos de Hoy siempre van en `comprobar`.

**La nota la pone la dinámica, no tú.** Una sola función del backend convierte en nota cada evidencia en modo `comprobar`:

- `acierto = false` da `again`.
- Un acierto con `pistas > 0`, o con `ms` mayor que el `ms_lento` que declara la dinámica, da `hard`.
- Cualquier otro acierto da `good`.

`easy` no se usa. Cada dinámica declara su propio `ms_lento`, porque un trazo tarda más que una elección.

## 2. Datos

### 2.1 El catálogo vive en archivos del repo

```
backend/src/klara/mapas/
  ja/mapa.json          escala, unidades, lecciones
  ja/kana.json          46 kana: romaji, confusiones, trazos (paths de KanjiVG), audio
  ja/audio/*.mp3        un archivo por kana
  ja/KANJIVG.txt        atribución y licencia (CC BY-SA 3.0)
  de/mapa.json
  de/sustantivos.json   lema, género (+ fuente), plural, traducción, banco de frases
  de/casos.json         acusativo y dativo: tabla de artículos y tabla cerrada de rección
  en/mapa.json
  en/contrastes.json    fonemas (IPA y símbolo de Azure), pares mínimos, audio
  en/audio/*.mp3        un archivo por palabra de los pares
```

El código que carga, valida y genera vive en `backend/src/klara/catalogo/`, separado de `curriculum/` (que es el eje léxico y de género del alemán viejo).

**`mapa.json`** (recortado):

```json
{
  "idioma": "ja",
  "escala": ["かな", "N5", "N4", "N3"],
  "unidades": [{
    "id": "hiragana",
    "titulo": "Hiragana",
    "nivel": "かな",
    "puedo": ["Puedo leer, oír y escribir los 46 hiragana sin pensarlo."],
    "sabes": { "vista": "tabla", "filas": [["ja:kana:あ", "ja:kana:い", "ja:kana:う", "ja:kana:え", "ja:kana:お"],
                                          ["ja:kana:や", null, "ja:kana:ゆ", null, "ja:kana:よ"]] },
    "lecciones": [
      { "id": "a", "titulo": "あ い う え お", "bajada": "la fila de あ: leerla, oírla y escribirla",
        "plantilla": "kana", "items": ["ja:kana:あ", "ja:kana:い", "ja:kana:う", "ja:kana:え", "ja:kana:お"] }
    ]
  }]
}
```

- El `titulo` de una lección va en el idioma que se estudia (lleva `lang`). La `bajada` va en español.
- **Plantillas.** Una lección nombra una `plantilla` y sus `items`, o lista sus `actividades` una por una. Una plantilla es una función del backend que convierte los ítems en actividades. Hay cuatro: `kana`, `sustantivos`, `caso` y `contraste` (sección 6). Esto refina lo que se dijo en el chat, donde cada actividad iba escrita a mano. Con las plantillas, el JSON de las 24 lecciones queda corto, y la regla «toda faceta que una lección practica, esa lección la comprueba» la garantiza la plantilla misma.
- **Actividad suelta.** Se escribe así: `{ "dinamica": "trazo", "modo": "practicar", "items": ["ja:kana:あ"], "faceta": "escribir" }`. Lleva un `contenido` explícito solo cuando la lección necesita algo concreto.
- **Vista de «lo que sabes».** `sabes.vista` puede ser `tabla` (con `filas` y huecos `null`) o `lista` (en el orden de las lecciones).

**Validación.** Se hace al arrancar el servidor y también en los tests. Si algo falla, el servidor no arranca. Se verifica que:

- cada actividad, incluidas las que salen de las plantillas, cumpla el esquema de su dinámica;
- cada ítem nombrado exista en su inventario;
- la faceta sea válida para el tipo de ítem y la dinámica la ejercite;
- la dinámica soporte el modo;
- toda faceta que una lección practica, esa misma lección la compruebe;
- cada audio tenga su archivo y cada kana tenga sus trazos;
- los ids de lección no se repitan dentro de una unidad;
- las `filas` de `sabes` solo nombren ítems de esa unidad.

**Ítems huérfanos.** Al arrancar, el servidor lista en el log las filas de `user_facets` cuya clave ya no está en el catálogo. Esas filas se ignoran y nunca se borran.

### 2.2 Tablas nuevas

Las agrega la migración `20261009_0024`, que solo suma tablas y no toca las existentes.

**`user_facets`**: el estado FSRS de cada faceta.
- `id` uuid; `user_id` con FK a `users` y `ON DELETE CASCADE`.
- `idioma` `varchar(5)`: el prefijo de la clave, copiado para poder consultar por idioma.
- `item_key` `text`, `faceta` `varchar(20)`.
- Los 9 campos del protocolo `FsrsCard` (`services/srs_engine.py:36`), con los mismos tipos que en `StudyCard`, más `created_at`.
- Índice único en (`user_id`, `item_key`, `faceta`) e índice en (`user_id`, `idioma`, `next_review_at`).
- La fila nace con la primera evidencia en `comprobar` de esa faceta, es decir, en la prueba de la lección que la presenta. En la práctica es lo que se aprobó en el chat («la fila se crea cuando una lección te presenta esa faceta»), sin dejar filas de algo que nunca se probó. A partir de ahí la actualiza `apply_review`, sin tocar el motor.

**`facet_reviews`**: el registro de evidencias de todos los modos.
- `id` uuid, generado en el teléfono; sirve como clave de idempotencia.
- `user_id`; `run_id` con FK a `lesson_runs`.
- `idioma`, `item_key`, `faceta`, `dinamica`, `modo`.
- `acierto`, `pistas`, `ms`.
- `nota`: null fuera de `comprobar`.
- `detalle` JSONB, y `created_at`.
- No tiene FK a `user_facets`, porque la evidencia de práctica llega antes de que exista la fila.
- `detalle` guarda un resumen, no los datos crudos. En un trazo, por ejemplo, guarda la `media` y el `largo` de cada trazo, que sirven para afinar los umbrales, pero no los puntos.

**`lesson_runs`**: una fila por cada vez que corre el reproductor.
- `id`, `user_id`, `idioma`.
- `leccion_id`: null si la sesión fue solo de repasos.
- `origen`: `hoy` o `mapa`.
- `started_at` y `finished_at` (este último es null mientras la corrida no termina).
- De esta tabla salen dos cosas:
  - Una lección está hecha si tiene una corrida terminada con `origen = hoy`. De ahí se calcula la posición en el mapa.
  - Lo mismo define si una línea de Hoy está hecha (5.1).

**`users.study_languages`**: `ARRAY(varchar(5))`, puede ser null.
- Si es null, vale `[target_language]`, siempre que ese idioma tenga mapa.
- Se valida en `UserUpdate` (`schemas/user.py:33`): entre 1 y 3 idiomas, sin repetir, y solo idiomas que tienen mapa.

### 2.3 Lo viejo

- `user_cards`, `study_cards`, `vocab_items`, `modules` y las columnas de idioma y nivel de `users` se quedan. Siguen sirviendo a Repaso, Pronunciar, las historias y el taller.
- `GET /today` cambia de respuesta (5.1). Su único consumidor es Hoy (`frontend/src/routes/Hoy.tsx:26`), así que `services/today.py` se reescribe en vez de sumar un endpoint al lado.

## 3. Dinámicas

### 3.1 El contrato

```ts
type Modo = "presentar" | "practicar" | "comprobar";

interface Evidencia {
  item: string;      // "ja:kana:あ"
  faceta: Faceta;    // "escribir"
  acierto: boolean;
  pistas: number;
  ms: number;
  detalle?: unknown; // propio de cada dinámica
}

interface PropsDinamica<C> {
  contenido: C;
  modo: Modo;
  capacidades: Capacidades;
  onResultado: (e: Evidencia[]) => void; // [] en presentar: «listo, sigue»
}
```

- **Una dinámica no sabe nada de lecciones, de Hoy ni de la API.** Lo que necesita del exterior le llega como `capacidades`:
  - `reproducir(audio)`: un archivo del catálogo o TTS en vivo.
  - `puntuar(texto, idioma)`: el puntaje de Azure que ya usa Pronunciar (`lib/useMicScorer.ts`).
  - `puedeEscuchar`, `puedeHablar` y `puedeEscribir`.
- **En el frontend**, los componentes van en `src/dinamicas/`, con un registro que asocia cada nombre a su componente. La lógica pura de cada dinámica va en `src/lib/dinamicas/<nombre>.ts`, con sus tests de vitest. Es el mismo patrón que `Repaso.tsx` con `recallSession.ts`.
- **En el backend**, cada dinámica se declara en `klara/catalogo/` con:
  - el esquema pydantic de su contenido;
  - las facetas que ejercita, por tipo de ítem;
  - los modos que soporta;
  - `ms_lento` y `segundos_tipicos` (de ahí salen los minutos estimados);
  - el **generador**, que arma el contenido a partir del catálogo. Las lecciones y los repasos usan el mismo generador, así que nunca se separan.

### 3.2 Las seis dinámicas

| Dinámica | Modos | Qué ejercita | Quién evalúa | Pista |
|---|---|---|---|---|
| `trazo` | presentar, practicar, comprobar | kana × escribir | el teléfono, contra KanjiVG (5.5) | el trazo animado |
| `articulo` | presentar, practicar, comprobar | sustantivo × género, caso × aplicar | el teléfono, con la tabla de artículos (3.3) | el color del género o la regla de terminación |
| `par-minimo` | presentar, practicar, comprobar | contraste × oír | el teléfono | repetir lento |
| `eleccion` | practicar, comprobar | kana × reconocer/oír, sustantivo × reconocer | el teléfono | — |
| `emparejar` | practicar | kana × reconocer, sustantivo × género | el teléfono | — |
| `sombra` | practicar, comprobar | contraste × pronunciar | Azure, por fonema (3.3) | — |

Esto ajusta lo dicho en el chat en tres puntos:
- `eleccion` se usa en japonés y alemán. En inglés entra con el mapa de inglés.
- `emparejar` solo va en práctica, porque un juego contra el reloj es mala señal para FSRS. Igual deja una evidencia por pareja en el registro.
- `par-minimo` también presenta: muestra las dos tarjetas para oírlas, sin hacer pregunta.

`emparejar` corre contra un reloj, `TIEMPO_EMPAREJAR`, que arranca en 45 s. Una pareja cuenta como acierto si el primer intento con su ficha fue correcto. Las que quedan sin hacer cuando se acaba el tiempo cuentan como fallo.

### 3.3 Los evaluadores que hay que escribir con cuidado

**`articulo`.** Trabaja con la tabla de artículos definidos en singular:

| | m | f | n |
|---|---|---|---|
| nominativo | der | die | das |
| acusativo | den | die | das |
| dativo | dem | der | dem |

El contenido declara el género y el caso correctos, y también los **casos en juego**: en las lecciones de género solo se juega el nominativo (y se ofrecen der, die y das); en las de caso, los tres casos (y se ofrecen der, die, das, den y dem).

Si eliges un artículo equivocado, el evaluador busca todas las lecturas (género, caso) que dan ese artículo dentro de los casos en juego. Cada dimensión se registra solo si todas esas lecturas coinciden en ella. Así funciona con «Ich helfe ___ Frau», donde lo correcto es *der* (femenino, dativo):

| Eliges | Lecturas posibles | Género | Caso |
|---|---|---|---|
| die | (f, nom), (f, ac) | bien | mal |
| dem | (m, dat), (n, dat) | mal | bien |
| das | (n, nom), (n, ac) | mal | mal |

Dos casos más:
- «___ Kaffee ist heiß»: solo se juega el nominativo. Si eliges *die*, la única lectura es (f), así que se registra género mal y nada de caso.
- Si lo correcto es *den* (m, acusativo) y eliges *der*, las lecturas son (m, nom) y (f, dat). Como no coinciden en el género, el género no se registra. En el caso sí coinciden, así que se registra caso mal.

La evidencia de caso va al ítem del caso correcto de ese hueco (`de:caso:acusativo` o `de:caso:dativo`). El nominativo no es un ítem.

*Esto corrige el chat, donde con «das» solo se registraba el fallo de género. Ninguna lectura de «das» es dativo, así que el caso también falló, y eso sí se puede saber.*

**El repaso de un género** saca una frase del banco del sustantivo. Solo usa frases en nominativo o de un caso que ya tenga fila en `user_facets`, así un repaso nunca pide una regla que todavía no viste. Aun así, esa respuesta también cuenta como evidencia de la regla. En un repaso, los casos en juego son el nominativo más los casos que ya tienen fila, y las opciones que se ofrecen salen de ahí.

**`sombra`.** Azure ya puntúa por fonema (`pronunciation/azure_client.py:72`, con granularidad `Phoneme`). Cada lado de un contraste guarda su símbolo en el alfabeto de Azure, por ejemplo `ih` / `iy`. La respuesta cuenta como acierto si el fonema objetivo supera `UMBRAL_FONEMA`, una perilla que arranca en 60. El promedio de la palabra no cuenta.

**`trazo`.** Está en 5.5.

## 4. Una sesión de principio a fin

1. **Componer la sesión.** `GET /api/v1/sesiones/{idioma}` no cambia nada; solo lee. Devuelve:
   - hasta 25 repasos (`CAP_REPASOS`): facetas vencidas de ese idioma, en orden de `next_review_at`, sin dos facetas del mismo ítem seguidas y todas en `comprobar`;
   - la siguiente lección del mapa, ya expandida, si queda alguna.

   Cada actividad viene con su contenido generado, incluidos los trazos y las URLs de audio. Hoy usa la misma función para estimar los minutos, así que los que promete son los de la sesión.
2. **Abrir la corrida.** `POST /api/v1/lesson-runs` con `{ idioma, leccion_id, origen }`.
3. **Responder.** Cada respuesta se manda en `POST /api/v1/evidencias`: la lista de evidencias de esa respuesta, cada una con su `id` (uuid), `run_id`, `dinamica` y `modo`. El servidor:
   1. valida ítem, faceta, dinámica y modo contra el catálogo, y devuelve 422 si algo no cuadra;
   2. inserta en `facet_reviews` con `ON CONFLICT (id) DO NOTHING`;
   3. si el modo es `comprobar`, calcula la nota, crea la fila de `user_facets` si falta y llama a `apply_review`.
4. **Cerrar.** `POST /api/v1/lesson-runs/{id}/fin` marca la corrida como terminada y devuelve cuántos repasos de ese idioma vencen mañana.

**Repetir una lección desde el mapa:** `GET /api/v1/lecciones/{idioma}/{unidad}/{leccion}` devuelve la lección expandida, con todo lo que era `comprobar` bajado a `practicar`. Corre con `origen = mapa`.

**«Otra lección»:** es `GET /api/v1/sesiones/{idioma}?repasos=0`.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v1/today?since=` | las líneas de Hoy (5.1); reemplaza la respuesta actual |
| GET | `/api/v1/mapas` | un resumen por idioma de estudio, para Biblioteca |
| GET | `/api/v1/mapas/{idioma}` | el mapa con su estado y «lo que sabes» |
| GET | `/api/v1/sesiones/{idioma}` | la sesión de una línea |
| GET | `/api/v1/lecciones/{idioma}/{unidad}/{leccion}` | una lección para repetirla en práctica |
| POST | `/api/v1/lesson-runs` | abre una corrida |
| POST | `/api/v1/lesson-runs/{id}/fin` | cierra la corrida y devuelve los repasos de mañana |
| POST | `/api/v1/evidencias` | registra evidencias; es idempotente por `id` |
| GET | `/api/v1/audio/{idioma}/{archivo}` | sirve `mapas/<idioma>/audio/` en solo lectura; el nombre se valida y no acepta rutas |
| PATCH | `/api/v1/me` | ya existe; ahora también acepta `study_languages` |

## 5. Pantallas

Todas se ven en `docs/design/tres-idiomas/pantallas.html`. Las arman los átomos k-* que ya existen; lo nuevo está en 5.7.

### 5.1 Hoy (`/`)

`routes/Hoy.tsx` y `lib/hoyView.ts` se reescriben, y `hoyView` lleva sus tests.

- La línea de arriba es la de Biblioteca: «Klara» y la fecha.
- Después va el saludo (`home.greeting.conNombre`) y un rótulo. Antes de empezar dice «Tu plan de hoy · N min»; cuando ya hiciste algo, «Te quedan · N min»; al terminar todo, «Tu plan de hoy · hecho».
- **El recorrido** (`k-route`) tiene una parada por idioma de estudio. Las paradas de antes (leer, pronunciar, hablar, repasar) salen de Hoy; esas pantallas siguen funcionando y se abren desde el mapa de alemán (5.3).

```ts
interface Linea {
  idioma: string;
  estado: "hecha" | "ahora" | "pendiente";
  minutos: number;   // suma de segundos_tipicos de la sesión
  repasos: number;   // los que entran en la sesión (≤ CAP_REPASOS)
  leccion: { id: string; titulo: string; bajada: string } | null;
  hecho: { repasos: number; leccion: string | null } | null; // si estado = hecha
}
```

- **Orden.** Va primero el idioma cuya última línea terminada es la más vieja. Solo cuenta lo que terminaste **antes de hoy**, así el orden no cambia a mitad del día. Si hay empate, o un idioma nunca se ha hecho, decide el orden de `study_languages`. *Esto ajusta la sección 1 del chat, donde el orden era fijo: con un orden fijo, en los días cortos siempre se quedaba fuera el mismo idioma.*
- **Estado.** Una línea está `hecha` si desde `since` terminó una corrida `origen = hoy` de ese idioma. La primera que no está hecha es `ahora`, y las demás quedan `pendiente`. Cualquiera se puede tocar.
- **Panel de la línea actual** (`k-hero`):
  - Rótulo: «<idioma> · N min» y «Empezar».
  - Titular: el título de la lección, con `lang` del idioma. Si no hay lección, «N repasos».
  - Bajada: «N repasos y luego <bajada>.». Sin repasos va solo la `bajada`. Sin lección dice «Solo repasos: terminaste el mapa.».
- **Fila hecha:** el nombre del idioma, «Hecho» y «N repasos · <título de la lección>».
- **Fila pendiente:** el nombre del idioma, los minutos y «N repasos · <bajada>».
- **Sin idiomas con mapa:** una nota que lleva a Ajustes.
- **Error:** como hoy, con `k-error` y «Reintentar».

### 5.2 Biblioteca

- Va una tapa por idioma de estudio (`k-cover`, el átomo no cambia), y cada tapa abre `/mapa/:idioma`. La tapa lleva:
  - en la franja, el nombre del idioma (con `lang`);
  - abajo, el nivel de la unidad actual;
  - la barra, con la fracción de lecciones hechas;
  - el pie, que dice «N vencen» en acento o «Al día».

  Los datos salen de `GET /api/v1/mapas`.
- Debajo de la repisa de idiomas va «Tus temas», con la tapa del taller.
- La tapa del curso viejo de alemán desaparece. Al curso se llega desde el mapa de alemán.

### 5.3 Mapa (`/mapa/:idioma`)

- **Escala.** Arriba va la escala del idioma, con «estás aquí» (`k-bar--milestones`). La posición es `(i + p) / (n − 1)`, donde:
  - `i` es el índice del nivel de la unidad actual;
  - `p` es la fracción de lecciones hechas de esa unidad;
  - `n` es el largo de la escala.
- **Unidades.** Cada unidad muestra su título, su nivel y sus «puedo…» (`k-note`). Sus lecciones van en filas `k-row`:
  - hecha (✓): se puede tocar, y se repite en práctica;
  - actual («Hoy»): abre la línea;
  - las siguientes no se pueden tocar. La que viene justo después de la actual va como `pending`, y el resto como `locked`.
- **«Lo que sabes».** Cada ítem lleva una rayita por faceta, con tres valores:
  - `0`: la faceta no tiene fila;
  - `1`: `interval_days < 21`;
  - `2`: `interval_days ≥ 21`, que cuenta como sabido (es el umbral de «madura» de Anki).

  La vista `tabla` dibuja las `filas` del mapa, con sus huecos. La vista `lista` pone una fila por ítem; en alemán el artículo va en su color, con `k-row__n[data-gender]`, que ya existe.
- **En alemán**, al final va la fila «También en alemán: historias, Pronunciar y Hablar», que lleva a la portada vieja (`/curso/aleman`).
- **En japonés**, al pie, va la atribución de KanjiVG.

### 5.4 El reproductor (`/sesion/:idioma` y `/leccion/:idioma/:unidad/:leccion`)

La pantalla es `routes/Sesion.tsx`, y su reducer, `lib/sesion.ts`, se prueba con vitest.

- **El marco** es el de Repaso:
  - `SessTop`: salir, «<idioma> · <lección>» y la cuenta;
  - `k-bar--segs`, con un segmento por actividad (`skipped` para las que se saltan);
  - `k-fill`, con la dinámica;
  - `k-dock`, con el estado y las acciones.
- **El rótulo del modo** es un `k-cap k-cap--center` que dice «Nuevo», «Práctica», «Prueba» o «Repaso». «Repaso» es una prueba que llega por la cola de repasos.
- **Avance.** Si aciertas todo, la sesión sigue sola después de `AUTO_AVANCE_MS` (700). Si algo falla, la corrección se queda en pantalla hasta que tocas «Seguir».
- **Una actividad de práctica que fallas** vuelve una sola vez, tres actividades después.
- **Saltar.** «Ahora no puedo escuchar», «Ahora no puedo hablar» y «Ahora no puedo escribir» apagan esa capacidad por el resto de la sesión. Las actividades que la necesitan quedan `skipped` y no dejan evidencia. Si no hay permiso de micrófono o Azure está caído, pasa lo mismo que con «hablar».
- **Teclado** (en escritorio): 1–5 eligen una opción; Enter o Espacio siguen.
- **Envíos.** La evidencia sale al responder. Si un envío falla, se reintenta una vez, y si vuelve a fallar se cuenta. Al final aparece «N respuestas no se guardaron», como en Repaso.
- **Final.** Muestra:
  - una tabla ítem × faceta con lo que cambió;
  - una nota con lo que quedó por reforzar;
  - los repasos de mañana (los devuelve `…/fin`).

  Abajo van «Otra lección», si queda alguna, y «A Hoy».
- **Si cierras a mitad**, la corrida queda sin `finished_at`. La próxima vez la sesión se compone de nuevo, y lo que ya se registró se queda.

### 5.5 Trazo

- **El lienzo.**
  - Usa la caja de 109 × 109 de KanjiVG, con la guía 田 punteada.
  - Funciona con Pointer Events, así que el mismo código atiende el dedo, el lápiz y el mouse.
  - Lleva `touch-action: none` y `user-select: none`.
- **En presentar,** el kana se dibuja solo, trazo por trazo y numerado, con su audio y su mnemotecnia. «Ver el orden» repite la animación.
- **En practicar,** la plantilla va en gris, con un punto que late donde empieza el trazo que toca.
- **En comprobar,** el lienzo está vacío y la consigna es el sonido («Escribe la que suena»), con audio.
- **La evaluación** ocurre al soltar el dedo, en `evaluarTrazo(puntos, esperado)` (`lib/dinamicas/trazo.ts`):
  1. Se remuestrea el trazo a `N = 24` puntos por largo de arco.
  2. Se muestrea igual el trazo de KanjiVG que toca.
  3. Se calculan dos números: `media`, la distancia media entre puntos pareados, y `largo`, el cociente entre el largo del trazo y el de referencia.
  4. El trazo vale si `media < UMBRAL_MEDIA` (12) y `0,55 < largo < 1,7`.

  La dirección no necesita su propio chequeo, porque un trazo al revés dispara la media. Un toque de menos de 4 unidades se ignora. Las tres constantes son perillas: se afinan con los `media` y `largo` reales que quedan en `detalle`.
- **Si el trazo vale,** se reemplaza por el trazo limpio de KanjiVG, para que lo último que veas sea la forma correcta. Si no vale, se borra.
- **La pista.** En práctica, al segundo fallo en el mismo trazo se anima el correcto, y eso cuenta 1 pista. En prueba basta el primer fallo: se muestra el correcto, lo repasas encima y también cuenta 1 pista.
- **La evidencia** es una por kana, con `acierto = pistas ≤ 2`. Con la nota de la sección 1, eso da `good` con 0 pistas, `hard` con 1 o 2, y `again` con más.
- **Ya está probado en el mockup.** Con un mouse simulado, el lienzo rechaza el trazo al revés y el que no corresponde, y muestra la pista al segundo fallo.

### 5.6 Ajustes

Se agrega «Idiomas que estudias», al lado del selector de idioma que ya existe (`routes/Settings.tsx`). Son chips `k-chip` de selección múltiple, uno por cada idioma con mapa. Al guardar se manda `study_languages` con `PATCH /api/v1/me`. Hay que dejar al menos uno marcado.

### 5.7 Piezas nuevas del sistema

Cada pieza entra a `sistema.css` y a la hoja (`docs/design/klara-sistema/hoja.html`) con sus estados, y `hoja.check.mjs` tiene que pasar. Antes de crear una pieza, se revisa si un átomo existente la cubre, como se hizo en la migración 14.

| Pieza | Estados |
|---|---|
| `.k-trazo`: lienzo, guía, plantilla, tinta, punto de inicio y pista | presentar, practicar, comprobar, corregido |
| `.k-sabes`: tabla y rayitas de facetas | 0, 1, 2, hueco |
| `.k-hueco`: frase con hueco | vacío, bien, mal con corrección |
| `.k-par`: tarjeta de par mínimo | normal, bien, mal |
| `.k-ficha`: ficha del tablero | normal, elegida, hecha, mal |
| `.k-btn--redondo`: el botón grande de oír | normal, sonando |

Tres cosas usan lo que ya existe en vez de una pieza nueva:
- El rótulo del modo es `k-cap k-cap--center`.
- La corrección es una `k-note`.
- Los chips de `articulo` son `k-chip` con `data-tone`.

Para el japonés se agrega el token `--font-ja` (Noto Serif JP, de Google Fonts, como las otras familias), aplicado a `:lang(ja)`.

## 6. Las rebanadas

### 6.1 Japonés: hiragana

- **Unidad 1, «Hiragana»**, nivel かな. Son 10 lecciones, una por fila: あ, か, さ, た, な, は, ま, や (や ゆ よ), ら y わ (わ を ん). En total, 46 kana.
- **La plantilla `kana`**, a partir de los kana de una fila, arma:
  1. Para cada kana, un `trazo` en presentar y luego uno en practicar.
  2. Una `eleccion` en practicar, mezclando reconocer y oír. Los distractores salen primero de las confusiones (さ/ち, ぬ/め, る/ろ, わ/ね/れ…) y después de lo que ya viste.
  3. Un `emparejar` con la fila.
  4. La prueba: un `trazo` en comprobar por cada kana, y luego una `eleccion` en comprobar de reconocer y otra de oír por cada kana.
- **El romaji** va en Hepburn. Solo aparece en esta unidad y solo como nombre del sonido. Las excepciones (し shi, ち chi, つ tsu, ふ fu, ん n, を o) se explican al presentarlas.
- Cada lección dura unos 10 min.

### 6.2 Alemán: der, die, das

- **Unidad 1, «der, die, das»**, nivel A1, con unos 40 sustantivos.
  - La base es la lista A1 de `scripts/load_de_modules.py`.
  - Se pueden sumar sustantivos A1 que falten (Frau, Mann), siempre que su género salga del oráculo.
  - Un sustantivo sin entrada en `gender_lexicon` no entra. Monat, por ejemplo, queda fuera.
- **6 lecciones:**
  1. La familia
  2. En el café
  3. La casa
  4. El día y la ciudad
  5. Akkusativ: den
  6. Dativ: dem y der
- **La plantilla `sustantivos`** (lecciones 1–4) arma:
  1. Un `articulo` en presentar: el sustantivo con su artículo, la traducción, el audio y la regla de terminación si la tiene (`detect_gender_rule`, `curriculum/gender_rules.py:69`).
  2. Un `articulo` en practicar, solo en nominativo.
  3. Una `eleccion` del significado.
  4. Un `emparejar` de sustantivo con artículo.
  5. La prueba de género y de significado.
- **La plantilla `caso`** (lecciones 5–6) presenta la regla con su tabla y sus regentes, y después practica y prueba `articulo` en frases, sobre sustantivos que ya viste.
- **Las frases.** Cada una declara su regente, y el regente tiene que estar en la tabla cerrada de rección de `casos.json`:
  - acusativo: für, ohne, durch, gegen, um; haben, sehen, kaufen, bestellen, trinken, brauchen, suchen;
  - dativo: mit, bei, von, zu, aus, nach, seit; helfen, danken, gehören, gefallen, antworten.

  Quedan fuera las preposiciones de dos casos (in, an, auf…), el artículo indefinido y el plural.
- **El audio** usa el TTS en vivo, con la caché que ya existe.

### 6.3 Inglés: sonidos que el español no tiene

**Unidad 1**, nivel B2: 8 contrastes del inglés americano (en-US), con una lección por contraste.

| Contraste | Pares (ejemplos) | Azure |
|---|---|---|
| ɪ / iː | ship–sheep, live–leave, bit–beat | ih / iy |
| æ / ʌ | cat–cut, bag–bug, cap–cup | ae / ah |
| æ / ɑ | hat–hot, cap–cop, sack–sock | ae / aa |
| b / v | berry–very, ban–van, best–vest | b / v |
| s / z | sip–zip, bus–buzz, ice–eyes | s / z |
| ʃ / tʃ | ship–chip, share–chair, wash–watch | sh / ch |
| θ / t | three–tree, thin–tin, thank–tank | th / t |
| dʒ / j | jet–yet, joke–yolk, jam–yam | jh / y |

**La plantilla `contraste`** arma la lección así:

1. **Presentar,** con `par-minimo`: las dos palabras con su audio y una explicación, desde el español, de cómo se articula cada sonido.
2. **Practicar:** unos 6 `par-minimo` y unos 3 `sombra`.
3. **Probar:** unos 4 `par-minimo` y 2 `sombra`.

`sombra` repite las palabras de los pares, así que no hace falta audio aparte.

### 6.4 Lo que dura y lo que pesa

- **Duración.** Con una lección al día, el japonés dura 10 días, el alemán 6 y el inglés 8. Después cada línea queda solo con repasos hasta que llegue la spec de su mapa, así que las tres specs tienen que estar listas unas dos semanas después del deploy.
- **Carga de repasos.** Son unas 236 facetas: 46 × 3 + unas 40 × 2 + 2 + 8 × 2. Con retención 0,9, una faceta nueva pide unos 3–4 repasos en sus primeras dos semanas. Eso da unos 55–60 repasos al día entre los tres idiomas, unos 20 por línea, debajo del tope de 25.

## 7. De dónde sale el contenido y cómo se valida

| Contenido | Fuente | Validación |
|---|---|---|
| Trazos de los kana | KanjiVG (CC BY-SA 3.0). `scripts/importar_kanjivg.py` los extrae una vez a `kana.json`. | El número de trazos de cada kana coincide con la tabla estándar. |
| Audio de kana y de pares | TTS generado una vez como archivo, con la voz por idioma que ya está configurada (`elevenlabs_voice_id_ja`, `elevenlabs_voice_id_en`). | Azure tiene que reconocer el audio como lo que debía decir; si no, no entra. Lo que falla dos veces lo escucha Samuel. |
| Sustantivos y su género | `scripts/load_de_modules.py`, más los que se sumen. | El género coincide con `gender_lexicon`. El cruce se hace al preparar el contenido y queda en el JSON como `genero_fuente: "oracle"`. |
| Frases, mnemotecnias y explicaciones | Las escribe un LLM al preparar la rebanada, en español. | Reglas: el artículo cuadra con el género y el caso, el regente está en la tabla de rección, y la longitud está dentro del límite. |
| Audio de las frases en alemán | TTS en vivo, con caché. | Ya funciona en las historias. |

El contenido va solo en español, que es la lengua de Samuel. Por los 6 idiomas del gate solo pasa la interfaz.

## 8. Cuando algo falla

| Falla | Qué pasa |
|---|---|
| Un mapa o un inventario roto | El servidor no arranca y los tests fallan. |
| Un estado sin su ítem | Se lista en el log al arrancar y se ignora; nunca se borra. |
| Una evidencia que no cuadra (ítem, faceta, dinámica o modo) | El servidor responde 422 y el reproductor la cuenta como no guardada. |
| Una evidencia repetida | `ON CONFLICT DO NOTHING`: no cuenta dos veces. |
| Un envío que falla | Se reintenta una vez; si vuelve a fallar, entra en el aviso del final. |
| No hay micrófono, Azure o TTS | Esas actividades quedan `skipped` y la sesión sigue. |
| Falla `GET /today` | Aparece `k-error` con «Reintentar», como hoy. |
| Falla `GET /sesiones` | El reproductor muestra el error, con «Reintentar» y «Salir». |
| Cierras la app a mitad de una lección | La corrida queda abierta. La próxima vez la lección empieza de nuevo, y lo que ya se registró se queda. |

## 9. Pruebas

**vitest (frontend):**
- `lib/dinamicas/trazo.ts`: el trazo bueno, el invertido, el corto, el que no corresponde y uno de largo fuera de rango.
- `lib/dinamicas/articulo.ts`: todas las tablas de 3.3, incluidos los casos ambiguos.
- Las otras dinámicas:
  - `par-minimo` y `eleccion`;
  - `emparejar`: una evidencia por pareja, y el tiempo agotado cuenta como fallo;
  - `sombra`: el fonema objetivo contra el umbral.
- `lib/sesion.ts`: las fases, el avance automático, la vuelta tres actividades después, los saltos por capacidad y la cuenta de envíos fallidos.
- `lib/hoyView.ts`: los estados, el panel y los textos de las líneas.

**pytest (backend):**
- **El cargador:** pasa con un mapa bueno, pasa con los mapas reales del repo, y cada regla de 2.1 tiene un caso roto que falla con un mensaje claro.
- **Las plantillas:** cada faceta que se practica también se comprueba.
- **La función de nota**, con su tabla de casos.
- **`POST /evidencias`:**
  - la idempotencia;
  - el 422;
  - que solo `comprobar` mueva FSRS;
  - que la fila nazca con la primera prueba;
  - la evidencia de varios ítems a la vez.
- **`GET /today`:**
  - el orden, que solo cuenta lo terminado antes de hoy;
  - el tope de 25;
  - la línea hecha;
  - una línea sin lección y una sin repasos.
- **`GET /sesiones`:** nunca van dos facetas del mismo ítem seguidas, y el repaso de un género solo usa casos que ya viste.
- **`user_facets`** cumple `FsrsCard`; se suma al test de paridad que ya existe (`tests/test_srs_engine_paridad.py`).
- **La migración** sube y baja.

**Contenido:**
- Los 46 kana tienen trazos y audio.
- Cada sustantivo tiene `genero_fuente: "oracle"`. El CI no tiene la base de prod, así que el cruce se hace al preparar el contenido y el test revisa el resultado.
- Cada frase cumple la tabla de rección.
- Cada audio existe.

**Gate:** las cadenas nuevas de la interfaz van en los 6 idiomas (`frontend/src/locales/*`). Como las Actions están apagadas, `gates-locales` corre antes del PR.

## 10. Deploy

- La migración `20261009_0024` solo suma: tres tablas y una columna. El downgrade las quita.
- El audio y los trazos viajan dentro del backend, en `klara/mapas/`. La imagen tiene que incluir los JSON y los mp3, no solo los `.py`.
- El deploy lo corre Samuel con `scripts/deploy-prod.sh`. Después, en el teléfono:
  1. elige sus tres idiomas en Ajustes;
  2. hace una línea de cada idioma;
  3. revisa que el mapa muestre lo que cambió.

## 11. Medición

A las 2 y a las 4 semanas del deploy, el backup de prod se restaura en un postgres desechable, igual que en la medición del 2026-10-09, y se mide:

- **Días por semana con al menos una evidencia en `facet_reviews`.** La meta es 5 o más.
- **Minutos por día**, a partir de `lesson_runs`.
- **Líneas terminadas por idioma.** La que se quede atrás dice si el orden está funcionando.

Si no se llega a la meta, lo siguiente no es la spec de un mapa: es averiguar por qué.

## 12. Orden de construcción

Cada paso deja algo que Samuel puede usar, así el uso diario empieza antes de terminar todo:

1. **Núcleo del backend:** el catálogo con su validación, las tablas, las evidencias, la función de nota y las plantillas. Todavía no hay nada que ver.
2. **El reproductor con `eleccion`, y Hoy con sus líneas.** Lo prueba el reconocimiento de los kana.
3. **Japonés:** `trazo`, `emparejar` y las 10 lecciones de hiragana. Desde aquí ya se usa a diario.
4. **Alemán:** `articulo` y la unidad «der, die, das».
5. **Inglés:** `par-minimo`, `sombra` y los 8 contrastes.
6. **Mapa, Biblioteca y Ajustes**, y las piezas nuevas en la hoja del sistema.

## Riesgos y perillas

- **Los umbrales son suposiciones.** `UMBRAL_MEDIA`, el rango de `largo` y `UMBRAL_FONEMA` no se pueden saber hasta tener trazos y audio reales. Quedan como constantes con nombre, y `detalle` guarda los datos para afinarlas.
- **El TTS de un kana suelto puede sonar raro,** porque no tiene contexto. Por eso pasa por Azure, y lo que falla dos veces lo escucha Samuel.
- **La carga de repasos crece con las facetas** (3 por kana). Si se pasa del tope a menudo, se bajan las lecciones nuevas antes que subir el tope.
- **Los trazos del mockup son aproximados.** Los reales salen de KanjiVG, y su atribución es obligatoria (CC BY-SA 3.0).
