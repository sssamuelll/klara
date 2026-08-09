import { describe, expect, it } from "vitest";
import { acumular, iniciarReloj } from "./timings";

/** Reloj falso: avanza solo cuando el test lo dice. */
function crono() {
  let t = 0;
  return { ahora: () => t, avanzar: (ms: number) => (t += ms) };
}

describe("iniciarReloj", () => {
  it("mide el tiempo transcurrido", () => {
    const c = crono();
    const r = iniciarReloj(c.ahora);
    c.avanzar(4200);
    expect(r.cerrar()).toBe(4200);
  });

  it("descuenta el tiempo con la pestaña oculta", () => {
    // El caso del café: 3s leyendo, 7 min fuera, 2s decidiendo. Sin descontar,
    // esta pregunta parecería la más cara del cuestionario y la poda de #138
    // la marcaría para eliminar por una razón falsa.
    const c = crono();
    const r = iniciarReloj(c.ahora);
    c.avanzar(3000);
    r.pausar();
    c.avanzar(420000);
    r.reanudar();
    c.avanzar(2000);
    expect(r.cerrar()).toBe(5000);
  });

  it("cierra bien aunque la pestaña siga oculta", () => {
    const c = crono();
    const r = iniciarReloj(c.ahora);
    c.avanzar(1000);
    r.pausar();
    c.avanzar(60000);
    expect(r.cerrar()).toBe(1000);
  });

  it("ignora un reanudar sin pausar previo", () => {
    const c = crono();
    const r = iniciarReloj(c.ahora);
    c.avanzar(500);
    r.reanudar();
    c.avanzar(500);
    expect(r.cerrar()).toBe(1000);
  });

  it("no cuenta dos veces si se pausa dos veces seguidas", () => {
    const c = crono();
    const r = iniciarReloj(c.ahora);
    c.avanzar(1000);
    r.pausar();
    c.avanzar(5000);
    r.pausar();
    c.avanzar(5000);
    r.reanudar();
    c.avanzar(1000);
    expect(r.cerrar()).toBe(2000);
  });

  it("topea a 300 s: por encima es ruido, no señal", () => {
    const c = crono();
    const r = iniciarReloj(c.ahora);
    c.avanzar(999999);
    expect(r.cerrar()).toBe(300000);
  });
});

describe("acumular", () => {
  it("suma al volver atrás en vez de pisar", () => {
    // Lo que se quiere medir es el costo TOTAL de la pregunta, no el último
    // tramo: quien vuelve tres veces a una pregunta la está pagando cara.
    let t: Record<string, number> = {};
    t = acumular(t, "ses_duracion", 1200);
    t = acumular(t, "ses_duracion", 800);
    expect(t.ses_duracion).toBe(2000);
  });

  it("no mezcla preguntas", () => {
    let t: Record<string, number> = {};
    t = acumular(t, "a", 100);
    t = acumular(t, "b", 250);
    expect(t).toEqual({ a: 100, b: 250 });
  });

  it("mantiene el tope al acumular", () => {
    let t: Record<string, number> = { q: 299000 };
    t = acumular(t, "q", 50000);
    expect(t.q).toBe(300000);
  });
});
