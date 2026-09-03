import { useEffect } from "react";

export interface InlineSelectOption<T extends string> {
  code: T;
  label: string;
  sub?: string;
}

interface TriggerProps<T extends string> {
  value: T;
  options: InlineSelectOption<T>[];
  open: boolean;
  onOpen: () => void;
}

/**
 * La palabra elegible dentro de la frase. Sigue leyéndose como parte del
 * renglón —es una `.k-word` del pasaje, con su área táctil de 44px y su fondo
 * de «de esta estamos hablando» mientras está abierta—, y el cursor «▾» es la
 * afordancia: sin `:hover` no hay otra manera de decir que se toca.
 *
 * El desplegable NO vive aquí: `.k-sheet` es armazón que se posiciona contra
 * `.k-app`, y meterlo dentro del `<p class="k-stage">` lo convertía en un ítem
 * más de su `-webkit-box` y partía la frase en pedazos verticales (medido).
 * Lo pinta `ObSelectSheet`, hermano del pasaje.
 */
export function ObInlineTrigger<T extends string>({
  value,
  options,
  open,
  onOpen,
}: TriggerProps<T>) {
  const current = options.find((o) => o.code === value) ?? options[0];
  return (
    <button
      type="button"
      className="k-word"
      data-matched="true"
      data-active={open ? "true" : undefined}
      onClick={onOpen}
      aria-haspopup="listbox"
      aria-expanded={open}
    >
      {current.label}
      <span aria-hidden="true"> ▾</span>
    </button>
  );
}

interface SheetProps<T extends string> {
  title: string;
  value: T;
  options: InlineSelectOption<T>[];
  onChange: (value: T) => void;
  onClose: () => void;
}

/** La hoja inferior del sistema (átomo 9) con las opciones como filas. */
export function ObSelectSheet<T extends string>({
  title,
  value,
  options,
  onChange,
  onClose,
}: SheetProps<T>) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="k-scrim" onClick={onClose} />
      <div className="k-sheet" role="dialog" aria-label={title}>
        <span className="k-sheet__grab" aria-hidden="true" />
        <div className="k-sheet__head">
          <p className="k-cap">{title}</p>
        </div>
        <div className="k-sheet__body">
          <ul role="listbox">
            {options.map((o) => (
              <li key={o.code}>
                <button
                  type="button"
                  role="option"
                  aria-selected={o.code === value}
                  className="k-row"
                  data-state={o.code === value ? "selected" : undefined}
                  onClick={() => {
                    onChange(o.code);
                    onClose();
                  }}
                >
                  <span className="k-row__title">{o.label}</span>
                  {o.sub && <span className="k-row__meta">{o.sub}</span>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
