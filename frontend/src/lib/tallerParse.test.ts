import { describe, expect, it } from "vitest";
import { parse } from "./tallerParse";

describe("parse", () => {
  it("una línea con un TAB da una tarjeta", () => {
    const { cards, rejected, overflow } = parse("ATP\tadenosín trifosfato");
    expect(cards).toEqual([{ front: "ATP", back: "adenosín trifosfato" }]);
    expect(rejected).toEqual([]);
    expect(overflow).toBe("");
  });

  it("cero TABs se rechaza con su número de línea", () => {
    const { cards, rejected } = parse("una línea sin separador");
    expect(cards).toEqual([]);
    expect(rejected).toEqual([{ line: 1, text: "una línea sin separador" }]);
  });

  it("dos o más TABs se rechaza con su número de línea (export de Anki de 3 columnas)", () => {
    const { cards, rejected } = parse("front\tback\tetiqueta-de-mas");
    expect(cards).toEqual([]);
    expect(rejected).toEqual([{ line: 1, text: "front\tback\tetiqueta-de-mas" }]);
  });

  it("líneas vacías se ignoran, no se rechazan", () => {
    const { cards, rejected } = parse("ATP\tadenosín\n\n   \nADN\tácido");
    expect(cards).toEqual([
      { front: "ATP", back: "adenosín" },
      { front: "ADN", back: "ácido" },
    ]);
    expect(rejected).toEqual([]);
  });

  it("espacios alrededor del TAB se recortan en ambas caras", () => {
    const { cards } = parse("  ATP  \t  adenosín trifosfato  ");
    expect(cards).toEqual([{ front: "ATP", back: "adenosín trifosfato" }]);
  });

  it("front o back vacíos tras strip se rechaza", () => {
    const soloFront = parse("ATP\t   ");
    expect(soloFront.cards).toEqual([]);
    expect(soloFront.rejected).toEqual([{ line: 1, text: "ATP\t   " }]);

    const soloBack = parse("   \tadenosín");
    expect(soloBack.cards).toEqual([]);
    expect(soloBack.rejected).toEqual([{ line: 1, text: "   \tadenosín" }]);
  });

  it("preserva el número de línea real cuando hay líneas vacías y rechazos mezclados", () => {
    const texto = "ATP\tadenosín\n\nsin tab aquí\nADN\tácido";
    const { cards, rejected } = parse(texto);
    expect(cards).toEqual([
      { front: "ATP", back: "adenosín" },
      { front: "ADN", back: "ácido" },
    ]);
    expect(rejected).toEqual([{ line: 3, text: "sin tab aquí" }]);
  });

  it("más de 200 tarjetas: las primeras 200 se aceptan, el resto queda como sobrante crudo", () => {
    const lineas = Array.from({ length: 210 }, (_, i) => `F${i}\tB${i}`);
    const texto = lineas.join("\n");

    const { cards, overflow } = parse(texto);

    expect(cards).toHaveLength(200);
    expect(cards[0]).toEqual({ front: "F0", back: "B0" });
    expect(cards[199]).toEqual({ front: "F199", back: "B199" });
    // El sobrante es texto crudo, sin tocar — arranca en la línea 201.
    expect(overflow).toBe(lineas.slice(200).join("\n"));
  });

  it("un rechazo no consume el cupo de 200: el sobrante arranca después de la 200ª ACEPTADA", () => {
    const lineas = Array.from({ length: 202 }, (_, i) => `F${i}\tB${i}`);
    lineas[5] = "línea rota sin tab"; // se rechaza, no cuenta para el cupo
    const texto = lineas.join("\n");

    const { cards, rejected, overflow } = parse(texto);

    expect(cards).toHaveLength(200);
    expect(rejected).toEqual([{ line: 6, text: "línea rota sin tab" }]);
    // La línea 202 (índice 201) es la que sobra, no la 201.
    expect(overflow).toBe(lineas[201]);
  });

  it("texto vacío no produce tarjetas, rechazos ni sobrante", () => {
    const { cards, rejected, overflow } = parse("");
    expect(cards).toEqual([]);
    expect(rejected).toEqual([]);
    expect(overflow).toBe("");
  });
});
