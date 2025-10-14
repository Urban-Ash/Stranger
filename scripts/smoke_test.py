import json
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5082"

def get(path: str, timeout: int = 10):
    url = BASE + path
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return resp.status, body
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        return e.code, body
    except URLError as e:
        return -1, str(e)
    except Exception as e:
        return -1, f"error: {e}"

def ok_json(status: int, body: str):
    if status != 200:
        return False, f"HTTP {status}"
    try:
        data = json.loads(body)
        if isinstance(data, dict) and (data.get('success') is True or 'data' in data or 'records' in data):
            return True, "ok"
        return False, "json missing success/data"
    except Exception as e:
        return False, f"json error: {e}"

def main():
    report = []
    # Root UI
    s, b = get("/", timeout=3)
    report.append(("GET /", s, "ok" if s == 200 else b[:120]))

    # Metrics
    s, b = get("/api/metrics", timeout=5)
    good, msg = ok_json(s, b)
    report.append(("GET /api/metrics", s, msg))

    # Search
    s, b = get("/api/search?query=17689273821&max_results=10", timeout=12)
    good, msg = ok_json(s, b)
    report.append(("GET /api/search", s, msg))

    # Source detail (known working case)
    s, b = get("/api/source_detail?table=public.total_69&phone=17689273821&limit=2", timeout=20)
    good, msg = ok_json(s, b)
    report.append(("GET /api/source_detail total_69 phone", s, msg))

    # Schema introspect
    s, b = get("/api/schema_introspect?include_aliases=1&ttl=30", timeout=8)
    good, msg = ok_json(s, b)
    report.append(("GET /api/schema_introspect", s, msg))

    # Validate id_card (format only)
    s, b = get("/api/validate/id_card?id_card=11010519491231002X", timeout=8)
    good, msg = ok_json(s, b)
    report.append(("GET /api/validate/id_card", s, msg))

    # Summarize
    failures = [r for r in report if not (200 <= r[1] < 300)]
    print("Base:", BASE)
    for name, status, msg in report:
        print(f"{name:35} -> {status:3} {msg}")
    print(f"Result: {'PASS' if not failures else 'FAIL'} ({len(report)-len(failures)} passed, {len(failures)} failed)")

if __name__ == "__main__":
    main()