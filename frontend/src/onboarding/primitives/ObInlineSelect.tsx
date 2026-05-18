import { useEffect, useRef, useState } from "react";

export interface InlineSelectOption<T extends string> {
  code: T;
  label: string;
  sub?: string;
}

interface Props<T extends string> {
  value: T;
  options: InlineSelectOption<T>[];
  onChange: (value: T) => void;
}

/**
 * Inline dropdown that reads as part of flowing text (used in the language
 * sentence). Not a native <select> on purpose — the trigger inherits the
 * surrounding type style so it looks like the underlined word.
 */
export default function ObInlineSelect<T extends string>({
  value,
  options,
  onChange,
}: Props<T>) {
  const current = options.find((o) => o.code === value) ?? options[0];
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span className="ob-isel" ref={wrapRef}>
      <button
        type="button"
        className="ob-isel__trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{current.label}</span>
        <span className="ob-isel__caret k-serif">▾</span>
      </button>
      {open && (
        <ul className="ob-isel__menu" role="listbox">
          {options.map((o) => (
            <li key={o.code}>
              <button
                type="button"
                className="ob-isel__opt"
                data-active={o.code === value}
                onClick={() => {
                  onChange(o.code);
                  setOpen(false);
                }}
              >
                <span className="ob-isel__opt-label">{o.label}</span>
                {o.sub && <span className="k-mono ob-isel__opt-sub">{o.sub}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </span>
  );
}
