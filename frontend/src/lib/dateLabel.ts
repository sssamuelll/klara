const DAYS_ES_SHORT = ["DOM", "LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB"];
const MONTHS_ES_SHORT = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"];
const DAYS_ES_LONG = [
  "domingo",
  "lunes",
  "martes",
  "miércoles",
  "jueves",
  "viernes",
  "sábado",
];
const MONTHS_ES_LONG = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
];

export function mastheadDate(d: Date = new Date(), city = "Nürnberg"): string {
  const day = DAYS_ES_SHORT[d.getDay()];
  const dd = String(d.getDate()).padStart(2, "0");
  const mon = MONTHS_ES_SHORT[d.getMonth()];
  const yyyy = d.getFullYear();
  return `${day} ${dd} ${mon} ${yyyy} · ${city.toUpperCase()}`;
}

export function bylineDate(d: Date = new Date()): string {
  const day = DAYS_ES_LONG[d.getDay()];
  const dd = d.getDate();
  const mon = MONTHS_ES_LONG[d.getMonth()];
  const yyyy = d.getFullYear();
  const cap = day.charAt(0).toUpperCase() + day.slice(1);
  return `${cap} ${dd} de ${mon}, ${yyyy}`;
}

export function greeting(d: Date = new Date()): string {
  const h = d.getHours();
  if (h < 12) return "Buenos días";
  if (h < 19) return "Buenas tardes";
  return "Buenas noches";
}
