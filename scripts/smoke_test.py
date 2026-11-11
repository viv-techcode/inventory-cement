"""Check the deployed service's main API and static pages from a supplied URL."""
from __future__ import annotations
import sys
from urllib.error import URLError
from urllib.request import urlopen

PATHS = ["/api/health", "/api/dashboard", "/api/catalog", "/api/inventory/balances", "/api/sales", "/api/forecasts/leaderboard", "/api/purchase-orders", "/api/data/quality", "/", "/app.js", "/styles.css"]

def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/smoke_test.py BASE_URL")
        return 2
    base = sys.argv[1].rstrip("/")
    failed = False
    for path in PATHS:
        try:
            with urlopen(base + path, timeout=30) as response:
                body = response.read()
                ok = response.status == 200 and bool(body)
                print(f"{'PASS' if ok else 'FAIL'} {path} status={response.status} bytes={len(body)}")
                failed |= not ok
        except (URLError, TimeoutError) as exc:
            print(f"FAIL {path} error={exc}")
            failed = True
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
