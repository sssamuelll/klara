import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./i18n";
import App from "./App";
import "./styles/global.css";
import "./styles/native.css";
import "./styles/onboarding.css";
import "./styles/sentence-view.css";
import "./styles/finish.css";
import "./styles/speak.css";
import "./styles/path.css";
import "./styles/mobile3.css";
import "./styles/mobile4.css";
import "./styles/perfil-aprendizaje.css";
import "./styles/auth.css";
import "./styles/landing.css";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Root element not found");

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
