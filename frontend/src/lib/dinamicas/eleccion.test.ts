import { describe, expect, it } from "vitest";
import { evaluarEleccion, textoCorrecto, tonoOpcion, type ContenidoEleccion } from "./eleccion";

const c: ContenidoEleccion = {
  item: "ja:kana:か",
  faceta: "reconocer",
  pregunta: { texto: "か", lang: "ja", audio: null },
  opciones: [
    { item: "ja:kana:か", texto: "ka", lang: null },
    { item: "ja:kana:や", texto: "ya", lang: null },
    { item: "ja:kana:け", texto: "ke", lang: null },
  ],
  correcta: "ja:kana:か",
};

describe("evaluarEleccion", () => {
  it("acierta con la correcta y guarda cuál eligió", () => {
    expect(evaluarEleccion(c, "ja:kana:か", 1200)).toEqual({
      item: "ja:kana:か",
      faceta: "reconocer",
      acierto: true,
      pistas: 0,
      ms: 1200,
      detalle: { elegida: "ja:kana:か" },
    });
  });

  it("falla con otra", () => {
    const e = evaluarEleccion(c, "ja:kana:や", 800);
    expect(e.acierto).toBe(false);
    expect(e.detalle).toEqual({ elegida: "ja:kana:や" });
  });
});

describe("tonoOpcion", () => {
  it("sin respuesta, sin tonos", () => {
    expect(tonoOpcion(c, "ja:kana:か", null)).toBeUndefined();
  });

  it("la correcta en bien y la elegida en mal; las demás, nada", () => {
    expect(tonoOpcion(c, "ja:kana:か", "ja:kana:や")).toBe("good");
    expect(tonoOpcion(c, "ja:kana:や", "ja:kana:や")).toBe("bad");
    expect(tonoOpcion(c, "ja:kana:け", "ja:kana:や")).toBeUndefined();
  });
});

describe("textoCorrecto", () => {
  it("es el texto de la opción correcta", () => {
    expect(textoCorrecto(c)).toBe("ka");
  });
});

// Lo que el contenido de reconocer de arriba no deja ver: en oír la pregunta es
// solo audio y el backend baraja las opciones, así que la correcta no va primera.
const oir: ContenidoEleccion = {
  item: "ja:kana:か",
  faceta: "oir",
  pregunta: { texto: null, lang: "ja", audio: "/audio/ja/ka.mp3" },
  opciones: [
    { item: "ja:kana:や", texto: "や", lang: "ja" },
    { item: "ja:kana:か", texto: "か", lang: "ja" },
    { item: "ja:kana:け", texto: "け", lang: "ja" },
  ],
  correcta: "ja:kana:か",
};

describe("lo que no se ve con la correcta primera", () => {
  it("la evidencia es del ítem preguntado y de su faceta, no del que eligió", () => {
    expect(evaluarEleccion(oir, "ja:kana:や", 500)).toMatchObject({
      item: "ja:kana:か",
      faceta: "oir",
      acierto: false,
    });
  });

  it("al acertar solo se tiñe la correcta", () => {
    expect(tonoOpcion(c, "ja:kana:か", "ja:kana:か")).toBe("good");
    expect(tonoOpcion(c, "ja:kana:や", "ja:kana:か")).toBeUndefined();
  });

  it("el texto correcto se busca por ítem, no por posición; sin ella no dice nada", () => {
    expect(textoCorrecto(oir)).toBe("か");
    expect(textoCorrecto({ ...oir, correcta: "ja:kana:ぬ" })).toBe("");
  });
});
