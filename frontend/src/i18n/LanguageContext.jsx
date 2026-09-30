import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  LANGUAGES,
  translateLocal,
} from "./translations";

const STORAGE_KEY = "disaster_ai_language";
const LanguageContext = createContext(null);

function isSupportedLanguage(code) {
  return LANGUAGES.some((item) => item.code === code);
}

function readSavedLanguage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return isSupportedLanguage(saved) ? saved : "en";
  } catch {
    return "en";
  }
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(readSavedLanguage);

  const setLanguage = useCallback((code) => {
    const next = isSupportedLanguage(code) ? code : "en";
    setLanguageState(next);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch {
      // Local storage may be unavailable in private/restricted browsers.
    }

    document.documentElement.lang = language;
    document.documentElement.dir =
      language === "ur" || language === "ks" ? "rtl" : "ltr";
  }, [language]);

  const t = useCallback(
    (text) => translateLocal(text, language),
    [language]
  );

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      languages: LANGUAGES,
      t,
    }),
    [language, setLanguage, t]
  );

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const value = useContext(LanguageContext);

  if (!value) {
    throw new Error(
      "useLanguage must be used inside LanguageProvider"
    );
  }

  return value;
}
