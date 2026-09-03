import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** La navegación del capítulo; va al dock, que es donde vive el transporte. */
  nav?: ReactNode;
  /** La marginalia de Klara (`WHISPERS` en data.ts). Vivía en una tercera
   *  columna que desaparecía bajo 860px, o sea en ningún teléfono; ahora cierra
   *  la columna del capítulo como lo que siempre fue: una nota al margen. */
  whisper?: string;
}

/**
 * El cuerpo de un paso dentro del cascarón de sesión: la columna que scrollea
 * y el dock. Es un fragmento a propósito — `.k-fill` y `.k-dock` tienen que ser
 * hermanos e hijos directos de `.k-app`, así que ningún envoltorio puede
 * meterse en medio.
 */
export default function ObStep({ children, nav, whisper }: Props) {
  return (
    <>
      <div className="k-fill">
        <div className="k-live">
          {children}
          {whisper && <p className="k-note">{whisper}</p>}
        </div>
      </div>
      {nav && <div className="k-dock">{nav}</div>}
    </>
  );
}
