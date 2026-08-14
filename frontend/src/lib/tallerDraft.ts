// Ciclo de vida del texto del taller (spec §5). El borrador vive en storage,
// no en React: es lo que hace que sobreviva a un 401 (client.ts:106 desmonta
// la pantalla), una recarga o un cierre accidental. `storage` se inyecta
// (`window.localStorage` en producción) para poder probar sin jsdom.

const DRAFT_KEY = "taller.draft";
const DEFAULT_MAX_PASTE_CHARS = 100_000;

export interface DraftStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export function saveDraft(text: string, storage: DraftStorage): void {
  if (text === "") storage.removeItem(DRAFT_KEY);
  else storage.setItem(DRAFT_KEY, text);
}

export function loadDraft(storage: DraftStorage): string {
  return storage.getItem(DRAFT_KEY) ?? "";
}

export interface TruncateResult {
  text: string;
  droppedLines: number;
}

export function truncatePaste(
  text: string,
  maxChars: number = DEFAULT_MAX_PASTE_CHARS
): TruncateResult {
  if (text.length <= maxChars) return { text, droppedLines: 0 };

  const lines = text.split("\n");
  const kept: string[] = [];
  let length = 0;
  for (const line of lines) {
    const nextLength = kept.length === 0 ? line.length : length + 1 + line.length;
    if (nextLength > maxChars) break;
    kept.push(line);
    length = nextLength;
  }

  if (kept.length === 0) {
    // La primera línea sola ya excede el tope: cortar la partiría a mitad de
    // línea, que la regla prohíbe. Se deja intacta y que la valide el parser.
    return { text, droppedLines: 0 };
  }

  return { text: kept.join("\n"), droppedLines: lines.length - kept.length };
}
