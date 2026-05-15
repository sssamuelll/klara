import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

export default function ChatStub() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return (
    <main className="k-page placeholder">
      <button className="story__back k-mono" onClick={() => navigate("/")}>
        {t("common.back")}
      </button>
      <div className="ph__head">
        <span className="k-mono">{t("stub.chat.kicker")}</span>
        <h1 className="ph__title">{t("stub.chat.title")}</h1>
        <p className="ph__dek">{t("stub.chat.dek")}</p>
      </div>
    </main>
  );
}
