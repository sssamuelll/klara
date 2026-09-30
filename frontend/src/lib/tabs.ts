export type Tab = "hoy" | "biblioteca" | "mas";

/** La pestaña activa de cada ruta (spec §1.1). `/nuevo` se abre desde la estantería. */
export function tabActiva(pathname: string): Tab | null {
  if (pathname === "/") return "hoy";
  if (pathname === "/biblioteca" || pathname === "/nuevo" || pathname.startsWith("/curso/")) {
    return "biblioteca";
  }
  if (pathname.startsWith("/perfil")) return "mas";
  return null;
}
