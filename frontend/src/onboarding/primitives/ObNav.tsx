interface Props {
  onPrev?: () => void;
  onNext?: () => void;
  onSkip?: () => void;
  canNext: boolean;
  nextLabel?: string;
  skipLabel?: string;
  submitting?: boolean;
}

/**
 * La fila de transporte del capítulo. Vive dentro del `.k-dock` de `ObStep`:
 * una sola nube (`.k-wrap`) con los dos controles en mono a la izquierda y el
 * botón de avanzar ocupando lo que sobra. Cuando no hay atrás ni saltar —el
 * primer capítulo—, el botón se queda con la fila entera.
 */
export default function ObNav({
  onPrev,
  onNext,
  onSkip,
  canNext,
  nextLabel = "Continuar",
  skipLabel,
  submitting = false,
}: Props) {
  return (
    <div className="k-wrap">
      {onPrev && (
        <button type="button" className="k-btn k-btn--text" onClick={onPrev} disabled={submitting}>
          ← Atrás
        </button>
      )}
      {onSkip && skipLabel && (
        <button type="button" className="k-btn k-btn--text" onClick={onSkip} disabled={submitting}>
          {skipLabel}
        </button>
      )}
      <button
        type="button"
        className="k-btn k-btn--lg k-btn--block"
        onClick={onNext}
        disabled={!canNext || submitting}
      >
        {nextLabel} <span className="k-btn__arrow" aria-hidden="true">→</span>
      </button>
    </div>
  );
}
