import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../api/client";
import type { RejectedLine, TallerCard } from "../lib/tallerParse";
import { parse } from "../lib/tallerParse";
import { loadDraft, saveDraft, truncatePaste } from "../lib/tallerDraft";
import type { TallerOverview } from "../api/types";

const DRAFT_DEBOUNCE_MS = 400;
const MAX_TAGS = 10;

type Mode = "compose" | "review";

// Fila de previsualización en orden de renderizado: una tarjeta que se va a
// guardar, o un rechazo de "un solo TAB, un lado vacío" que el mockup muestra
// inline como incompleta (`sin reverso — no se guarda`) en vez de mandarlo a
// la lista de rechazos separada.
type PreviewRow = { kind: "card"; card: TallerCard } | { kind: "bad"; front: string };

function isSingleTabEmptySide(line: RejectedLine): { front: string } | null {
  const parts = line.text.split("\t");
  if (parts.length !== 2) return null;
  const front = parts[0].trim();
  const back = parts[1].trim();
  if (front !== "" && back === "") return { front };
  return null;
}

// ponytail: el mockup interleava buenas/incompletas en su posición original
// de línea; tallerParse.ts no devuelve el número de línea por tarjeta (no lo
// pide su contrato), así que acá se muestran las buenas primero y las
// incompletas después, no en la posición exacta del textarea. Cosmético —
// upgrade si Iris lo pide en un re-gate.
function buildPreviewRows(cards: TallerCard[], rejected: RejectedLine[]): PreviewRow[] {
  const bad = rejected.map(isSingleTabEmptySide).filter((x): x is { front: string } => x !== null);
  return [
    ...cards.map((card): PreviewRow => ({ kind: "card", card })),
    ...bad.map((b): PreviewRow => ({ kind: "bad", front: b.front })),
  ];
}

// Rechazos "duros" (0 o 2+ TABs): la contraparte de arriba, para la lista
// separada con número de línea. "1 TAB, lado vacío" ya se mostró inline.
function hardRejections(rejected: RejectedLine[]): RejectedLine[] {
  return rejected.filter((line) => isSingleTabEmptySide(line) === null);
}

export default function Taller() {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [addingTag, setAddingTag] = useState(false);
  const [newTag, setNewTag] = useState("");
  const [overview, setOverview] = useState<TallerOverview | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [pasteNotice, setPasteNotice] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>("compose");
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tagInputRef = useRef<HTMLInputElement | null>(null);

  const refreshOverview = useCallback(() => {
    api
      .tallerOverview()
      .then(setOverview)
      .catch((err) => console.error("taller.overview", err));
  }, []);

  useEffect(() => {
    setText(loadDraft(window.localStorage));
    refreshOverview();
  }, [refreshOverview]);

  useEffect(() => {
    if (addingTag) tagInputRef.current?.focus();
  }, [addingTag]);

  const { cards, rejected, overflow } = useMemo(() => parse(text), [text]);
  const previewRows = useMemo(() => buildPreviewRows(cards, rejected), [cards, rejected]);
  const separateRejections = useMemo(() => hardRejections(rejected), [rejected]);

  function updateText(next: string) {
    setText(next);
    if (draftTimer.current) clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      saveDraft(next, window.localStorage);
    }, DRAFT_DEBOUNCE_MS);
  }

  function handleTextareaChange(e: ChangeEvent<HTMLTextAreaElement>) {
    const raw = e.target.value;
    const { text: cut, droppedLines } = truncatePaste(raw);
    setPasteNotice(droppedLines > 0 ? droppedLines : null);
    updateText(cut);
  }

  function commitNewTag() {
    const value = newTag.trim().toLowerCase();
    setNewTag("");
    setAddingTag(false);
    if (value === "" || tags.includes(value) || tags.length >= MAX_TAGS) return;
    setTags((prev) => [...prev, value]);
  }

  function removeTag(tag: string) {
    setTags((prev) => prev.filter((x) => x !== tag));
  }

  async function handleSave() {
    if (cards.length === 0 || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      const batchId = crypto.randomUUID();
      await api.createTallerCardsBulk(cards, tags, batchId);
      // Solo quedan las líneas que no se guardaron: rechazadas + sobrante.
      const remainder = [...rejected.map((r) => r.text), overflow].filter((s) => s !== "").join("\n");
      updateText(remainder);
      setTags([]);
      refreshOverview();
    } catch (err) {
      console.error("taller.save", err);
      setSaveError(
        err instanceof ApiError && err.status === 422
          ? t("taller.errors.invalid")
          : t("taller.errors.saveFailed"),
      );
    } finally {
      setSaving(false);
    }
  }

  const isEmpty = text.trim() === "";
  const incompletas = previewRows.filter((r) => r.kind === "bad").length;

  // El campo y la entrada de etiqueta son los mismos en los dos estados de
  // composición (vacío y con texto): un control, no dos copias.
  const campo = (
    <div className="k-field k-field--area">
      <label className="k-field__label" htmlFor="taller-texto">
        {t("taller.compose.label")}
      </label>
      <textarea
        id="taller-texto"
        className="k-field__input"
        spellCheck={false}
        placeholder={t("taller.compose.placeholder")}
        value={text}
        onChange={handleTextareaChange}
      />
    </div>
  );

  // La etiqueta en edición ya tiene la forma del chip que va a ser.
  const entradaEtiqueta = (
    <input
      ref={tagInputRef}
      className="k-chip"
      value={newTag}
      onChange={(e) => setNewTag(e.target.value)}
      onBlur={commitNewTag}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          commitNewTag();
        }
      }}
    />
  );

  const botonAnadir = (
    <button type="button" className="k-chip" onClick={() => setAddingTag(true)}>
      {t("taller.compose.addChip")}
    </button>
  );

  return (
    <>
      <div className="k-desk__gate">
        <p className="k-note k-note--bare">{t("taller.gate.message")}</p>
      </div>

      <main className="k-desk">
        <header className="k-topline">
          <span className="k-hero k-hero--quiet">
            <h1 className="k-hero__title">{t("taller.entry.link")}</h1>
          </span>
          <p className="k-topline__meta">
            {overview
              ? t("taller.masthead.total", { count: overview.total })
              : t("common.loading")}
            {overview && overview.due > 0 && (
              <>
                {" · "}
                <button
                  type="button"
                  className="k-btn k-btn--text"
                  onClick={() => setMode("review")}
                >
                  {t("taller.masthead.due", { count: overview.due })}
                </button>
              </>
            )}
          </p>
        </header>

        <aside className="k-desk__rail">
          <h2 className="k-cap">{t("taller.rail.tagsTitle")}</h2>
          <ul>
            <li>
              <button type="button" className="k-row" data-state="selected" disabled>
                <span className="k-row__title">{t("taller.rail.all")}</span>
              </button>
            </li>
            {/* ponytail: solo lectura en F0 — filtrar por etiqueta desde el
                riel es gramática de interacción, diferida a Petra (F2). El
                <button> inerte matchea el markup del mockup a la espera de ese
                cableado; el `:disabled` del átomo 4 lo deja igual que en reposo
                a propósito (una fila inerte no debe parecer rota). */}
            {overview?.tags.map((tc) => (
              <li key={tc.tag}>
                <button type="button" className="k-row" disabled>
                  <span className="k-row__title">{tc.tag}</span>
                  <span className="k-row__meta">{tc.count}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {mode === "review" ? (
          <div className="k-desk__col">
            {/* ponytail: la vista real del repaso es la Task 4.2 de PR4 —
                máquina de modos excluyentes ya en pie, contenido llega en el
                próximo PR. Nadie fuera de la allowlist ve este estado. */}
            <p className="k-note">{t("taller.review.comingSoon")}</p>
            <div className="k-wrap">
              <button type="button" className="k-btn" onClick={() => setMode("compose")}>
                {t("taller.review.back")}
              </button>
            </div>
          </div>
        ) : isEmpty ? (
          <div className="k-desk__col">
            {campo}
            <div className="k-wrap">{addingTag ? entradaEtiqueta : botonAnadir}</div>

            <hr className="k-hairline" />

            {/* Con la mesa vacía el repaso es el sujeto, no la marginalia. */}
            <div className="k-hero k-hero--quiet">
              <span className="k-hero__tag">
                {overview ? t("taller.empty.saved", { count: overview.total }) : ""}
              </span>
              <p className="k-hero__title">
                {overview && overview.due > 0
                  ? t("taller.empty.call", { count: overview.due })
                  : t("taller.empty.callNone")}
              </p>
            </div>
            {overview && overview.due > 0 && (
              <div className="k-wrap">
                <button type="button" className="k-btn" onClick={() => setMode("review")}>
                  {t("taller.empty.review")}
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="k-desk__col">
            {campo}

            {pasteNotice !== null && (
              <p className="k-error">
                {t("taller.compose.pasteTruncated", { count: pasteNotice })}
              </p>
            )}

            <div className="k-wrap">
              {tags.map((tag) => (
                <button key={tag} type="button" className="k-chip" onClick={() => removeTag(tag)}>
                  {tag}
                  <span className="k-chip__x" aria-label={t("taller.compose.removeChip", { tag })}>
                    ×
                  </span>
                </button>
              ))}
              {addingTag ? entradaEtiqueta : tags.length < MAX_TAGS && botonAnadir}
            </div>

            <h2 className="k-cap k-cap--rule">
              <span>{t("taller.compose.preview.count", { count: cards.length })}</span>
              {incompletas > 0 && (
                <span className="k-chip k-chip--static" data-tone="bad">
                  <span className="k-chip__dot" aria-hidden="true" />
                  {t("taller.compose.preview.incomplete", { count: incompletas })}
                </span>
              )}
            </h2>
            <ul>
              {previewRows.map((row, i) => (
                <li key={i}>
                  <div
                    className="k-row k-row--quiet"
                    data-empty={row.kind === "bad" ? "true" : undefined}
                  >
                    <span className="k-row__title">
                      {row.kind === "card" ? row.card.front : row.front}
                    </span>
                    <span className="k-row__sub">
                      {row.kind === "card" ? row.card.back : t("taller.compose.preview.noBack")}
                    </span>
                  </div>
                </li>
              ))}
            </ul>

            {separateRejections.length > 0 && (
              <ul className="k-error">
                {separateRejections.map((r) => (
                  <li key={r.line}>{t("taller.rejected.line", { line: r.line, text: r.text })}</li>
                ))}
              </ul>
            )}

            {saveError && (
              <p className="k-error" role="alert">
                {saveError}
              </p>
            )}

            <div className="k-wrap">
              <kbd className="k-chip k-chip--static">⌘↵</kbd>
              <button
                type="button"
                className="k-btn"
                disabled={cards.length === 0 || saving}
                onClick={handleSave}
              >
                {t("taller.compose.save", { count: cards.length })}
              </button>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
