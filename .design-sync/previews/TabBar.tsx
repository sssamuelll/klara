import { TabBar } from "klara-frontend";

// La barra de pestañas del cascarón móvil. Lee la ruta activa del router y
// pinta el destino actual con el borde inferior en tinta. Vive pegada al fondo
// de .m3-app, con altura 58px + el inset de la zona segura.

// Se enmarca en el ancho real del teléfono (430px es el máximo de .m3-app):
// suelta a ancho completo no se lee como lo que es.
const Telefono = ({ children }: { children: React.ReactNode }) => (
  <div
    style={{
      width: 390,
      border: "1px solid var(--rule)",
      background: "var(--paper)",
      display: "flex",
      flexDirection: "column",
      justifyContent: "flex-end",
      height: 180,
    }}
  >
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: 15, color: "var(--ink-4)" }}>
      contenido de la pantalla
    </div>
    {children}
  </div>
);

export const EnLaBiblioteca = () => (
  <div style={{ padding: 24 }}>
    <Telefono>
      <TabBar />
    </Telefono>
  </div>
);
