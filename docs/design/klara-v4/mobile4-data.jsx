/* global React, SAMPLE_STORY, M2_REPASO, M2_MAPA, M2_HABLAR */
/* Klara v4 — cada tema es un curso; idiomas es solo un tipo */

const T4 = (text) => ({ type: "text", text });
const W4 = (text, def, ej) => ({ type: "word", text, word: { lemma: text, article: null, translation: def, example: ej || null } });

const KT_ALEMAN = {
  id: "aleman", tipo: "idioma", titulo: "Alemán", sub: "Edición Nürnberg · A2", estado: "● ahora", progreso: 0.76, vencen: 12,
  pasos: [
    { n: "01", t: "Leer", dek: "El sello que tarda diez minutos", meta: "3 min", ruta: "estudiar", e: "hecha" },
    { n: "02", t: "Pronunciar", dek: "Tres frases de la historia, en voz alta", meta: "4 min", ruta: "estudiar", e: "ahora" },
    { n: "03", t: "Hablar", dek: "En el mostrador, con Klara", meta: "2 min", ruta: "explicar", e: "luego" },
    { n: "04", t: "Repasar", dek: "12 fichas vencen hoy", meta: "5 min", ruta: "repaso", e: "luego" },
  ],
  sesTitulo: SAMPLE_STORY.title,
  chunks: SAMPLE_STORY.sentences.map((s) => ({ tokens: s.tokens, gloss: s.es })),
  conMic: true, fb: { pre: "Casi. En ", post: " el acento cae en la primera sílaba — otra vez, sin prisa." },
  explicar: {
    modo: "Conversación · pide tu turno",
    texto: "Ein Termin, gerne. Wann haben Sie Zeit?", gloss: "Un turno, claro. ¿Cuándo tiene tiempo?",
    corr: { mal: "ich möchten", bien: "ich möchte", nota: "Con „ich“ el verbo pierde la n. Lo dijiste igual que ayer — va quedando." },
    ayuda: "¿Cómo se dice…?",
  },
  fichas: M2_REPASO.fichas,
  mapa: {
    h1: ["Vas por ", "A2", "."], frase: M2_MAPA.fraseNivel, stops: ["A0", "A1", "A2", "B1"], x: 0.76,
    rows: [
      { n: "A1", tit: "Ocho módulos dominados", e: "dominado", estado: "Marzo ✓" },
      { n: "07", tit: "En el Bürgeramt", e: "encurso", estado: "● 4/7" },
      { n: "08", tit: "El médico de cabecera", e: "proximo", estado: "Próximo" },
      { n: "B1", tit: "Contar qué pasó, opinar", e: "futuro", estado: "Más adelante" },
    ],
  },
};

const KT_THREEJS = {
  id: "threejs", tipo: "tecnico", titulo: "Three.js", sub: "Módulo 1 · La escena", estado: "sigue hoy", progreso: 0.12, vencen: 8,
  pasos: [
    { n: "01", t: "Estudiar", dek: "Escena, cámara, renderer", meta: "4 min", ruta: "estudiar", e: "ahora" },
    { n: "02", t: "Practicar", dek: "Monta tu primera escena", meta: "6 min", ruta: "estudiar", e: "luego" },
    { n: "03", t: "Explicar", dek: "Cuéntaselo a Klara, sin apuntes", meta: "3 min", ruta: "explicar", e: "luego" },
    { n: "04", t: "Repasar", dek: "8 fichas vencen hoy", meta: "3 min", ruta: "repaso", e: "luego" },
  ],
  sesTitulo: "Escena, cámara, renderer",
  chunks: [
    { tokens: [T4("Toda imagen en Three.js nace de tres piezas: una "), W4("escena", "el mundo: contenedor de todo lo que existe", { de: "const scene = new THREE.Scene()", es: "crea el mundo, vacío" }), T4(", una "), W4("cámara", "el punto de vista desde donde se mira el mundo"), T4(" y un "), W4("renderer", "el que dibuja la escena en píxeles"), T4(".")], gloss: "Las tres piezas mínimas de cualquier proyecto." },
    { tokens: [T4("La escena es un "), W4("grafo", "árbol de objetos: mover al padre mueve a los hijos"), T4(" de objetos: cada "), W4("mesh", "geometría + material = un objeto visible", { de: "new THREE.Mesh(geometry, material)", es: "lo que de verdad se ve" }), T4(" cuelga de otro.")], gloss: "Piensa en un móvil de cuna: todo cuelga de algo." },
    { tokens: [T4("El renderer toma escena y cámara y pinta píxeles en un "), W4("canvas", "el lienzo HTML donde termina cada frame"), T4(", sesenta veces por segundo.")], gloss: "Tú describes el mundo; dibujar es trabajo suyo." },
  ],
  conMic: false, fb: null,
  explicar: {
    modo: "Feynman · hoy explicas tú",
    texto: "Explícame qué hace el renderer — como si yo tuviera doce años.", gloss: "Si te falta el término exacto, pídemelo.",
    corr: null, ayuda: "Pista",
  },
  fichas: [
    { article: "", w: "Scene", pos: "clase", trad: "el mundo: contenedor raíz de objetos", de: "const scene = new THREE.Scene()", es: "todo lo visible cuelga de aquí" },
    { article: "", w: "PerspectiveCamera", pos: "clase", trad: "punto de vista con perspectiva real", de: "new THREE.PerspectiveCamera(75, w / h, 0.1, 1000)", es: "fov, aspecto, near, far" },
    { article: "", w: "WebGLRenderer", pos: "clase", trad: "el que dibuja: escena + cámara → píxeles", de: "renderer.render(scene, camera)", es: "una vez por frame" },
    { article: "", w: "Mesh", pos: "clase", trad: "geometría + material = objeto visible", de: "new THREE.Mesh(geo, mat)", es: "lo que de verdad se ve" },
  ],
  mapa: {
    h1: ["Módulo ", "1", "."], frase: "Ya entiendes las piezas. El módulo 2 es luz y sombra; el 4, tu primera escena publicada.", stops: ["M1", "M2", "M3", "M4"], x: 0.12,
    rows: [
      { n: "01", tit: "La escena", e: "encurso", estado: "● 1/4" },
      { n: "02", tit: "Luz, sombra, material", e: "proximo", estado: "Próximo" },
      { n: "03", tit: "Movimiento y cámara", e: "futuro", estado: "—" },
      { n: "04", tit: "Tu escena publicada", e: "futuro", estado: "—" },
    ],
  },
};

const KT_ENTREVISTA = {
  id: "entrevista", tipo: "oral", titulo: "Entrevista: CEO en Berlín", sub: "Inglés · día 1 de 5", estado: "nuevo", progreso: 0.04, vencen: 4,
  pasos: [
    { n: "01", t: "Escuchar", dek: "La entrevista modelo, con calma", meta: "4 min", ruta: "estudiar", e: "ahora" },
    { n: "02", t: "Frases clave", dek: "Dilas en voz alta, con tu acento", meta: "4 min", ruta: "estudiar", e: "luego" },
    { n: "03", t: "Simular", dek: "Klara hace de CEO", meta: "5 min", ruta: "explicar", e: "luego" },
    { n: "04", t: "Repasar", dek: "Las fichas del día", meta: "3 min", ruta: "repaso", e: "luego" },
  ],
  sesTitulo: "La entrevista modelo",
  chunks: [
    { tokens: [T4("Thanks for coming in. So — "), W4("walk me through", "explícame paso a paso", { de: "Walk me through your CV.", es: "Cuéntame tu CV, paso a paso." }), T4(" your background, in two minutes.")], gloss: "Gracias por venir. Cuéntame tu trayectoria, en dos minutos." },
    { tokens: [T4("We raised a "), W4("seed round", "primera ronda de inversión"), T4(" last spring, so the "), W4("runway", "meses de caja que quedan", { de: "Our runway is nine months.", es: "Nos quedan nueve meses de caja." }), T4(" question is on everyone's mind.")], gloss: "Levantamos una ronda semilla en primavera; la pregunta de la caja está en el aire." },
    { tokens: [T4("Our "), W4("churn", "clientes que se van cada mes"), T4(" was brutal until we rebuilt "), W4("onboarding", "el arranque del usuario en el producto"), T4(".")], gloss: "Perdíamos clientes cada mes, hasta que rehicimos el arranque." },
  ],
  conMic: true, fb: { pre: "Bien. Junta ", post: " en una sola frase, sin pausa en el medio." },
  explicar: {
    modo: "Simulación · Klara es la CEO",
    texto: "Tell me about yourself — you have sixty seconds.", gloss: "Háblame de ti — tienes sesenta segundos.",
    corr: null, ayuda: "¿Cómo se dice…?",
  },
  fichas: [
    { article: "", w: "walk me through", pos: "expresión", trad: "explícame paso a paso", de: "Walk me through your last project.", es: "Cuéntame tu último proyecto, paso a paso." },
    { article: "", w: "runway", pos: "sust.", trad: "meses de caja que quedan", de: "Our runway is nine months.", es: "Nos quedan nueve meses de caja." },
    { article: "", w: "churn", pos: "sust.", trad: "clientes que se van cada mes", de: "Churn dropped to two percent.", es: "La fuga bajó al dos por ciento." },
    { article: "", w: "seed round", pos: "sust.", trad: "primera ronda de inversión", de: "We closed our seed round in May.", es: "Cerramos la ronda semilla en mayo." },
  ],
  mapa: {
    h1: ["Día ", "1", "."], frase: "Cinco días: entender, sonar natural, simular dos veces y llegar con frases tuyas.", stops: ["D1", "D2", "D3", "D4", "D5"], x: 0.04,
    rows: [
      { n: "D1", tit: "Entender la entrevista", e: "encurso", estado: "● hoy" },
      { n: "D2", tit: "Tus respuestas, primera vuelta", e: "proximo", estado: "Mañana" },
      { n: "D3", tit: "Números y métricas", e: "futuro", estado: "—" },
      { n: "D4", tit: "Simulación completa", e: "futuro", estado: "—" },
      { n: "D5", tit: "La entrevista real", e: "futuro", estado: "—" },
    ],
  },
};

const KLARA_TEMAS = { aleman: KT_ALEMAN, threejs: KT_THREEJS, entrevista: KT_ENTREVISTA };
Object.assign(window, { KLARA_TEMAS });
