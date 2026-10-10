import { describe, expect, it } from "vitest";
import { alternarIdioma } from "./idiomasEstudio";

const ORDEN = ["de", "ja", "en"];

describe("alternarIdioma", () => {
  it("marcar uno lo agrega en el orden de los mapas", () => {
    expect(alternarIdioma(["en"], "de", ORDEN)).toEqual(["de", "en"]);
    expect(alternarIdioma(["de", "en"], "ja", ORDEN)).toEqual(["de", "ja", "en"]);
  });

  it("sin ninguno elegido, marcar uno deja solo ese (la cuenta recién migrada)", () => {
    expect(alternarIdioma([], "ja", ["ja"])).toEqual(["ja"]);
    expect(alternarIdioma([], "en", ORDEN)).toEqual(["en"]);
  });

  it("desmarcar uno lo quita", () => {
    expect(alternarIdioma(["de", "ja"], "de", ORDEN)).toEqual(["ja"]);
  });

  it("el último no se puede desmarcar", () => {
    expect(alternarIdioma(["ja"], "ja", ORDEN)).toEqual(["ja"]);
  });
});
