# Hoy y Biblioteca — el lobby nuevo de Klara

**Fecha:** 2026-09-30 · **Estado:** diseño aprobado por secciones en chat; spec pendiente de revisión
**Mockups:** https://claude.ai/artifact/AauMudVjqVPENieX34qMTH (B «El recorrido» con la ilustración de A; C «La estantería» como biblioteca; prueba de ilustración Pro contra Flash)

## Objetivo

Que al abrir Klara veas en un toque qué te toca hoy y con qué historia, y que la pantalla refleje lo que ya hiciste. Hoy el lobby (`routes/Inicio.tsx`) es más de la mitad papel vacío, propone «Leer · La historia de hoy» sin decir qué historia ni mostrar una palabra en alemán, y el plan del día vive un toque más abajo, en la portada del curso.

**Decisiones de Samuel (2026-09-30):**

- Alcance: todo en un solo spec (Hoy, Biblioteca, ilustraciones y subtítulos).
- Hoy = «El recorrido» (concepto B), con la ilustración de la historia dentro del panel de la parada actual.
- Biblioteca = «La estantería» (concepto C).
- Ilustración: el estilo cálido, con `gemini-3.1-flash-image-preview` ($0,069 por imagen, medido). No las dos tintas de Pro.
- Arquitectura: el día se calcula en un endpoint (sin tablas de estado) y la ilustración se guarda en caché por escena.

## Fuera de alcance

- Datos multitema. «Nuevo tema» sigue llevando a `/nuevo` (placeholder). La estantería pinta los temas que existan: hoy, Deutsch.
- El bloque «Sigue donde lo dejaste» de C. Solo aparecería con dos temas o más, y hoy eso nunca pasa. Entra con el segundo tema.
- Guardar el plan del día (`plan_steps`) y que el recomendador lo reordene.
- La ilustración en la pantalla de lectura o en otras listas. Por ahora vive solo en el panel de Hoy.
- Un diseño de escritorio más allá de la columna de 430 px.

## 1. Pantallas y navegación

### 1.1 Barra de pestañas

`components/TabBar.tsx` pasa a tres pestañas (`k-tabs--3`):

- **Hoy** → `/`.
- **Biblioteca** → `/biblioteca`. También queda activa en `/curso/*`, porque la portada de un tema vive dentro de la biblioteca.
- **Más** → el menú con Perfil, sin cambios.

La pestaña activa sale de una función pura `tabActiva(pathname)`, que es lo que se prueba. Hoy estrena un icono propio (una línea con una parada), con el mismo trazo de 1,5 que los actuales.

### 1.2 Hoy (`/`)

`routes/Inicio.tsx` se reescribe como `routes/Hoy.tsx`, y `RootGate` lo pinta cuando hay sesión. `useCourseData` sale de `Inicio.tsx` a `lib/`, porque Portada y Biblioteca lo siguen usando.

De arriba abajo:

1. **Tira superior** (`.k-topline`). A la izquierda, «Deutsch ⌄» (un botón que lleva a `/biblioteca`) y «EDICIÓN NÜRNBERG · A2» (`biblioteca.cursoSub`). A la derecha, la K.
2. **Saludo** (`home.greeting.conNombre`), como hoy.
3. **Rótulo** `.k-cap--rule`: «EL PLAN DE HOY · N MIN». N es la suma de los minutos de las paradas que faltan (3, 4, 3 y 5, de `curso.paso.*.meta`). Con las cuatro hechas dice «EL PLAN DE HOY · HECHO».
4. **El recorrido** (`.k-route`, átomo nuevo). Es una línea vertical con cuatro paradas en orden fijo: Leer, Pronunciar, Hablar y Repasar. Cada parada lleva un `data-state`:
   - `now`: la primera parada no hecha. Lleva el rótulo «ESTÁS AQUÍ» en acento y su panel (1.3).
   - `done`: fila cerrada con título, subtítulo (en Leer, el título de la historia) y «HECHO» en mono.
   - `pending`: título, subtítulo (`curso.paso.*.dek`) y minutos.

   Todas se pueden tocar, en cualquier orden. Leer abre la historia (1.3), Pronunciar va a `/pronunciar` (directo, sin el selector de Práctica), Hablar a `/chat` y Repasar a `/repaso`. Todas navegan con `state: { from: "/" }`.
5. **Fin de la línea.** Mientras falte algo dice «Mañana, otra historia.». Con las cuatro hechas no hay panel, y la línea cierra con «Listo por hoy. Mañana, otra historia.».

**Carga y error.** Mientras `/today` no responde, las cuatro paradas salen `pending` y sin panel. Si falla, aparece una `.k-error` con «Reintentar» encima de la línea. Las paradas siguen tocables, y Leer cae a `/story/new`.

### 1.3 El panel de la parada actual

Es el `.k-hero` del sistema (bloque 12), con un elemento nuevo, `.k-hero__art`, para la ilustración. En oscuro se comporta como el héroe de hoy: se invierte, y queda un panel color papel sobre el fondo pizarra.

- **Leer.** Si `illustration_path` no es null, `__art` muestra la ilustración en 21:9, con `alt=""` porque el título va justo debajo. Después, la tira «LEER · 3 MIN», el título en alemán, el subtítulo en cursiva si existe y la flecha. La acción depende de `story.state`:
  - `continue`: «Seguir leyendo» → `/estudiar/{id}`.
  - `new`: «Empezar» → `POST /modules/{module_id}/story` (ya existe) y abre `/estudiar/{id}`. Si responde `library.empty`, va a `/story/new`.
  - `request`: el título es «Pídele una historia a Klara» → `/story/new`.
- **Pronunciar.** La tira «PRONUNCIAR · 4 MIN», la frase en alemán entre comillas bajas („…“) y su traducción en cursiva. Sin frase, el subtítulo genérico.
- **Hablar.** La tira «HABLAR · 3 MIN» y «Una conversación con Klara».
- **Repasar.** La tira «REPASAR · 5 MIN» y «{n} fichas por repasar».

### 1.4 Biblioteca (`/biblioteca`, nueva)

Vive dentro de `V4Shell`. Arriba, la misma tira que Hoy. Después, el título `.k-hero--quiet` «Tu biblioteca», el rótulo «TUS TEMAS» y la estantería (`.k-shelf`, átomo nuevo): tapas del mismo alto, en 2:3, apoyadas en un filete que hace de repisa, tres por fila.

- **Tapa de tema** (`.k-cover`). La tela se hace en CSS, con una trama de `repeating-linear-gradient` sobre tokens y sin imágenes. Lleva una franja bermellón con el nombre en serif y «EDICIÓN NÜRNBERG» en mono. No tiene sombra, porque el sistema reserva las sombras para las capas flotantes: el lomo se sugiere con una franja más oscura a la izquierda. Debajo van la barra de progreso (`.k-bar`) y una línea mono («A2 · 12 VENCEN», o «A2 · ● HOY» si no vence nada). Al tocarla va a `/curso/{id}`.
- **Tapa «Nuevo tema»** (`.k-cover--new`). Borde punteado, «+», «Nuevo tema» y el pie «KLARA ARMA EL PLAN». Al tocarla va a `/nuevo`.

### 1.5 La portada del tema (`/curso/:id`)

Pierde la lista «El plan de hoy · 4 pasos», que se mudó a Hoy. Se queda con el título, el progreso y las filas «El mapa del curso» y «Género». El «←» de la tira vuelve a `/biblioteca`.

### 1.6 Textos

Las claves nuevas van en `common.json` de las seis carpetas de `src/locales` (de, en, es, fr, ja, pt). Abajo va el castellano. El resto se traduce en el mismo PR, después de pasar el castellano por `solace-wren`.

| clave | es |
|---|---|
| `tabbar.hoy` | Hoy |
| `tabbar.biblioteca` | Biblioteca |
| `hoy.estasAqui` | Estás aquí |
| `hoy.hecho` | Hecho |
| `hoy.plan` | El plan de hoy · {{min}} min |
| `hoy.planHecho` | El plan de hoy · hecho |
| `hoy.fin` | Mañana, otra historia. |
| `hoy.listo` | Listo por hoy. |
| `hoy.seguir` | Seguir leyendo |
| `hoy.empezar` | Empezar |
| `hoy.pedir` | Pídele una historia a Klara |
| `hoy.fichas_one` / `_other` | {{count}} ficha por repasar / {{count}} fichas por repasar |
| `hoy.error` | No pude cargar tu día. |
| `hoy.reintentar` | Reintentar |
| `biblioteca.temas` | Tus temas |
| `biblioteca.nuevoPie` | Klara arma el plan |

## 2. `GET /today`

### 2.1 La petición

`GET /today?since=<ISO 8601 con zona>`, con sesión (cookie o Bearer). El frontend manda el instante de su medianoche local: `new Date()` con `setHours(0, 0, 0, 0)`, en `toISOString()`. Responde 422 si `since` no trae zona, si está más de 1 minuto en el futuro o si tiene más de 48 horas.

### 2.2 Las reglas

- `steps.read`: existe una fila de `story_views` del usuario con `finished_at >= since`.
- `steps.pronounce`: existe un `pronunciation_attempts.attempted_at >= since`.
- `steps.speak`: existe un `speak_turns.created_at >= since`.
- `steps.review`: existe un `reviews.reviewed_at >= since`, o `due == 0`.
- `due`: las fichas vencidas, con el mismo predicado que `GET /srs/cards/due` (`next_review_at <= now` o NULL), contadas con `count(*)`. Hoy el frontend las cuenta pidiendo 50.
- `now`: la primera de `read`, `pronounce`, `speak` y `review` que no está hecha. Es `null` si las cuatro lo están.
- `story`: se aplica la primera regla que calce.
  1. `done`: la historia de la última vista terminada desde `since`.
  2. `continue`: la historia más reciente del usuario (por `created_at`), si no tiene ninguna vista terminada. Solo se mira la más reciente, para que una historia vieja y abandonada no vuelva.
  3. `new`: la entrada que devuelve `pick_library_entry` para el módulo activo (`read_active_module`, que solo lee). Aquí `id` es null, y `library_entry_id` y `module_id` vienen llenos.
  4. `request`: cuando no calza nada de lo anterior, porque no hay módulo activo o la biblioteca del módulo está vacía.
- `sentence`: la primera frase (`target` y `native`) de la historia de la última vista terminada, de cualquier día. Es null si nunca terminaste una.
- `story.illustration_path`: `/illustrations/{hash}` si la historia (o la entrada de biblioteca) tiene `scene` y existe la fila de su hash (3.2). Si no, null. La ruta es relativa a la base de la API: el frontend le antepone `apiBase()`, que en la app nativa es absoluta.

### 2.3 La respuesta

```json
{
  "now": "read",
  "steps": { "read": false, "pronounce": false, "speak": false, "review": false },
  "story": {
    "state": "new",
    "id": null,
    "library_entry_id": "6f1c…",
    "module_id": "a2e9…",
    "title": "Die Bäckerei am Samstag",
    "subtitle": "Una panadería, un sábado a las ocho.",
    "illustration_path": "/illustrations/3f9a…"
  },
  "sentence": { "target": "Der Bäcker öffnet um acht.", "native": "El panadero abre a las ocho." },
  "due": 12,
  "module": { "id": "a2e9…", "title": "…", "cefr_level": "A2" }
}
```

Con `state: "request"`, `title`, `subtitle` e `illustration_path` vienen en null. `library_entry_id` solo viene lleno en `new`; en `done` y `continue` es null, y `id` y `module_id` son los de la historia (`module_id` puede ser null en una historia pedida fuera de un módulo).

### 2.4 Costo y fallos

Son unas seis consultas, todas con índice: las cuatro tablas de actividad tienen índice por usuario y fecha. Una ilustración que falta nunca hace fallar `/today`.

## 3. Subtítulo e ilustración

### 3.1 Subtítulo y escena

El contrato JSON de `llm/prompts.py` suma dos campos:

- `"subtitle"`: una línea en {native_label}, de 70 caracteres o menos, que diga de qué va la escena sin contar el final.
- `"scene"`: la escena principal en inglés, escrita para un ilustrador, de 300 caracteres o menos: lugar, momento del día, objetos y luz. Sin texto, letreros, marcas ni personas reconocibles.

`stories` y `story_library` ganan dos columnas nullable: `subtitle` (String 160) y `scene` (String 600). El parser acepta que falten, y entonces quedan en null. Lo que se pase del tope de la columna se recorta. `claim_library_entry` copia los dos campos.

### 3.2 La tabla `illustrations`

Sigue el patrón de `AudioCache`: `id`, `hash` (String 64, único), `scene` (Text), `style_version` (Integer), `model` (String 80), `mime_type` (String 40), `image_data` (LargeBinary), `size_bytes` (Integer) y `created_at`.

La clave es `sha256("{style_version}|{escena normalizada}")`. Normalizar es recortar los extremos y colapsar los espacios. **El modelo se guarda, pero no entra en la clave.** Si Google retira el modelo preview y cambiamos a otro, las imágenes ya hechas siguen sirviendo. Cambiar el estilo sí es intencional: se sube `STYLE_VERSION` y el backfill regenera.

### 3.3 La generación: `services/illustration.py`

- Una llamada directa a `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` con `httpx`, que ya es dependencia. Va con la cabecera `x-goog-api-key` y `generationConfig: { responseModalities: ["IMAGE"], imageConfig: { aspectRatio: "21:9", imageSize: "1K" } }`. La imagen llega en `candidates[0].content.parts[].inlineData`, con un timeout de 60 segundos. No se usa LiteLLM porque la 1.85 del backend no pasa `imageConfig`, y subirla toca la generación de historias.
- `STYLE_PROMPT` queda fijo en el código, con `STYLE_VERSION = 1`. Describe a propósito el estilo cálido que se eligió: grabado y riso, tinta negra cálida y bermellón como protagonistas, luz ámbar, rosas y grises de piedra, papel crema con grano y nada de texto. Se calibra en 5.3.
- `ensure_illustration(db, scene) -> str | None`:
  - Escena vacía → `None`.
  - Si ya existe la fila del hash, devuelve el hash.
  - Sin `gemini_api_key` → `None`, sin llamar a nadie.
  - Si no, genera, inserta con `ON CONFLICT DO NOTHING` y devuelve el hash.
  - Un error HTTP, un bloqueo de seguridad, una respuesta sin imagen o una imagen de más de 3 MB se registran en el log y devuelven `None`. No hay reintentos dentro de una petición.

### 3.4 Cuándo se genera

- **`POST /stories`:** después del commit, `BackgroundTasks` llama a `ensure_illustration` con su propia sesión de base de datos.
- **`build_story_library`:** para cada entrada nueva que tenga escena, de a una, y al final imprime el costo.
- **Reclamar una historia de la biblioteca:** nada. La escena copiada apunta a la imagen de la entrada.
- **`scripts/backfill_portadas.py`**, una sola vez, en dos fases:
  1. Textos. Las entradas de la biblioteca sin `subtitle` o `scene` hacen una llamada al modelo de historias con el título y las frases, que devuelve el JSON `{subtitle, scene}`. Las historias clonadas copian los dos campos de su entrada (`library_source_id`), sin LLM. Las historias propias sin textos hacen la misma llamada que la biblioteca.
  2. Imágenes. Cada escena distinta sin fila pasa por `ensure_illustration`, de a una.

  Opciones: `--dry-run` (cuenta e imprime el costo estimado, sin escribir ni llamar a nadie), `--limit N` y `--only-library`. Es idempotente: se puede volver a correr.

### 3.5 Cómo se sirve: `GET /illustrations/{hash}`

No pide sesión. Un `hash` que no sea hex de 64 caracteres da 404. Responde los bytes con su `mime_type`, `Cache-Control: public, max-age=31536000, immutable` y `ETag` igual al hash. El hash no se puede adivinar sin conocer la escena, y las escenas no llevan nombres ni personas reconocibles.

### 3.6 Configuración

- `config.py`: `gemini_api_key: SecretStr | None = None` e `illustration_model: str = "gemini-3.1-flash-image-preview"`.
- `docker-compose.yml`: `GEMINI_API_KEY: ${GEMINI_API_KEY:-}` en el `environment` del backend. **Sin esta línea la clave no llega al contenedor**, aunque esté en el `.env`: el compose pasa las claves una por una (la trampa del #95).

### 3.7 Costo

Cada escena distinta cuesta $0,069. Lo medimos el 2026-09-30 con la cabecera de costo de LiteLLM; el mapa de precios dice $0,045. El subtítulo y la escena del backfill son una llamada corta a DeepSeek por historia, centavos en total. `--dry-run` imprime el total antes de gastar.

## 4. Sistema de diseño

- **Átomos nuevos en `sistema.css`:** `.k-route` (con `__stop`, `__dot`, `__label` y `__end`, y `data-state="now|done|pending"`), `.k-shelf` y `.k-cover` (con la variante `--new`). El bloque 12 gana el elemento `.k-hero__art`, y la barra, la variante `.k-tabs--3`.
- Cada pieza lleva su apartado en `CONTRATO.md` (mapa, medidas, estados y reduced motion) y su muestra en la hoja. `hoja.check.mjs` tiene que pasar en los dos temas y en los dos anchos.
- Cero literales de color. La trama de la tela se hace con `color-mix()` sobre tokens.
- No se crea ninguna hoja de estilos nueva.

## 5. Pruebas, verificación y despliegue

### 5.1 Pruebas (TDD: se escriben primero y se ven fallar)

**Backend (pytest):**

- `/today`:
  - `since` sin zona, en el futuro o de hace más de 48 horas → 422.
  - El borde de cada regla: algo hecho un segundo antes de `since` no cuenta, y algo hecho justo en `since` sí.
  - `review` queda hecho con `due == 0`, y el orden de `now` se respeta.
  - Los cuatro casos de `story`, incluido que una historia terminada ayer lleve a `new`.
  - `sentence`, e `illustration_path` presente y ausente.
  - `due` exacto con más de 50 fichas.
- `services/illustration.py`, contra un transporte HTTP falso:
  - La normalización de la escena.
  - Un acierto de caché no llama a Gemini, y sin clave tampoco se llama.
  - Un éxito guarda la fila con su tipo y tamaño.
  - Un error, una respuesta sin imagen y una imagen de más de 3 MB devuelven `None`.
  - Un choque de inserción concurrente devuelve el hash.
- `GET /illustrations/{hash}`: 200 con cabeceras de caché y sin sesión; 404 si no existe y si el hash está mal formado.
- El JSON de historias con y sin `subtitle` y `scene`, y recortado cuando se pasa de largo. Además, que el reclamo copie los dos campos, que `build_story_library` llame a `ensure_illustration` para las entradas nuevas y que `POST /stories` agende la ilustración solo cuando hay escena.
- `backfill_portadas`: con `--dry-run` no escribe ni llama. Las historias clonadas copian de su entrada. Una segunda corrida no hace nada.

**Frontend (vitest, funciones puras, como `courseView.test.ts`):**

- `buildHoyVM(today)`:
  - Qué parada se abre y qué pie lleva cada estado de `story`.
  - Qué paradas salen HECHO y los minutos del rótulo.
  - Pronunciar con y sin frase.
  - Todo hecho: sin panel y con «Listo por hoy».
- `tabActiva(pathname)` para `/`, `/biblioteca`, `/curso/aleman` y `/perfil`.

### 5.2 Revisión visual

El arnés de Playwright con la API simulada (el de las capturas del 2026-09-30) fotografía Hoy en sus cuatro momentos (al entrar, después de leer, todo hecho y sin historia) y la Biblioteca. Las fotos se toman en claro y oscuro, a 390×844 y a 390×667, y se comparan contra los mockups. El arnés también mide el desborde horizontal de cada contenedor con scroll y los controles de menos de 44 px.

### 5.3 Calibración del estilo

Antes del backfill en prod se generan cuatro escenas reales de la biblioteca, sacadas del backup restaurado en local, con el `STYLE_PROMPT` final. Samuel las aprueba o se ajusta el prompt, y con él `STYLE_VERSION`.

### 5.4 Gates

`gates-locales` antes del PR, porque Actions está apagado.

### 5.5 Despliegue

1. Samuel agrega `GEMINI_API_KEY` al `.env` de prod.
2. `scripts/deploy-prod.sh`. La migración corre sola cuando arranca el contenedor.
3. En la caja, Samuel corre `backfill_portadas --dry-run`, revisa el costo y después corre la versión real.

### 5.6 Quién implementa

Claude escribe las pruebas. Los delegados implementan con TDD, según saver. Claude verifica el hash de las pruebas, corre la suite completa y lee el diff.

No se delegan, y los escribe Claude:

- el router público `/illustrations`, porque no pide sesión;
- `config.py` y `docker-compose.yml`, porque tocan secretos;
- la dependencia de sesión de `/today`.

## 6. Riesgos

- **Flash es un modelo preview.** Su id vive en la configuración, y la clave de las imágenes no depende del modelo.
- **La consistencia del estilo cálido con Flash.** Lo decide la calibración. Si varía demasiado, el plan B es Pro con el mismo prompt, a $0,137 por imagen.
- **Imágenes públicas por hash.** No llevan datos personales, pero la escena de una historia propia le revela el tema a quien tenga el enlace.
- **`since` lo manda el dispositivo.** Si el reloj del teléfono está mal, el día también. Se acepta.
- **Service worker.** Workbox solo cachea las fuentes y excluye `/api` del fallback de navegación, así que `/today` siempre llega fresco. Verificado el 2026-09-30.
- **Una config de Vite compilada.** En `frontend/` existe un `vite.config.js` compilado e ignorado por git, que Vite carga antes que `vite.config.ts`. Este trabajo no toca la config de Vite. Si el plan llegara a tocarla, hay que borrar primero ese `.js`.

## 7. Ajustes al escribir el spec, respecto a lo aprobado en chat

1. La clave de la ilustración no incluye el modelo (3.2), para que retirar el modelo preview no deje las imágenes huérfanas.
2. La respuesta da `illustration_path` relativo en vez de una URL, porque la app nativa usa una base absoluta.
3. En oscuro, el panel es el `.k-hero` del sistema, que se invierte (panel papel sobre pizarra), en vez de la superficie gris del mockup. Así se ve hoy la tarjeta de Leer, y no hace falta otra superficie.
4. «Sigue donde lo dejaste» no se construye: con un solo tema no aparecería nunca.
5. Pronunciar lleva directo a `/pronunciar`, sin pasar por el selector de Práctica.
