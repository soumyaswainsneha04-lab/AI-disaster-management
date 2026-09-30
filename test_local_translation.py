import json
import sys
import urllib.request

payload = {
    "language": "hi",
    "texts": [
        "Need immediate assistance?",
        "India Emergency Response Dashboard",
        "Choose your location",
        "Your location is used only for this assessment in the current session.",
    ],
}

request = urllib.request.Request(
    "http://127.0.0.1:8000/public/translate-batch",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
except Exception as exc:
    print(f"Translation test failed: {exc}")
    sys.exit(1)

print(json.dumps(result, ensure_ascii=False, indent=2))
