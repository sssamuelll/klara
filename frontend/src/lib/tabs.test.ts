import { describe, expect, it } from "vitest";
import { tabActiva } from "./tabs";

describe("tabActiva", () => {
  it.each([
    ["/", "hoy"],
    ["/biblioteca", "biblioteca"],
    ["/curso/aleman", "biblioteca"],
    ["/curso/aleman/mapa", "biblioteca"],
    ["/nuevo", "biblioteca"],
    ["/perfil", "mas"],
    ["/perfil/aprendizaje", "mas"],
    ["/estudiar/s1", null],
  ])("%s → %s", (ruta, tab) => {
    expect(tabActiva(ruta)).toBe(tab);
  });
});
