#!/usr/bin/env python3
"""Test de integracion: verifica que todos los servicios respondan."""
import httpx

BASE = "http://localhost:3000"


def test(path: str, desc: str) -> bool:
    try:
        r = httpx.get(f"{BASE}{path}", timeout=10)
        ok = r.status_code == 200
        print(f"  {'OK' if ok else 'FAIL'} {desc} (HTTP {r.status_code})")
        return ok
    except Exception as e:
        print(f"  FAIL {desc}: {e}")
        return False


def main() -> int:
    print("=== Test de Integracion Imrryr OS ===")
    tests = [
        ("/", "Dashboard HTML"),
        ("/api/widgets", "API widgets"),
        ("/api/finanzas", "API finanzas"),
        ("/api/semillas", "API semillas"),
        ("/api/status", "API status"),
    ]
    results = [test(p, d) for p, d in tests]
    ok = all(results)
    print(f"\n{'V' if ok else 'X'} {sum(results)}/{len(results)} tests OK")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
