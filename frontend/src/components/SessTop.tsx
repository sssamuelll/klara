import { useTranslation } from "react-i18next";

interface Props {
  titulo: string;
  right: string;
  onExit: () => void;
}

export default function SessTop({ titulo, right, onExit }: Props) {
  const { t } = useTranslation();
  return (
    <div className="m3-sess-top">
      <button className="m3-back" onClick={onExit}>{t("common.exit")}</button>
      <span className="titulo">{titulo}</span>
      <span className="der">{right}</span>
    </div>
  );
}
