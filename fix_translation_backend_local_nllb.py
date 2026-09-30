from pathlib import Path
import shutil
import sys

START = "# ============================================================\n# MULTILINGUAL UI TRANSLATION\n# ============================================================"
END = "# ============================================================\n# CITIZEN SAFETY & PUBLIC ACCESS\n# ============================================================"

NEW_BLOCK = r'''# ============================================================
# MULTILINGUAL UI TRANSLATION
# ============================================================

# FREE LOCAL TRANSLATION
# ----------------------
# No paid API, API key, subscription, or cloud translation service is used.
# The NLLB-200 distilled 600M model runs locally through PyTorch.
# The model is downloaded once by the setup script and then cached locally.
#
# IMPORTANT LICENSE NOTE:
# facebook/nllb-200-distilled-600M is released under CC-BY-NC-4.0.
# It is suitable for this academic/non-commercial project, but do not use
# this model in a commercial product without checking its license.

TRANSLATION_LANGUAGE_CODES = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "as": "asm_Beng",
    "bn": "ben_Beng",
    "gu": "guj_Gujr",
    "kn": "kan_Knda",
    "kok": "gom_Deva",
    "ml": "mal_Mlym",
    "mr": "mar_Deva",
    "mni": "mni_Mtei",
    "lus": "lus_Latn",
    "ne": "npi_Deva",
    "or": "ory_Orya",
    "pa": "pan_Guru",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "ur": "urd_Arab",
    "ks": "kas_Arab",
}

LOCAL_TRANSLATION_MODEL = "facebook/nllb-200-distilled-600M"
LOCAL_TRANSLATION_CACHE_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "operations_state"
    / "ui_translation_cache.json"
)

_TRANSLATION_CACHE: dict[tuple[str, str], str] = {}
_TRANSLATION_MODEL = None
_TRANSLATION_TOKENIZER = None
_TRANSLATION_LOCK = None


def _translation_lock():
    global _TRANSLATION_LOCK
    if _TRANSLATION_LOCK is None:
        import threading
        _TRANSLATION_LOCK = threading.RLock()
    return _TRANSLATION_LOCK


def _load_translation_cache():
    if _TRANSLATION_CACHE:
        return

    try:
        if not LOCAL_TRANSLATION_CACHE_FILE.exists():
            return

        payload = json.loads(
            LOCAL_TRANSLATION_CACHE_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(payload, dict):
            return

        for language, values in payload.items():
            if not isinstance(values, dict):
                continue
            for source, translated in values.items():
                if (
                    isinstance(source, str)
                    and isinstance(translated, str)
                    and translated.strip()
                    and translated.strip() != source.strip()
                ):
                    _TRANSLATION_CACHE[(language, source)] = translated
    except Exception:
        # A corrupt cache must never prevent the emergency application from
        # starting. It will simply be rebuilt as translations are requested.
        pass


def _save_translation_cache():
    try:
        LOCAL_TRANSLATION_CACHE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        grouped: dict[str, dict[str, str]] = {}
        for (language, source), translated in _TRANSLATION_CACHE.items():
            grouped.setdefault(language, {})[source] = translated

        temporary = LOCAL_TRANSLATION_CACHE_FILE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                grouped,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(LOCAL_TRANSLATION_CACHE_FILE)
    except Exception:
        # Translation persistence is an optimization, never a hard dependency.
        pass


def _load_local_translation_model():
    global _TRANSLATION_MODEL
    global _TRANSLATION_TOKENIZER

    if _TRANSLATION_MODEL is not None and _TRANSLATION_TOKENIZER is not None:
        return _TRANSLATION_TOKENIZER, _TRANSLATION_MODEL

    with _translation_lock():
        if _TRANSLATION_MODEL is not None and _TRANSLATION_TOKENIZER is not None:
            return _TRANSLATION_TOKENIZER, _TRANSLATION_MODEL

        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Local translation dependencies are missing. Run "
                "setup_local_translation.ps1 first."
            ) from exc

        print(
            "[Disaster AI India] Loading FREE local translation model "
            f"{LOCAL_TRANSLATION_MODEL} ..."
        )

        tokenizer = AutoTokenizer.from_pretrained(
            LOCAL_TRANSLATION_MODEL,
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            LOCAL_TRANSLATION_MODEL,
        )

        # CPU dynamic INT8 reduces the runtime RAM footprint substantially.
        # GPU users keep the regular model and use float16 when possible.
        if torch.cuda.is_available():
            model = model.to("cuda")
            try:
                model = model.half()
            except Exception:
                pass
        else:
            try:
                model = torch.ao.quantization.quantize_dynamic(
                    model,
                    {torch.nn.Linear},
                    dtype=torch.qint8,
                )
            except Exception as exc:
                print(
                    "[Disaster AI India] CPU INT8 optimization unavailable; "
                    f"continuing with CPU model: {exc}"
                )

        model.eval()

        _TRANSLATION_TOKENIZER = tokenizer
        _TRANSLATION_MODEL = model

        print("[Disaster AI India] Local translation model ready.")

        return tokenizer, model


def _translate_local_batch(texts: list[str], language: str) -> dict[str, str]:
    target = TRANSLATION_LANGUAGE_CODES.get(language)

    if not target or target == "eng_Latn":
        return {text: text for text in texts}

    _load_translation_cache()

    pending = []
    output: dict[str, str] = {}

    for text in texts:
        cached = _TRANSLATION_CACHE.get((language, text))
        if cached and cached.strip() and cached.strip() != text.strip():
            output[text] = cached
        else:
            pending.append(text)

    if not pending:
        return output

    tokenizer, model = _load_local_translation_model()

    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    target_id = tokenizer.convert_tokens_to_ids(target)

    if target_id is None or target_id == tokenizer.unk_token_id:
        raise RuntimeError(
            f"Unsupported NLLB target language code: {target}"
        )

    # Keep the inference batch modest so the app remains usable on normal
    # student laptops. The frontend already sends batches of up to 24 phrases.
    batch_size = 8

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]

        encoded = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256,
        )

        if device == "cuda":
            encoded = {
                key: value.to(device)
                for key, value in encoded.items()
            }

        tokenizer.src_lang = "eng_Latn"

        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                forced_bos_token_id=target_id,
                max_new_tokens=96,
                num_beams=2,
                do_sample=False,
            )

        translated_values = tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
        )

        for source, translated in zip(batch, translated_values):
            value = " ".join(str(translated or "").split()).strip()

            # Never cache an empty response or an unchanged English source.
            if value and value != source.strip():
                output[source] = value
                _TRANSLATION_CACHE[(language, source)] = value

    if output:
        with _translation_lock():
            _save_translation_cache()

    return output


@app.post(
    "/public/translate-batch",
    tags=["Citizen Safety & Public Access"],
    summary="Translate visible Disaster AI India UI text locally",
)
def public_translate_batch(request: TranslationBatchRequest):
    language = request.language.strip()

    if language not in TRANSLATION_LANGUAGE_CODES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported application language.",
        )

    unique_texts: list[str] = []
    seen = set()

    for value in request.texts:
        clean = " ".join(str(value or "").split()).strip()

        if (
            not clean
            or len(clean) > 300
            or clean in seen
        ):
            continue

        seen.add(clean)
        unique_texts.append(clean)

    if language == "en":
        return {
            "language": language,
            "translations": {
                text: text
                for text in unique_texts
            },
            "provider": "local",
            "model": LOCAL_TRANSLATION_MODEL,
        }

    try:
        translations = _translate_local_batch(
            unique_texts,
            language,
        )
    except Exception as exc:
        # Never break emergency functionality because translation failed.
        print(
            "[Disaster AI India] Local translation unavailable: "
            f"{exc}"
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Local translation model is not ready. "
                "Run setup_local_translation.ps1 and restart the backend."
            ),
        ) from exc

    # Preserve untranslated items as English. The frontend already has its
    # reviewed local dictionary and will use it for critical/common labels.
    response_translations = {
        text: translations.get(text, text)
        for text in unique_texts
    }

    translated_count = sum(
        1
        for source, translated in response_translations.items()
        if translated.strip() != source.strip()
    )

    return {
        "language": language,
        "translations": response_translations,
        "translated_count": translated_count,
        "requested_count": len(unique_texts),
        "provider": "local",
        "model": LOCAL_TRANSLATION_MODEL,
    }
'''


def locate_main() -> Path:
    candidates = [
        Path.cwd() / "backend" / "main.py",
        Path.cwd() / "main.py",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not find backend/main.py. Run this script from the Milestone_03 project folder."
    )


def main():
    path = locate_main()
    text = path.read_text(encoding="utf-8")

    start = text.find(START)
    end = text.find(END)

    if start == -1 or end == -1 or end <= start:
        raise RuntimeError(
            "Could not find the multilingual translation block in backend/main.py. "
            "No changes were made."
        )

    backup = path.with_name("main.py.before_local_translation_fix")
    if not backup.exists():
        shutil.copy2(path, backup)

    updated = (
        text[:start]
        + NEW_BLOCK.rstrip()
        + "\n\n"
        + text[end:]
    )
    path.write_text(updated, encoding="utf-8")

    print(f"Updated: {path}")
    print(f"Backup:  {backup}")
    print("FREE local NLLB translation backend applied successfully.")
    print("No paid API key is required.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
