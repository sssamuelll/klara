import { useTranslation } from "react-i18next";

export default function RecordingBar() {
  const { t } = useTranslation();
  return (
    <div className="recbar" role="status" aria-live="polite">
      <span className="recbar__dot" />
      <span className="recbar__bars" aria-hidden="true">
        {Array.from({ length: 18 }).map((_, i) => (
          <span
            key={i}
            className="recbar__bar"
            style={{ animationDelay: `${i * 60}ms` }}
          />
        ))}
      </span>
      <span className="recbar__label k-mono">{t("recbar.listening")}</span>
    </div>
  );
}
