import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
LANGUAGE = "hi"

TEXTS = [
    "Emergency teams are moving to the affected district.",
    "Relief supplies are being prepared for immediate dispatch.",
    "Please move to the nearest safe shelter if instructed.",
    "The response team is checking road access before delivery.",
    "Medical supplies should be prioritized for this incident.",
    "The nearest depot has enough water for the current estimate.",
    "Field teams should report blocked roads immediately.",
    "The dashboard is updating the latest disaster information.",
    "Please keep emergency contact numbers available.",
    "The allocation plan will be reviewed by the response coordinator.",
    "This location requires additional shelter capacity.",
    "The system is calculating the safest delivery route.",
]


def post(texts):
    payload = {
        "language": LANGUAGE,
        "texts": texts,
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
        body = exc.read().decode("utf-8", errors="replace")
        try:
            result = json.loads(body)
        except Exception:
            result = body
        return exc.code, elapsed, result
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return None, elapsed, str(exc)


def main():
    print("Disaster AI India - Local NLLB Translation Benchmark")
    print("=" * 64)
    print(f"Language: {LANGUAGE}")
    print(f"Texts in batch: {len(TEXTS)}")
    print()

    print("1) First translation request...")
    status1, ms1, result1 = post(TEXTS)
    print(f"   HTTP {status1} | {ms1:.1f} ms")
    if status1 != 200:
        print(result1)
        return 1

    print(
        f"   translated_count={result1.get('translated_count')} "
        f"requested_count={result1.get('requested_count')} "
        f"provider={result1.get('provider')}"
    )

    print()
    print("2) Same request again (cache test)...")
    status2, ms2, result2 = post(TEXTS)
    print(f"   HTTP {status2} | {ms2:.1f} ms")
    if status2 != 200:
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
    print(f"First request : {ms1:.1f} ms")
    print(f"Cached request: {ms2:.1f} ms")

    if ms1 > 0:
        print(f"Speedup       : {ms1 / max(ms2, 0.1):.1f}x")

    print()
    print("This benchmark uses only the local /public/translate-batch endpoint.")
    print("No paid API or external translation service is used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
