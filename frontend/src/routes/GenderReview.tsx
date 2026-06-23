import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import GenderReviewSession from "../components/GenderReviewSession";

export default function GenderReview(): JSX.Element {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return <GenderReviewSession onExit={() => navigate("/")} exitLabel={t("genderReview.home")} />;
}
