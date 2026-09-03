// Entrada para design-sync. Klara es una app, no una librería: sus componentes
// son `export default`, y el modo synth del convertidor hace `export * from`,
// que no reexporta defaults. Este barrel los vuelve nombrados para el bundle.
// No es una reimplementación: reexporta los componentes reales tal cual.

// Estilos en el MISMO orden que main.tsx, para que esbuild los empaquete igual
// que la app real. global.css arrastra tokens.css y pages.css por @import.
import "./src/styles/global.css";
import "./src/styles/sistema.css";
import "./src/styles/native.css";
import "./src/styles/path.css";

import "./src/i18n"; // efecto de módulo: deja i18next inicializado

// Proveedor para las previews: casi todo componente de Klara lee el router.
// No es un componente del sistema (no está en componentSrcMap, así que no
// genera tarjeta); existe solo para que cfg.provider tenga a qué apuntar.
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
export function DesignPreviewProvider({ children }: { children?: ReactNode }) {
  return <MemoryRouter initialEntries={["/"]}>{children}</MemoryRouter>;
}

export { default as BreakdownPopover } from "./src/components/BreakdownPopover";
export { default as EstudiarView } from "./src/components/EstudiarView";
export { default as GenderPicker } from "./src/components/GenderPicker";
export { default as GenderReviewSession } from "./src/components/GenderReviewSession";
export { default as InvitationsPanel } from "./src/components/InvitationsPanel";
export { default as KlaraMark } from "./src/components/KlaraMark";
export { default as Masthead } from "./src/components/Masthead";
export { default as OwnerPasswordGate } from "./src/components/OwnerPasswordGate";
export { default as PasswordSetForm } from "./src/components/PasswordSetForm";
export { default as SessTop } from "./src/components/SessTop";
export { default as StoryFinish } from "./src/components/StoryFinish";
export { default as TabBar } from "./src/components/TabBar";
export { default as WordPopover } from "./src/components/WordPopover";
