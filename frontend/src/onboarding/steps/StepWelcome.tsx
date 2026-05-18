import KlaraMark from "../../components/KlaraMark";

interface Props {
  next: () => void;
}

export default function StepWelcome({ next }: Props) {
  return (
    <div className="ob-welcome">
      <div className="ob-welcome__mark">
        <KlaraMark size={140} speaking />
      </div>
      <h1 className="ob-welcome__hello">Hola.</h1>
      <p className="ob-welcome__lede">
        Me llamo Klara. Cada día te traigo una historia corta para leer, pronunciar y conversar.
      </p>
      <ul className="ob-welcome__triad">
        <li><span className="k-mono">I</span> Lectura</li>
        <li><span className="k-mono">II</span> Pronunciación</li>
        <li><span className="k-mono">III</span> Conversación</li>
      </ul>
      <p className="ob-welcome__sub k-serif">
        Antes, déjame conocerte. Son cinco preguntas.
      </p>

      <div className="ob-welcome__cta">
        <button type="button" className="ob-btn ob-btn--lg" onClick={next} autoFocus>
          <span>Empezar</span>
          <span className="ob-btn__arrow k-serif">→</span>
        </button>
        <span className="k-mono ob-welcome__tip">o pulsa Enter</span>
      </div>
    </div>
  );
}
