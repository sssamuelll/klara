import { describe, expect, it } from "vitest";
import type { MapaResumen } from "../api/types";
import { alternarIdioma, estudioParaGuardar, type MapasCargados } from "./idiomasEstudio";

const ORDEN = ["de", "ja", "en"];
const mapa = (idioma: string): MapaResumen => ({ idioma, estudias: false, nivel: "A1", progreso: 0, vencen: 0 });
const MAPAS = ORDEN.map(mapa);

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

describe("estudioParaGuardar", () => {
  it("sin tocar el selector no manda nada", () => {
    expect(estudioParaGuardar(["ja"], ["ja"], MAPAS)).toBeUndefined();
    expect(estudioParaGuardar([], [], MAPAS)).toBeUndefined(); // la cuenta recién migrada
  });

  it("marcar y desmarcar lo mismo es no haber cambiado nada", () => {
    const vuelta = alternarIdioma(alternarIdioma(["de", "ja"], "en", ORDEN), "en", ORDEN);
    expect(estudioParaGuardar(["de", "ja"], vuelta, MAPAS)).toBeUndefined();
  });

  it("un cambio de verdad manda la lista, en el orden de los mapas", () => {
    expect(estudioParaGuardar(["ja"], alternarIdioma(["ja"], "de", ORDEN), MAPAS)).toEqual(["de", "ja"]);
    expect(estudioParaGuardar([], ["ja"], MAPAS)).toEqual(["ja"]);
  });

  it("sin mapas a la vista no manda nada: cargando, caídos o ninguno", () => {
    const sinMapas: MapasCargados[] = [null, "fallo", []];
    for (const mapas of sinMapas) expect(estudioParaGuardar([], ["ja"], mapas)).toBeUndefined();
  });
});
