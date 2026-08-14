// El único parser del sistema (spec §3): el backend recibe tarjetas ya
// estructuradas, así que este es el único sitio donde el TSV crudo se
// interpreta. Rechazar 0 o 2+ TABs por línea no es purismo — un export de
// Anki de 3 columnas metería la tercera dentro de `back` en silencio.

const MAX_CARDS = 200;

export interface TallerCard {
  front: string;
  back: string;
}

export interface RejectedLine {
  line: number;
  text: string;
}

export interface ParseResult {
  cards: TallerCard[];
  rejected: RejectedLine[];
  overflow: string;
}

export function parse(text: string): ParseResult {
  const lines = text.split("\n");
  const cards: TallerCard[] = [];
  const rejected: RejectedLine[] = [];

  for (let i = 0; i < lines.length; i++) {
    if (cards.length >= MAX_CARDS) {
      return { cards, rejected, overflow: lines.slice(i).join("\n") };
    }

    const raw = lines[i];
    if (raw.trim() === "") continue; // vacía: se ignora, no se rechaza

    const tabCount = raw.split("\t").length - 1;
    if (tabCount !== 1) {
      rejected.push({ line: i + 1, text: raw });
      continue;
    }

    const [rawFront, rawBack] = raw.split("\t");
    const front = rawFront.trim();
    const back = rawBack.trim();
    if (front === "" || back === "") {
      rejected.push({ line: i + 1, text: raw });
      continue;
    }

    cards.push({ front, back });
  }

  return { cards, rejected, overflow: "" };
}
