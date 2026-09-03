import ObStep from "../primitives/ObStep";

interface Props {
  next: () => void;
}

const TRIADA = [
  { n: "I", t: "Lectura" },
  { n: "II", t: "Pronunciación" },
  { n: "III", t: "Conversación" },
];

export default function StepWelcome({ next }: Props) {
  return (
    <ObStep
      nav={
        <>
          <div className="k-wrap">
            <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={next} autoFocus>
              Empezar <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          </div>
          <p className="k-note k-note--bare">o pulsa Enter</p>
        </>
      }
    >
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">Hola.</h1>
        <p className="k-hero__dek">
          Me llamo Klara. Cada día te traigo una historia corta para leer, pronunciar y conversar.
        </p>
      </header>

      <hr className="k-hairline" />
      <ul>
        {TRIADA.map((x) => (
          <li key={x.n} className="k-row k-row--quiet">
            <span className="k-row__n">{x.n}</span>
            <span className="k-row__title">{x.t}</span>
          </li>
        ))}
      </ul>
      <hr className="k-hairline" />

      <p className="k-note">Antes, déjame conocerte. Son cinco preguntas.</p>
    </ObStep>
  );
}
