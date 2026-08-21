import { describe, expect, it } from "vitest";
import { loadDraft, saveDraft, truncatePaste, type DraftStorage } from "./tallerDraft";

function memoryStorage(): DraftStorage {
  const map = new Map<string, string>();
  return {
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => void map.set(k, v),
    removeItem: (k) => void map.delete(k),
  };
}

describe("saveDraft / loadDraft", () => {
  it("taller.draft sobrevive a un desmontaje y vuelve al montar", () => {
    // La persistencia real vive en el storage, no en React: guardar y volver a
    // leer contra el MISMO storage es exactamente lo que pasa entre un
    // desmontaje (401, recarga, cierre accidental) y el remontaje.
    const storage = memoryStorage();
    saveDraft("ATP\tadenosín trifosfato", storage);

    const restored = loadDraft(storage);

    expect(restored).toBe("ATP\tadenosín trifosfato");
  });

  it("guardar texto vacío limpia el borrador en vez de dejar una cadena vacía", () => {
    const storage = memoryStorage();
    saveDraft("algo", storage);
    saveDraft("", storage);

    expect(loadDraft(storage)).toBe("");
    expect(storage.getItem("taller.draft")).toBeNull();
  });

  it("sin borrador previo, loadDraft devuelve cadena vacía", () => {
    expect(loadDraft(memoryStorage())).toBe("");
  });
});

describe("truncatePaste", () => {
  it("texto por debajo del tope no se toca", () => {
    const { text, droppedLines } = truncatePaste("una línea\notra línea", 1000);
    expect(text).toBe("una línea\notra línea");
    expect(droppedLines).toBe(0);
  });

  it("corta en el último salto de línea completo, jamás a mitad de línea", () => {
    // 3 líneas de 10 chars + 2 \n = 32 chars. Tope en 25: caben las dos
    // primeras (10 + 1 + 10 = 21 <= 25); la tercera se cae completa.
    const lineas = ["a".repeat(10), "b".repeat(10), "c".repeat(10)];
    const { text, droppedLines } = truncatePaste(lineas.join("\n"), 25);

    expect(text).toBe(`${lineas[0]}\n${lineas[1]}`);
    expect(text.length).toBeLessThanOrEqual(25);
    expect(droppedLines).toBe(1);
    // Nunca una línea partida: lo que queda son líneas completas.
    expect(text.endsWith(lineas[1])).toBe(true);
  });

  it("una sola línea que ya excede el tope no se puede cortar sin partirla: se deja intacta", () => {
    const unaLinea = "x".repeat(50);
    const { text, droppedLines } = truncatePaste(unaLinea, 10);

    expect(text).toBe(unaLinea);
    expect(droppedLines).toBe(0);
  });

  it("reporta cuántas líneas se fueron, no solo que se cortó", () => {
    const lineas = Array.from({ length: 10 }, (_, i) => `linea-${i}`.repeat(3));
    const texto = lineas.join("\n");
    const { droppedLines } = truncatePaste(texto, Math.floor(texto.length / 2));

    expect(droppedLines).toBeGreaterThan(0);
    expect(droppedLines).toBeLessThan(10);
  });
});
