import { useTranslation } from "react-i18next";

interface Props {
  titulo: string;
  /** El código de idioma cuando el título entero está en el idioma de estudio (`ja`, `de`…). */
  tituloLang?: string;
  right: string;
  onExit: () => void;
}

export default function SessTop({ titulo, tituloLang, right, onExit }: Props) {
  const { t } = useTranslation();
  return (
    <header className="k-topline k-topline--session">
      <button type="button" className="k-btn k-btn--text k-topline__exit" onClick={onExit}>
        {t("common.exit")}
      </button>
      <span className="k-topline__title" lang={tituloLang}>{titulo}</span>
      <span className="k-topline__meta">{right}</span>
    </header>
  );
}
