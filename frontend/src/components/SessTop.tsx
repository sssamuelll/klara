import { useTranslation } from "react-i18next";

interface Props {
  titulo: string;
  right: string;
  onExit: () => void;
}

export default function SessTop({ titulo, right, onExit }: Props) {
  const { t } = useTranslation();
  return (
    <header className="k-topline k-topline--session">
      <button type="button" className="k-btn k-btn--text k-topline__exit" onClick={onExit}>
        {t("common.exit")}
      </button>
      <span className="k-topline__title">{titulo}</span>
      <span className="k-topline__meta">{right}</span>
    </header>
  );
}
