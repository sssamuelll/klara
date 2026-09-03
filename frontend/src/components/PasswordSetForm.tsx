import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import { api } from "../api/client";

export interface PasswordSetFormProps {
  onSuccess?: () => void;
  submitLabel?: string;
}

export default function PasswordSetForm({ onSuccess, submitLabel }: PasswordSetFormProps) {
  const { t } = useTranslation();
  const { applyUserResponse } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const localValid = password.length >= 8 && password === confirm;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!localValid) {
      setError(
        password !== confirm
          ? t("onboarding.password.mismatch")
          : t("onboarding.password.tooShort"),
      );
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const updated = await api.setPassword(password);
      applyUserResponse(updated);
      setPassword("");
      setConfirm("");
      onSuccess?.();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : t("common.unknownError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      {error && <p className="k-error" role="alert">{error}</p>}
      <label className="k-field" data-error={error ? true : undefined}>
        <span className="k-field__label">{t("onboarding.password.label")}</span>
        <input
          className="k-field__input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          disabled={submitting}
        />
      </label>
      <label className="k-field" data-error={error ? true : undefined}>
        <span className="k-field__label">{t("onboarding.password.confirm")}</span>
        <input
          className="k-field__input"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          disabled={submitting}
        />
      </label>
      <div className="k-wrap">
        <button
          type="submit"
          className="k-btn"
          disabled={submitting || !localValid}
          aria-busy={submitting}
        >
          {submitting ? (
            <span className="k-spinner" />
          ) : (
            (submitLabel ?? t("onboarding.password.submit"))
          )}
        </button>
      </div>
    </form>
  );
}
