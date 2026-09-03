import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import OwnerPasswordGate from "./OwnerPasswordGate";

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();

  if (loading) {
    return (
      <main className="k-page">
        <span className="k-spinner" role="status" aria-label={t("common.loading")} />
      </main>
    );
  }

  if (user === null) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (user.needs_onboarding && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }

  if (!user.needs_onboarding && location.pathname === "/onboarding") {
    return <Navigate to="/" replace />;
  }

  if (
    !user.needs_onboarding &&
    user.is_superuser &&
    !user.auth_methods.includes("password")
  ) {
    return <OwnerPasswordGate />;
  }

  return <>{children}</>;
}
