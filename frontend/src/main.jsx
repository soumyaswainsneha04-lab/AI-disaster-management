import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";

import "leaflet/dist/leaflet.css";
import "./index.css";

import App from "./App.jsx";
import { LanguageProvider } from "./i18n/LanguageContext.jsx";
import GlobalTranslator from "./components/GlobalTranslator.jsx";

registerSW({
  immediate: true,

  onOfflineReady() {
    console.info(
      "Disaster AI India app shell is ready for offline use."
    );
  },

  onRegisteredSW(swUrl) {
    console.info(
      "Disaster AI India service worker registered:",
      swUrl
    );
  },

  onRegisterError(error) {
    console.error(
      "Service worker registration failed:",
      error
    );
  },
});

createRoot(
  document.getElementById("root")
).render(
  <StrictMode>
    <LanguageProvider>
      <GlobalTranslator>
        <App />
      </GlobalTranslator>
    </LanguageProvider>
  </StrictMode>
);
