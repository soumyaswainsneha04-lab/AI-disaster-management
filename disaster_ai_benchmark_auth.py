import getpass
import json
import statistics
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
WARMUP = 0
RUNS = 3


def request(method, path, payload=None, token=None, timeout=60):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers=headers,
        method=method,
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            elapsed = (time.perf_counter() - started) * 1000
            try:
                result = json.loads(body.decode("utf-8"))
            except Exception:
                result = body.decode("utf-8", errors="replace")
            return response.status, elapsed, result
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
        return None, elapsed, str(exc)


def timed(name, method, path, payload=None, token=None, timeout=60):
    times = []
    last_status = None
    last_result = None

    for run in range(WARMUP + RUNS):
        status, elapsed, result = request(
            method,
            path,
            payload=payload,
            token=token,
            timeout=timeout,
        )
        last_status = status
        last_result = result

        if status is not None and status < 400 and run >= WARMUP:
            times.append(elapsed)
        elif status is None:
            break
        elif status >= 400:
            break

    if times:
        return {
            "name": name,
            "status": last_status,
            "avg_ms": round(statistics.mean(times), 1),
            "min_ms": round(min(times), 1),
            "max_ms": round(max(times), 1),
        }

    return {
        "name": name,
        "status": last_status,
        "error": str(last_result)[:500],
    }


def login():
    print()
    print("Authentication is required because the disaster APIs are protected.")
    print("Use any APPROVED Disaster AI India account.")
    print()

    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")

    status, elapsed, result = request(
        "POST",
        "/auth/login",
        {"email": email, "password": password},
        timeout=30,
    )

    if status != 200 or not isinstance(result, dict):
        print()
        print("Login failed.")
        print(f"HTTP status: {status}")
        print(f"Response: {result}")
        return None

    token = result.get("access_token")
    if not token:
        print("Login succeeded but no access token was returned.")
        return None

    print(f"Login successful ({elapsed:.1f} ms).")
    return token


def main():
    print("Disaster AI India API Benchmark")
    print("=" * 60)
    print(f"Backend: {BASE}")
    print(f"Warmup: {WARMUP} | measured runs: {RUNS}")

    status, _, health = request("GET", "/health", timeout=30)
    if status != 200:
        print()
        print("Backend is not reachable or /health failed:")
        print(health)
        return 1

    token = login()
    if not token:
        return 1

    status, _, disasters = request(
        "GET",
        "/disasters?limit=10",
        token=token,
        timeout=60,
    )

    if status != 200:
        print()
        print("Could not obtain a test disaster row:")
        print(disasters)
        return 1

    records = disasters.get("data", []) if isinstance(disasters, dict) else []
    if not records:
        print("No disaster records were returned.")
        return 1

    row_id = int(records[0]["row_id"])
    row_ids = [int(r["row_id"]) for r in records[:3]]

    tests = [
        ("Health", "GET", "/health", None, 30),
        ("Dataset info", "GET", "/dataset-info", None, 60),
        ("Disaster list", "GET", "/disasters?limit=10", None, 60),
        ("Operations zones", "GET", "/operations/zones?limit=100", None, 60),
        ("Single disaster", "GET", f"/disasters/{row_id}", None, 60),
        ("Resource prediction", "GET", f"/disasters/{row_id}/predict", None, 120),
        ("Resource allocation", "GET", f"/disasters/{row_id}/allocation", None, 120),
        ("Feeds status", "GET", "/feeds/status", None, 30),
        (
            "Optimal resource allocation",
            "POST",
            "/optimization/resource-allocation",
            {
                "row_ids": row_ids,
                "transport_capacity_fraction": 1.0,
                "priority_overrides": {},
            },
            180,
        ),
    ]

    results = []

    print()
    for name, method, path, payload, timeout in tests:
        print(f"Testing {name}...", end=" ", flush=True)
        result = timed(
            name,
            method,
            path,
            payload=payload,
            token=token,
            timeout=timeout,
        )
        results.append(result)

        if "avg_ms" in result:
            print(
                f"{result['avg_ms']} ms "
                f"(min {result['min_ms']} / max {result['max_ms']})"
            )
        else:
            print(f"FAILED ({result.get('status')})")
            print(f"  {result.get('error', '')}")

    print("\nResults")
    print("-" * 72)
    print(f"Test row_id: {row_id}")
    print()
    print(f"{'Endpoint':32} {'Avg':>10} {'Min':>10} {'Max':>10}")
    print("-" * 70)

    for result in results:
        if "avg_ms" in result:
            print(
                f"{result['name'][:32]:32} "
                f"{result['avg_ms']:>8.1f}ms "
                f"{result['min_ms']:>8.1f}ms "
                f"{result['max_ms']:>8.1f}ms"
            )
        else:
            print(
                f"{result['name'][:32]:32} "
                f"FAILED ({result.get('status')})"
            )
            print(f"  {result.get('error', '')}")

    print("\nInterpretation guide")
    print("- < 200 ms: fast")
    print("- 200-500 ms: good")
    print("- 500-1000 ms: noticeable")
    print("- > 1000 ms: optimization candidate")
    print("- Live/network endpoints can vary and should be judged separately.")
    print()
    print("Your password was used only for this local login request and is not saved by this script.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
