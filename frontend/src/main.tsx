import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./i18n";
import App from "./App";
import "./styles/global.css";
import "./styles/sistema.css"; // el vocabulario k-*; va justo después de global.css y antes que cualquier hoja de pantalla
import "./styles/native.css";
import "./styles/path.css";
import "./styles/perfil-aprendizaje.css";
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
