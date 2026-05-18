interface Props {
  onPrev?: () => void;
  onNext?: () => void;
  onSkip?: () => void;
  canNext: boolean;
  nextLabel?: string;
  skipLabel?: string;
  submitting?: boolean;
}

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
    <nav className="ob-nav">
      <div className="ob-nav__left">
        {onPrev && (
          <button type="button" className="ob-link" onClick={onPrev} disabled={submitting}>
            <span className="k-serif ob-link__arrow">←</span> Atrás
          </button>
        )}
      </div>
      <div className="ob-nav__right">
        {onSkip && skipLabel && (
          <button
            type="button"
            className="ob-link ob-link--mute"
            onClick={onSkip}
            disabled={submitting}
          >
            {skipLabel}
          </button>
        )}
        <button
          type="button"
          className="ob-btn"
          onClick={onNext}
          disabled={!canNext || submitting}
        >
          <span>{nextLabel}</span>
          <span className="ob-btn__arrow k-serif">→</span>
        </button>
      </div>
    </nav>
  );
}
