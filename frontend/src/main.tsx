import React from "react";
import ReactDOM from "react-dom/client";
// Latin subsets only: keeps builds fast and asset churn low (fewer files for
// antivirus/indexers to scan on Windows). Devanagari/Indic glyphs fall back to
// system fonts until a dedicated Indic face is added with the Hindi UI.
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import "@fontsource/cinzel/latin-600.css";
import "@fontsource/cinzel/latin-700.css";
import "./index.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// PWA: offline shell + asset cache. Only in production builds.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/app/sw.js", { scope: "/" }).catch(() => {
      // registration is best-effort; the app works without it
    });
  });
}
