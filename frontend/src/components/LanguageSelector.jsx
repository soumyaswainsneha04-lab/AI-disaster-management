import { useLanguage } from "../i18n/LanguageContext";

export default function LanguageSelector({ compact = false }) {
  const { language, setLanguage, languages, t } = useLanguage();

  return (
    <label
      className={`language-selector ${compact ? "compact" : ""}`}
    >
      {!compact && <span>{t("Language")}</span>}

      <select
        value={language}
        onChange={(event) => setLanguage(event.target.value)}
        aria-label="Language"
      >
        {languages.map((item) => (
          <option key={item.code} value={item.code}>
            {item.native}
            {item.native !== item.name ? ` · ${item.name}` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
