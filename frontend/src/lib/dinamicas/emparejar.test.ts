import { describe, expect, it } from "vitest";
import {
  estadoFicha,
  evidenciasTablero,
  inicialTablero,
  paresFallados,
  seAcaboElTiempo,
  sinTiempo,
  tocar,
  ultimoFallo,
  type ContenidoEmparejar,
} from "./emparejar";

const c: ContenidoEmparejar = {
  pares: [
    { item: "ja:kana:か", izquierda: "か", derecha: "ka" },
    { item: "ja:kana:き", izquierda: "き", derecha: "ki" },
    { item: "ja:kana:く", izquierda: "く", derecha: "ku" },
  ],
  segundos: 45,
  lang_izquierda: "ja",
  faceta: "reconocer",
};
const items = c.pares.map((p) => p.item);
const nuevo = () => inicialTablero(items, [...items].reverse());

describe("tocar", () => {
  it("una pareja bien cerrada", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:か");
    expect(e.hechas).toEqual(["ja:kana:か"]);
    expect(e.elegida).toBeNull();
  });

  it("da igual por qué lado se empiece", () => {
    const e = tocar(tocar(nuevo(), "der", "ja:kana:き"), "izq", "ja:kana:き");
    expect(e.hechas).toEqual(["ja:kana:き"]);
  });

  it("tocar otra del mismo lado cambia la elegida", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "izq", "ja:kana:き");
    expect(e.elegida).toEqual({ lado: "izq", item: "ja:kana:き" });
  });

  it("fallar marca las dos fichas y sacude la segunda", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    expect(e.falladas.sort()).toEqual(["ja:kana:か", "ja:kana:き"]);
    expect(e.hechas).toEqual([]);
    expect(estadoFicha(e, "der", "ja:kana:き")).toBe("mal");
    expect(estadoFicha(e, "izq", "ja:kana:か")).toBeUndefined();
  });

  it("una hecha ya no se toca", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:か");
    expect(tocar(e, "izq", "ja:kana:か")).toBe(e);
  });

  it("termina al cerrar todas", () => {
    let e = nuevo();
    for (const i of items) e = tocar(tocar(e, "izq", i), "der", i);
    expect(e.terminado).toBe(true);
  });
});

describe("seAcaboElTiempo", () => {
  it("termina el tablero y suelta la elegida", () => {
    const e = seAcaboElTiempo(tocar(nuevo(), "izq", "ja:kana:か"));
    expect(e.terminado).toBe(true);
    expect(e.elegida).toBeNull();
  });
});

describe("estadoFicha", () => {
  it("elegida y hecha", () => {
    const e = tocar(nuevo(), "izq", "ja:kana:か");
    expect(estadoFicha(e, "izq", "ja:kana:か")).toBe("elegida");
    const f = tocar(e, "der", "ja:kana:か");
    expect(estadoFicha(f, "der", "ja:kana:か")).toBe("hecha");
  });

  // Las dos fichas de una pareja comparten ítem; el lado es lo que dice cuál es cuál.
  it("la elegida es solo la del lado que se tocó, no su pareja", () => {
    const e = tocar(nuevo(), "izq", "ja:kana:か");
    expect(estadoFicha(e, "izq", "ja:kana:か")).toBe("elegida");
    expect(estadoFicha(e, "der", "ja:kana:か")).toBeUndefined();
  });

  it("la que falló es solo la del lado que se tocó, no la otra del mismo ítem", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    expect(estadoFicha(e, "der", "ja:kana:き")).toBe("mal");
    expect(estadoFicha(e, "izq", "ja:kana:き")).toBeUndefined();
  });

  it("la marca de «mal» se va con el siguiente toque", () => {
    const fallada = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    const siguiente = tocar(fallada, "izq", "ja:kana:く");
    expect(estadoFicha(siguiente, "der", "ja:kana:き")).toBeUndefined();
    expect(estadoFicha(siguiente, "izq", "ja:kana:く")).toBe("elegida");
  });
});

describe("evidenciasTablero", () => {
  it("acierto solo lo cerrado sin fallos; lo demás, fallo", () => {
    let e = nuevo();
    e = tocar(tocar(e, "izq", "ja:kana:か"), "der", "ja:kana:か"); // limpia
    e = tocar(tocar(e, "izq", "ja:kana:き"), "der", "ja:kana:く"); // falla き y く
    e = tocar(tocar(e, "izq", "ja:kana:き"), "der", "ja:kana:き"); // la cierra después
    e = seAcaboElTiempo(e); // く queda sin cerrar
    const evs = evidenciasTablero(c, e, 20000);
    expect(evs.map((x) => [x.item, x.acierto])).toEqual([
      ["ja:kana:か", true],
      ["ja:kana:き", false],
      ["ja:kana:く", false],
    ]);
    expect(evs.every((x) => x.faceta === "reconocer" && x.pistas === 0 && x.ms === 20000)).toBe(true);
  });
});

describe("evidenciasTablero lleva la faceta del contenido", () => {
  it("en alemán el tablero ejercita el género, no el reconocer", () => {
    const evs = evidenciasTablero({ ...c, faceta: "genero" }, seAcaboElTiempo(nuevo()), 1000);
    expect(evs.every((x) => x.faceta === "genero")).toBe(true);
  });
});

// El reproductor ignora `[]` fuera de presentar: un tablero con parejas nunca puede dejar una lista vacía.
describe("un tablero real siempre deja evidencias", () => {
  it("sin cerrar ninguna cuando se acaba el tiempo: un fallo por pareja", () => {
    const evs = evidenciasTablero(c, seAcaboElTiempo(nuevo()), 45000);
    expect(evs.map((x) => [x.item, x.acierto])).toEqual([
      ["ja:kana:か", false],
      ["ja:kana:き", false],
      ["ja:kana:く", false],
    ]);
  });

  it("cerrar todas sin fallar: todas aciertan", () => {
    let e = nuevo();
    for (const i of items) e = tocar(tocar(e, "izq", i), "der", i);
    const evs = evidenciasTablero(c, e, 12000);
    expect(evs).toHaveLength(items.length);
    expect(evs.every((x) => x.acierto)).toBe(true);
  });

  it("cerrar todas, pero con un fallo en medio: esa pareja no acierta", () => {
    let e = nuevo();
    e = tocar(tocar(e, "izq", "ja:kana:か"), "der", "ja:kana:き"); // falla か y き
    for (const i of items) e = tocar(tocar(e, "izq", i), "der", i);
    expect(e.terminado).toBe(true);
    expect(evidenciasTablero(c, e, 30000).map((x) => x.acierto)).toEqual([false, false, true]);
  });
});

describe("el tablero después del último toque", () => {
  it("con el tiempo agotado ya no se toca nada", () => {
    const e = seAcaboElTiempo(nuevo());
    expect(tocar(e, "izq", "ja:kana:か")).toBe(e);
  });

  it("agotar el tiempo dos veces es lo mismo que una", () => {
    const e = seAcaboElTiempo(nuevo());
    expect(seAcaboElTiempo(e)).toBe(e);
  });

  it("cerrar la última pareja y que el reloj llegue a cero no cambia nada", () => {
    let e = nuevo();
    for (const i of items) e = tocar(tocar(e, "izq", i), "der", i);
    expect(seAcaboElTiempo(e)).toBe(e);
  });

  it("el tiempo suelta también la ficha que acababa de fallar", () => {
    const fallada = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    expect(seAcaboElTiempo(fallada).ultimoMal).toBeNull();
  });
});

describe("fallar", () => {
  it("suelta la elegida: el siguiente toque empieza otro intento", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    expect(e.elegida).toBeNull();
  });

  it("fallar dos veces con las mismas fichas no las apunta dos veces", () => {
    let e = nuevo();
    e = tocar(tocar(e, "izq", "ja:kana:か"), "der", "ja:kana:き");
    e = tocar(tocar(e, "izq", "ja:kana:か"), "der", "ja:kana:き");
    expect(e.falladas.sort()).toEqual(["ja:kana:か", "ja:kana:き"]);
  });

  it("el estado anterior no se toca", () => {
    const antes = nuevo();
    const copia = JSON.parse(JSON.stringify(antes));
    tocar(tocar(antes, "izq", "ja:kana:か"), "der", "ja:kana:き");
    expect(antes).toEqual(copia);
  });
});

// Lo que el tablero enseña al acabar con fallos y mientras se juega (la corrección y el «き no es ku»).
describe("ultimoFallo", () => {
  it("antes de fallar no hay nada que decir", () => {
    expect(ultimoFallo(nuevo())).toBeNull();
    expect(ultimoFallo(tocar(nuevo(), "izq", "ja:kana:か"))).toBeNull();
  });

  it("dice qué dos fichas se tocaron, la de la izquierda primero, empiece por donde empiece", () => {
    const izqPrimero = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    const derPrimero = tocar(tocar(nuevo(), "der", "ja:kana:き"), "izq", "ja:kana:か");
    expect(ultimoFallo(izqPrimero)).toEqual({ izq: "ja:kana:か", der: "ja:kana:き" });
    expect(ultimoFallo(derPrimero)).toEqual({ izq: "ja:kana:か", der: "ja:kana:き" });
  });

  it("es el último: el siguiente fallo reemplaza al anterior", () => {
    let e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    e = tocar(tocar(e, "izq", "ja:kana:く"), "der", "ja:kana:か");
    expect(ultimoFallo(e)).toEqual({ izq: "ja:kana:く", der: "ja:kana:か" });
  });

  it("se va con el siguiente toque y con el tiempo agotado", () => {
    const fallada = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    expect(ultimoFallo(tocar(fallada, "izq", "ja:kana:く"))).toBeNull();
    expect(ultimoFallo(seAcaboElTiempo(fallada))).toBeNull();
  });
});

describe("sinTiempo", () => {
  it("el tiempo agotado con parejas sin cerrar", () => {
    expect(sinTiempo(nuevo())).toBe(false);
    expect(sinTiempo(seAcaboElTiempo(nuevo()))).toBe(true);
    expect(sinTiempo(seAcaboElTiempo(tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:か")))).toBe(true);
  });

  it("cerrar todas no es quedarse sin tiempo, ni aunque el reloj llegue a cero después", () => {
    let e = nuevo();
    for (const i of items) e = tocar(tocar(e, "izq", i), "der", i);
    expect(sinTiempo(e)).toBe(false);
    expect(sinTiempo(seAcaboElTiempo(e))).toBe(false);
  });
});

describe("paresFallados", () => {
  const ids = (e: ReturnType<typeof nuevo>) => paresFallados(c, e).map((p) => p.item);

  it("un tablero cerrado sin fallos no tiene nada que corregir", () => {
    let e = nuevo();
    for (const i of items) e = tocar(tocar(e, "izq", i), "der", i);
    expect(ids(e)).toEqual([]);
  });

  it("sin tiempo y sin cerrar nada: todas", () => {
    expect(ids(seAcaboElTiempo(nuevo()))).toEqual(items);
  });

  it("cerrado con un fallo en medio: las dos fichas del fallo", () => {
    let e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    for (const i of items) e = tocar(tocar(e, "izq", i), "der", i);
    expect(e.terminado).toBe(true);
    expect(ids(e)).toEqual(["ja:kana:か", "ja:kana:き"]);
  });

  it("sin tiempo: las que faltan y las que se cerraron tras fallar, y no las limpias", () => {
    let e = nuevo();
    e = tocar(tocar(e, "izq", "ja:kana:か"), "der", "ja:kana:か"); // limpia
    e = tocar(tocar(e, "izq", "ja:kana:き"), "der", "ja:kana:く"); // falla き y く
    e = tocar(tocar(e, "izq", "ja:kana:き"), "der", "ja:kana:き"); // cierra き, ya fallada
    expect(ids(seAcaboElTiempo(e))).toEqual(["ja:kana:き", "ja:kana:く"]);
  });

  it("van en el orden de la columna izquierda, que es el que se ve en pantalla", () => {
    const e = seAcaboElTiempo(inicialTablero([items[2], items[0], items[1]], items));
    expect(ids(e)).toEqual([items[2], items[0], items[1]]);
  });

  it("son exactamente las que evidenciasTablero marca como fallo", () => {
    let e = nuevo();
    e = tocar(tocar(e, "izq", "ja:kana:か"), "der", "ja:kana:き");
    e = tocar(tocar(e, "izq", "ja:kana:く"), "der", "ja:kana:く");
    e = seAcaboElTiempo(e);
    const falladas = evidenciasTablero(c, e, 0).filter((x) => !x.acierto).map((x) => x.item);
    expect(ids(e).sort()).toEqual(falladas.sort());
  });
});
