import { useEffect, useRef } from "react";
import { apiFetch } from "../api";
import { useLanguage } from "../i18n/LanguageContext";
import { PROTECTED_TEXT, translateLocal } from "../i18n/translations";

const originalText = new WeakMap();
const originalAttributes = new WeakMap();
const remoteCache = new Map();
const CACHE_STORAGE_KEY = "disaster_ai_remote_translation_cache_v2";

const SKIP_SELECTOR = [
  "script",
  "style",
  "code",
  "pre",
  "svg",
  ".language-selector",
  ".leaflet-control-attribution",
  "[data-no-translate]",
  ".user-copy strong",
  ".profile-card > h3",
].join(",");

function normalize(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function isUsefulText(value) {
  const text = normalize(value);
  if (!text) return false;
  if (text.length > 300) return false;
  if (PROTECTED_TEXT.has(text)) return false;
  if (/^https?:\/\//i.test(text)) return false;
  if (/^[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}$/.test(text)) return false;
  if (/^[\d\s.,:%()+\-/#]+$/.test(text)) return false;
  if (!/[A-Za-z]/.test(text)) return false;
  return true;
}

function preserveWhitespace(original, translated) {
  const leading = original.match(/^\s*/)?.[0] || "";
  const trailing = original.match(/\s*$/)?.[0] || "";
  return `${leading}${translated}${trailing}`;
}

function collectTextItems(root) {
  const items = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();

  while (node) {
    const parent = node.parentElement;
    if (parent && !parent.closest(SKIP_SELECTOR)) {
      if (!originalText.has(node)) originalText.set(node, node.nodeValue || "");
      const source = originalText.get(node) || "";
      const clean = normalize(source);
      if (isUsefulText(clean)) items.push({ type: "text", node, source, clean });
    }
    node = walker.nextNode();
  }
  return items;
}

function collectAttributeItems(root) {
  const items = [];
  for (const element of root.querySelectorAll("input, textarea, button, [title], [aria-label]")) {
    if (element.closest(SKIP_SELECTOR)) continue;

    let stored = originalAttributes.get(element);
    if (!stored) {
      stored = {};
      originalAttributes.set(element, stored);
    }

    for (const attribute of ["placeholder", "title", "aria-label"]) {
      if (!element.hasAttribute(attribute)) continue;
      if (!(attribute in stored)) stored[attribute] = element.getAttribute(attribute) || "";

      const source = stored[attribute] || "";
      const clean = normalize(source);
      if (isUsefulText(clean)) {
        items.push({ type: "attribute", element, attribute, source, clean });
      }
    }
  }
  return items;
}

function writeItem(item, translated) {
  if (!translated || !item) return;

  if (item.type === "text" && item.node.isConnected) {
    const desired = preserveWhitespace(item.source, translated);
    if (item.node.nodeValue !== desired) item.node.nodeValue = desired;
    return;
  }

  if (item.type === "attribute" && item.element.isConnected) {
    if (item.element.getAttribute(item.attribute) !== translated) {
      item.element.setAttribute(item.attribute, translated);
    }
  }
}

function restoreEnglish(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();

  while (node) {
    if (originalText.has(node)) {
      const english = originalText.get(node);
      if (node.nodeValue !== english) node.nodeValue = english;
    }
    node = walker.nextNode();
  }

  for (const element of root.querySelectorAll("*")) {
    const stored = originalAttributes.get(element);
    if (!stored) continue;
    for (const [attribute, value] of Object.entries(stored)) {
      if (element.getAttribute(attribute) !== value) element.setAttribute(attribute, value);
    }
  }
}

function loadRemoteCache() {
  try {
    const parsed = JSON.parse(localStorage.getItem(CACHE_STORAGE_KEY) || "{}");
    for (const [key, value] of Object.entries(parsed)) {
      if (value && typeof value === "string") remoteCache.set(key, value);
    }
  } catch {
    // Ignore corrupt/blocked browser storage.
  }
}

function saveRemoteCache() {
  try {
    const object = Object.fromEntries(remoteCache.entries());
    localStorage.setItem(CACHE_STORAGE_KEY, JSON.stringify(object));
  } catch {
    // Translation must never break the application.
  }
}

function cacheKey(language, source) {
  return `${language}::${source}`;
}

function applyLocalTranslations(items, language, translatedMap, remoteNeeded) {
  for (const item of items) {
    const source = item.clean;
    if (PROTECTED_TEXT.has(source)) continue;

    const local = translateLocal(source, language);
    if (local && local !== source) {
      translatedMap.set(source, local);
      continue;
    }

    const cached = remoteCache.get(cacheKey(language, source));
    if (cached && cached !== source) {
      translatedMap.set(source, cached);
      continue;
    }

    remoteNeeded.push(source);
  }
}

function unique(values) {
  return [...new Set(values)];
}

function chunks(values, size = 24) {
  const output = [];
  for (let i = 0; i < values.length; i += size) {
    output.push(values.slice(i, i + size));
  }
  return output;
}

export default function GlobalTranslator({ children }) {
  const { language } = useLanguage();
  const timerRef = useRef(null);
  const runningRef = useRef(false);
  const generationRef = useRef(0);

  useEffect(() => {
    loadRemoteCache();

    const root = document.getElementById("root");
    if (!root) return undefined;

    let disposed = false;
    const generation = ++generationRef.current;

    async function translateUi() {
      if (disposed || runningRef.current) return;
      runningRef.current = true;

      try {
        restoreEnglish(root);

        if (language === "en") return;

        const items = [
          ...collectTextItems(root),
          ...collectAttributeItems(root),
        ];

        const translatedMap = new Map();
        const remoteNeeded = [];
        applyLocalTranslations(items, language, translatedMap, remoteNeeded);

        // Apply reviewed/local translations immediately so the interface
        // changes without waiting for the network.
        for (const item of items) {
          const translated = translatedMap.get(item.clean);
          if (translated) writeItem(item, translated);
        }

        const pending = unique(remoteNeeded).filter(
          (source) => !translatedMap.has(source)
        );

        if (!pending.length) return;

        // Ask the backend only for phrases that are genuinely missing locally.
        // The backend uses the local NLLB model and keeps its own cache.
        let cacheChanged = false;
        for (const batch of chunks(pending, 24)) {
          if (disposed || generation !== generationRef.current) return;

          let result;
          try {
            result = await apiFetch("/public/translate-batch", {
              auth: false,
              method: "POST",
              body: JSON.stringify({ language, texts: batch }),
            });
          } catch (error) {
            console.warn("Remote UI translation unavailable:", error);
            return;
          }

          if (disposed || generation !== generationRef.current) return;

          const translations = result?.translations || {};
          let changed = false;

          for (const [source, translated] of Object.entries(translations)) {
            const value = normalize(translated);
            if (value && value !== source) {
              remoteCache.set(cacheKey(language, source), value);
              changed = true;
            }
          }

          if (changed) cacheChanged = true;

          // Write this batch immediately instead of waiting for every page
          // phrase to finish.
          for (const item of items) {
            const translated = translations[item.clean];
            if (translated && normalize(translated) !== item.clean) {
              writeItem(item, normalize(translated));
            }
          }
        }

        if (cacheChanged) saveRemoteCache();
      } finally {
        runningRef.current = false;
      }
    }

    const schedule = () => {
      if (disposed || runningRef.current) return;
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        void translateUi();
      }, 120);
    };

    void translateUi();

    const observer = new MutationObserver(() => {
      if (!runningRef.current) schedule();
    });

    // React route/page changes add/remove DOM nodes. Do not observe
    // characterData: translation itself changes text nodes and would trigger
    // another full-document translation pass.
    observer.observe(root, {
      childList: true,
      subtree: true,
    });

    return () => {
      disposed = true;
      observer.disconnect();
      clearTimeout(timerRef.current);
      generationRef.current += 1;
    };
  }, [language]);

  return children;
}
