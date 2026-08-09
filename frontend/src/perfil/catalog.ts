/* Catálogo del Perfil de Aprendizaje (F1.5) — GENERADO.
 *
 * Misma fuente que backend/src/klara/schemas/learner_catalog.py: el paquete
 * de diseño «Onboarding v5». No se transcribe a mano — un typo en una opción
 * sería un 422 silencioso en producción.
 *
 * Las `ops` son IDs estables (el string en español), NO texto de pantalla: la
 * UI los traduce con perfil.aprendizaje.q.<id>.op.<n>. Lo que se guarda es el
 * ID, así el perfil no depende del idioma en que se llenó.
 */

export type ObControl = "radio" | "check" | "triage" | "chips";

export interface ObPregunta {
  id: string;
  b: string;
  control: ObControl;
  ops: string[];
  /** índice de la opción «Otra cosa» que abre un campo de texto */
  otra?: number;
  /** índice de la opción de negación, que no coexiste con ninguna otra */
  excl?: number;
  /** clave de texto libre para la nube de chips */
  escape?: string;
  /** pesa en el estado «Completo» */
  consumo?: boolean;
  /** tiene línea de apoyo bajo la pregunta */
  whisper?: boolean;
}

export const OB_BLOQUES: { id: string; n: number }[] = [
  { id: "hist", n: 3 },
  { id: "ses", n: 3 },
  { id: "entrada", n: 5 },
  { id: "fija", n: 4 },
  { id: "error", n: 7 },
  { id: "cierre", n: 1 },
];

export const OB_PREGUNTAS: ObPregunta[] = [
  { id: "hist_exito", b: "hist", control: "radio", ops: ["Rompiendo algo hasta que funcionó", "Copiando a alguien que ya sabía", "Un curso con fechas y entregas", "Leyendo primero, probando después", "Explicándoselo a otro", "Un rato corto, todos los días", "Otra cosa"], otra: 6, whisper: true },
  { id: "hist_abandono", b: "hist", control: "radio", ops: ["Se puso aburrido", "Perdí el hilo tras faltar unos días", "Era demasiado largo", "No veía para qué me servía", "Se puso difícil de golpe", "Me quedé sin tiempo", "Otra cosa"], otra: 6 },
  { id: "hist_metodos", b: "hist", control: "triage", ops: ["Fichas de repaso", "Videos largos", "Cursos con fechas", "Apps de idiomas", "Leer libros o manuales", "Practicar con alguien"], whisper: true },
  { id: "ses_duracion", b: "ses", control: "radio", ops: ["3 minutos", "10 minutos", "20 minutos o más", "Depende del tema"], consumo: true, whisper: true },
  { id: "ses_lugar", b: "ses", control: "check", ops: ["En casa", "En transporte o en la calle", "En pausas del trabajo"], consumo: true, whisper: true },
  { id: "ses_propuesta", b: "ses", control: "radio", ops: ["Que Klara proponga una sola cosa", "Un menú corto para elegir", "Según el día"] },
  { id: "entrada_arranque", b: "entrada", control: "radio", ops: ["Un ejemplo concreto, la teoría después", "La teoría mínima primero", "Una historia que lo use", "Haciéndolo directamente"] },
  { id: "entrada_interes", b: "entrada", control: "radio", ops: ["Que me sirva ya para algo", "Que me dé curiosidad por sí mismo", "Que me rete", "Depende del tema"], consumo: true },
  { id: "entrada_reto", b: "entrada", control: "radio", ops: ["Fácil, y que suba", "Rétame de una vez", "Que Klara calibre sola"], consumo: true },
  { id: "entrada_audio", b: "entrada", control: "radio", ops: ["Me fija las cosas", "Acompaña, pero no es lo central", "Me dispersa"] },
  { id: "entrada_hablar", b: "entrada", control: "radio", ops: ["Me fija las cosas", "A veces", "No me aporta"] },
  { id: "fija_fichas", b: "fija", control: "check", ops: ["Término y significado", "Un ejemplo y su concepto", "Completar la frase que falta", "Las fichas no me funcionan"], excl: 3, consumo: true },
  { id: "fija_feynman", b: "fija", control: "radio", ops: ["Es mi mejor prueba", "Me sirve a veces", "Me incomoda, pero quiero intentarlo", "No es para mí"] },
  { id: "fija_repeticion", b: "fija", control: "radio", ops: ["Me lo fija", "Me aburre y abandono", "Depende: repetir poco, variar el resto"] },
  { id: "fija_prueba", b: "fija", control: "check", ops: ["Explicarlo sin apuntes", "Usarlo en algo real", "Aprobar un quiz", "Que no se me caiga en el repaso"] },
  { id: "error_correccion", b: "error", control: "radio", ops: ["Directa y al momento", "Al final de la sesión", "Suave y con contexto"], consumo: true },
  { id: "error_atasco", b: "error", control: "radio", ops: ["Explícamelo distinto", "Dame un ejemplo concreto", "Sigue, y vuelve después"], consumo: true },
  { id: "error_pista", b: "error", control: "radio", ops: ["Déjame pelear un rato antes de la pista", "Pista temprana, no me dejes trancado", "Depende del día"], consumo: true },
  { id: "error_memoria", b: "error", control: "radio", ops: ["Me sirve", "Me da igual", "No lo quiero"] },
  { id: "ritmo_deadline", b: "error", control: "radio", ops: ["Me activa", "Me paraliza", "Depende del tema"] },
  { id: "ritmo_abandono", b: "error", control: "check", ops: ["Sesiones largas", "Mucha teoría seguida", "No ver para qué sirve", "Perder el hilo tras faltar unos días", "Otra cosa"], otra: 4 },
  { id: "ritmo_regreso", b: "error", control: "radio", ops: ["Muéstrame dónde iba", "Un repaso corto antes de seguir", "Sigue como si nada"] },
  { id: "libre", b: "cierre", control: "chips", ops: ["Estudio de noche", "Poco tiempo entre semana", "Casi siempre sin audio", "Me distraigo fácil", "Odio los videos largos", "Prefiero leer que escuchar", "Trabajo mejor con presión", "Aprendo en un idioma que no es el mío", "Nada especial"], excl: 8, escape: "libre_texto", whisper: true },
];

/** Las 8 que deciden «Completo». NO son las 23: contar saltos sería un reproche. */
export const OB_CONSUMO: string[] = ["ses_duracion", "ses_lugar", "entrada_interes", "entrada_reto", "fija_fichas", "error_correccion", "error_atasco", "error_pista"];

/** Tope duro por pregunta; por encima es ruido, no señal. */
export const OB_TOPE_MS = 300000;
