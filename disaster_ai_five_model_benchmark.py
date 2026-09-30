import getpass
import json
import statistics
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
DISASTERS = ["Flood", "Cyclone", "Earthquake", "Wildfire", "Landslide"]


def request(method, path, payload=None, token=None, timeout=180):
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


def login():
    print("Use any APPROVED Disaster AI India account.")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")

    status, elapsed, result = request(
        "POST",
        "/auth/login",
        {"email": email, "password": password},
        timeout=30,
    )

    if status != 200 or not isinstance(result, dict):
        print(f"Login failed: HTTP {status}")
        print(result)
        return None

    token = result.get("access_token")
    if not token:
        print("Login succeeded but no access token was returned.")
        return None

    print(f"Login successful ({elapsed:.1f} ms).\n")
    return token


def get_first_row_id(disaster_type, token):
    status, elapsed, result = request(
        "GET",
        f"/disasters?disaster_type={disaster_type}&limit=1",
        token=token,
        timeout=60,
    )

    if status != 200:
        print(f"  Could not find {disaster_type} row: HTTP {status}")
        print(f"  {result}")
        return None

    records = result.get("data", []) if isinstance(result, dict) else []
    if not records:
        print(f"  No {disaster_type} record returned.")
        return None

    return int(records[0]["row_id"])


def predict(row_id, token):
    return request(
        "GET",
        f"/disasters/{row_id}/predict",
        token=token,
        timeout=180,
    )


def main():
    print("Disaster AI India - Five-Model Cold/Warm Benchmark")
    print("=" * 64)
    print("IMPORTANT: Restart the backend immediately before running this.")
    print("This test measures the first load of each disaster model.")
    print()

    status, _, health = request("GET", "/health", timeout=30)
    if status != 200:
        print("Backend /health failed:")
        print(health)
        return 1

    token = login()
    if not token:
        return 1

    print("Finding one test row for each disaster type...")
    rows = {}
    for disaster_type in DISASTERS:
        row_id = get_first_row_id(disaster_type, token)
        if row_id is not None:
            rows[disaster_type] = row_id
            print(f"  {disaster_type:12} -> row_id {row_id}")

    if len(rows) != len(DISASTERS):
        print("\nCould not find all five disaster types.")
        return 1

    print()
    print("Running FIRST prediction for each model...")
    print("The first call is the cold-load measurement.")
    print()

    results = []

    for disaster_type in DISASTERS:
        row_id = rows[disaster_type]

        status1, cold_ms, result1 = predict(row_id, token)

        if status1 != 200:
            print(
                f"{disaster_type:12} FAILED on cold call "
                f"(HTTP {status1}): {result1}"
            )
            continue

        # A second call immediately after the first one measures cached/warm inference.
        status2, warm_ms, result2 = predict(row_id, token)

        if status2 != 200:
            print(
                f"{disaster_type:12} cold={cold_ms:.1f} ms, "
                f"warm call failed (HTTP {status2})"
            )
            continue

        results.append(
            {
                "disaster_type": disaster_type,
                "row_id": row_id,
                "cold_ms": cold_ms,
                "warm_ms": warm_ms,
            }
        )

        print(
            f"{disaster_type:12} "
            f"cold: {cold_ms:8.1f} ms   "
            f"warm: {warm_ms:8.1f} ms"
        )

    print()
    print("Summary")
    print("-" * 64)
    print(f"{'Disaster':14} {'Row':>8} {'Cold':>12} {'Warm':>12} {'Reduction':>14}")
    print("-" * 64)

    for item in results:
        reduction = (
            (1 - item["warm_ms"] / item["cold_ms"]) * 100
            if item["cold_ms"] > 0
            else 0
        )
        print(
            f"{item['disaster_type']:14} "
            f"{item['row_id']:>8} "
            f"{item['cold_ms']:>10.1f}ms "
            f"{item['warm_ms']:>10.1f}ms "
            f"{reduction:>11.1f}%"
        )

    if results:
        cold_values = [item["cold_ms"] for item in results]
        warm_values = [item["warm_ms"] for item in results]

        print()
        print(
            f"Average cold-load time: {statistics.mean(cold_values):.1f} ms"
        )
        print(
            f"Average warm inference: {statistics.mean(warm_values):.1f} ms"
        )

    print()
    print("Your password was used only for this local login request and is not saved.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
