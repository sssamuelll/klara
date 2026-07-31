/* global React */
/* Klara mobile v2 — datos de muestra (mapa, plan del día, hablar, repaso) */

const M2_TODAY = {
  fecha: "LUN 04 MAY 2026",
  ciudad: "NÜRNBERG",
  saludo: "Buen lunes,",
  nombre: "Samuel",
  linea: "Tres minutos. Sin apuro.",
  numero: "Nº 128",
};

const M2_PLAN = [
  { n: "01", id: "leer", titulo: "Leer", dek: "El sello que tarda diez minutos", meta: "3 min · 6 palabras nuevas", ruta: "lectura" },
  { n: "02", id: "pronunciar", titulo: "Pronunciar", dek: "Tres frases de la historia, en voz alta", meta: "4 min", ruta: "lectura" },
  { n: "03", id: "hablar", titulo: "Hablar", dek: "En el mostrador, con Klara", meta: "2 min", ruta: "hablar" },
  { n: "04", id: "repasar", titulo: "Repasar", dek: "12 fichas que vencen hoy", meta: "5 min", ruta: "repaso" },
];

const M2_MAPA = {
  nivel: "A2",
  progreso: 0.76, /* posición sobre la regla A0→B1 */
  fraseNivel: "Ya pides turnos, entiendes carteles y sobrevives al Bürgeramt. B1 es contar qué pasó ayer.",
  stats: [
    { num: "214", label: "palabras en repaso" },
    { num: "38", label: "historias leídas" },
    { num: "4 h 12 m", label: "de oído entrenado" },
  ],
  siguiente: { n: "02", titulo: "Pronunciar", dek: "Tres frases del Bürgeramt", meta: "4 min", ruta: "lectura" },
  niveles: [
    {
      id: "A1", titulo: "A1 — Dominado", resumen: "8 módulos · terminado en marzo", plegado: true,
      modulos: [
        { n: "01", titulo: "Presentarse", meta: "5 historias · 48 palabras", estado: "dominado" },
        { n: "02", titulo: "Números y horas", meta: "4 historias · 39 palabras", estado: "dominado" },
        { n: "03", titulo: "En la panadería", meta: "6 historias · 55 palabras", estado: "dominado" },
        { n: "04", titulo: "La casa nueva", meta: "5 historias · 52 palabras", estado: "dominado" },
      ],
    },
    {
      id: "A2", titulo: "A2 — Vas aquí", resumen: "", plegado: false,
      modulos: [
        { n: "05", titulo: "En el súper", meta: "6 historias · 74 palabras", estado: "dominado" },
        { n: "06", titulo: "La U-Bahn", meta: "5 historias · 61 palabras", estado: "dominado" },
        { n: "07", titulo: "En el Bürgeramt", meta: "7 historias · 92 palabras", estado: "encurso", frac: "4/7" },
        { n: "08", titulo: "El médico de cabecera", meta: "6 historias · 80 palabras", estado: "proximo" },
        { n: "09", titulo: "Pequeñas charlas", meta: "5 historias · 58 palabras", estado: "proximo" },
      ],
    },
    {
      id: "B1", titulo: "B1 — Más adelante", resumen: "", plegado: false,
      modulos: [
        { n: "10", titulo: "Contar qué pasó", meta: "el pasado, por fin", estado: "futuro" },
        { n: "11", titulo: "Opiniones y matices", meta: "estar de acuerdo, y no", estado: "futuro" },
      ],
    },
  ],
};

const M2_MODULO = {
  n: "07",
  nivel: "A2",
  titulo: "En el Bürgeramt",
  dek: "Turnos, formularios y la señora del mostrador. Todo lo que la burocracia alemana te va a pedir, en historias.",
  meta: "7 historias · 92 palabras",
  frac: { hechas: 4, total: 7 },
  historias: [
    { n: "1", t: "El número que no llega", fecha: "28 ABR", estado: "leida" },
    { n: "2", t: "Frau Schmidt pregunta dos veces", fecha: "29 ABR", estado: "leida" },
    { n: "3", t: "El formulario amarillo", fecha: "30 ABR", estado: "leida" },
    { n: "4", t: "El sello que tarda diez minutos", fecha: "HOY", estado: "hoy" },
    { n: "5", t: "Una firma que falta", fecha: "", estado: "porleer" },
    { n: "6", t: "La cita se cambia", fecha: "", estado: "porleer" },
    { n: "7", t: "Todo listo, casi", fecha: "", estado: "porleer" },
  ],
  palabras: [
    { w: "der Termin", e: "dominada" },
    { w: "anmelden", e: "repaso" },
    { w: "das Formular", e: "repaso" },
    { w: "die Bestätigung", e: "nueva" },
    { w: "der Mietvertrag", e: "repaso" },
    { w: "dran sein", e: "nueva" },
    { w: "unterschreiben", e: "dominada" },
  ],
};

const M2_HABLAR = {
  foco: "Pedir un turno en el mostrador",
  focoMeta: "USA LO DE HOY: ANMELDEN · DER TERMIN",
  turnos: [
    { who: "k", de: "Guten Tag! Was kann ich für Sie tun?", es: "¡Buen día! ¿Qué puedo hacer por usted?" },
    { who: "u", text: "Guten Tag… ich möchten einen Termin." },
    { who: "corr", mal: "ich möchten", bien: "ich möchte", nota: "Con „ich“ el verbo pierde la n. Lo dijiste igual que ayer — va quedando." },
    { who: "k", de: "Ein Termin, gerne. Wann haben Sie Zeit?", es: "Un turno, claro. ¿Cuándo tiene tiempo?", speaking: true },
  ],
};

const M2_REPASO = {
  total: 12,
  pos: 5,
  fichas: [
    { article: "der", w: "Mietvertrag", pos: "sust. m.", trad: "el contrato de alquiler", de: "Haben Sie den Mietvertrag dabei?", es: "¿Tiene el contrato de alquiler con usted?", fuente: "MÓD 07 · EL SELLO QUE TARDA DIEZ MINUTOS" },
    { article: "", w: "anmelden", pos: "verbo sep.", trad: "registrar(se), darse de alta", de: "Wo kann ich mich anmelden?", es: "¿Dónde me puedo registrar?", fuente: "MÓD 07 · EL FORMULARIO AMARILLO" },
    { article: "die", w: "Bestätigung", pos: "sust. f.", trad: "la confirmación", de: "Ich brauche eine Bestätigung.", es: "Necesito una confirmación.", fuente: "MÓD 07 · UNA FIRMA QUE FALTA" },
    { article: "", w: "dran sein", pos: "expresión", trad: "ser el turno de uno", de: "Sie sind dran!", es: "¡Es su turno!", fuente: "MÓD 07 · EL NÚMERO QUE NO LLEGA" },
  ],
};

Object.assign(window, { M2_TODAY, M2_PLAN, M2_MAPA, M2_MODULO, M2_HABLAR, M2_REPASO });
