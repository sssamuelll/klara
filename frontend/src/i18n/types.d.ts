import "react-i18next";
import type es from "../locales/es/common.json";

declare module "react-i18next" {
  interface CustomTypeOptions {
    defaultNS: "common";
    resources: { common: typeof es };
  }
}
