import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
LANGUAGE = "hi"

# These phrases are intentionally different from the earlier benchmark so
# they should exercise the NLLB model instead of relying on an existing cache.
TEXTS = [
    "Emergency teams are coordinating relief supplies.",
    "Please move to the nearest safe shelter.",
    "This area may experience severe flooding.",
    "Medical assistance is available at the relief center.",
    "Road access is currently being assessed.",
    "Relief resources are being allocated by priority.",
    "Please follow official emergency instructions.",
    "Your safety assessment is based on your current location.",
    "The response team is monitoring the situation.",
    "Food and drinking water are being distributed.",
    "Avoid entering damaged buildings.",
    "Emergency services are coordinating with local authorities.",
]


def request_translation():
    payload = {
        "language": LANGUAGE,
        "texts": TEXTS,
    }

    request = urllib.request.Request(
        BASE + "/public/translate-batch",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8")
            elapsed = (time.perf_counter() - started) * 1000
            return response.status, elapsed, json.loads(body)
    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        try:
            body = exc.read().decode("utf-8", errors="replace")
            result = json.loads(body) if body else {"detail": str(exc)}
        except Exception:
            result = {"detail": str(exc)}
        return exc.code, elapsed, result
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return None, elapsed, {"error": str(exc)}


def main():
    print("Disaster AI India - Translation Warm-Up Benchmark")
    print("=" * 64)
    print(f"Backend: {BASE}")
    print(f"Language: {LANGUAGE}")
    print(f"Texts in batch: {len(TEXTS)}")
    print()
    print("IMPORTANT: Run this only AFTER the backend reports that")
    print("the background translation-model warm-up is complete.")
    print()

    print("1) First uncached translation request...")
    status1, first_ms, result1 = request_translation()
    print(f"   HTTP {status1} | {first_ms:.1f} ms")

    if status1 != 200:
        print("   Translation request failed:")
        print(result1)
        return 1

    print(
        f"   translated_count={result1.get('translated_count')} "
        f"requested_count={result1.get('requested_count')} "
        f"provider={result1.get('provider')}"
    )

    print()
    print("2) Same request again (cache test)...")
    status2, second_ms, result2 = request_translation()
    print(f"   HTTP {status2} | {second_ms:.1f} ms")

    if status2 != 200:
        print("   Cached translation request failed:")
        print(result2)
        return 1

    print(
        f"   translated_count={result2.get('translated_count')} "
        f"requested_count={result2.get('requested_count')} "
        f"provider={result2.get('provider')}"
    )

    print()
    print("Results")
    print("-" * 64)
    print(f"First uncached batch : {first_ms:.1f} ms")
    print(f"Second cached batch  : {second_ms:.1f} ms")

    if second_ms > 0:
        print(f"Cache speedup        : {first_ms / second_ms:.1f}x")

    print()
    print("This benchmark uses only the local /public/translate-batch endpoint.")
    print("No paid API or external translation service is used.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
