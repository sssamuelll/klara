import { KlaraMark } from "klara-frontend";

// El monograma. Es lo único vivo de la interfaz: cuando Klara habla, late a
// --dur-breath (1600ms) con un halo en --accent-wash. Serif cursiva, sobre el
// papel — nunca sobre blanco, que es donde pierde el tono cálido del sistema.

const Papel = ({ children }: { children: React.ReactNode }) => (
  <div
    style={{
      background: "var(--paper)",
      padding: "36px 40px",
      display: "flex",
      alignItems: "center",
      gap: 24,
      minHeight: 96,
    }}
  >
    {children}
  </div>
);

const Etiqueta = ({ children, acento }: { children: React.ReactNode; acento?: boolean }) => (
  <span
    style={{
      fontFamily: "var(--font-mono)",
      fontSize: 11,
      letterSpacing: "0.08em",
      textTransform: "uppercase",
      color: acento ? "var(--accent)" : "var(--ink-3)",
    }}
  >
    {children}
  </span>
);

export const Reposo = () => (
  <Papel>
    <KlaraMark size={40} />
    <Etiqueta>en reposo</Etiqueta>
  </Papel>
);

export const Hablando = () => (
  <Papel>
    <KlaraMark size={40} speaking />
    <Etiqueta acento>hablando — el halo late a 1600ms</Etiqueta>
  </Papel>
);

export const Escala = () => (
  <Papel>
    {[16, 24, 40, 72].map((s) => (
      <span key={s} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
        <KlaraMark size={s} />
        <Etiqueta>{s}px</Etiqueta>
      </span>
    ))}
  </Papel>
);

export const CursivaYRecta = () => (
  <Papel>
    <span style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
      <KlaraMark size={64} />
      <Etiqueta>cursiva (por defecto)</Etiqueta>
    </span>
    <span style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
      <KlaraMark size={64} italic={false} />
      <Etiqueta>recta</Etiqueta>
    </span>
  </Papel>
);
