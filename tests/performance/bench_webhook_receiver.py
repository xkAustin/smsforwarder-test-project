from __future__ import annotations

import argparse
import json
import statistics
import time
import pytest
from typing import List, Dict, Any
import requests

pytestmark = pytest.mark.performance


def reset(base: str, timeout: float) -> None:
    requests.post(f"{base}/reset", timeout=timeout).raise_for_status()
    # fault/reset 不一定存在：不存在就忽略
    try:
        requests.post(f"{base}/fault/reset", timeout=timeout).raise_for_status()
    except Exception:
        pass


def percentile(values: List[float], p: float) -> float:
    """p in [0,100]"""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1


def run(base: str, n: int, timeout: float, warmup: int) -> Dict[str, Any]:
    lat_ms: List[float] = []
    ok = 0

    # warmup
    for i in range(warmup):
        try:
            requests.post(f"{base}/webhook", json={"warmup": i}, timeout=timeout)
        except Exception:
            # warmup 失败不影响继续
            pass

    t_start = time.perf_counter()
    for i in range(n):
        payload = {"i": i, "ts": time.time(), "tag": "perf"}
        t0 = time.perf_counter()
        try:
            r = requests.post(f"{base}/webhook", json=payload, timeout=timeout)
            dt = (time.perf_counter() - t0) * 1000
            lat_ms.append(dt)
            if r.status_code == 200:
                ok += 1
        except Exception:
            dt = (time.perf_counter() - t0) * 1000
            lat_ms.append(dt)

    t_end = time.perf_counter()

    duration_s = t_end - t_start
    out = {
        "target": f"{base}/webhook",
        "n": n,
        "warmup": warmup,
        "ok": ok,
        "success_rate": ok / n if n else 0,
        "p50_ms": statistics.median(lat_ms) if lat_ms else 0,
        "p95_ms": percentile(lat_ms, 95),
        "p99_ms": percentile(lat_ms, 99),
        "min_ms": min(lat_ms) if lat_ms else 0,
        "max_ms": max(lat_ms) if lat_ms else 0,
        "duration_s": duration_s,
        "approx_rps": (n / duration_s) if duration_s > 0 else 0,
    }
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Benchmark mock webhook receiver (no device required)"
    )
    ap.add_argument(
        "--base", default="http://127.0.0.1:18080", help="mock server base url"
    )
    ap.add_argument("--n", type=int, default=500, help="number of requests")
    ap.add_argument(
        "--timeout", type=float, default=3.0, help="request timeout seconds"
    )
    ap.add_argument("--warmup", type=int, default=20, help="warmup requests")
    ap.add_argument("--no-reset", action="store_true", help="do not reset server state")
    args = ap.parse_args()

    if not args.no_reset:
        reset(args.base, args.timeout)

    out = run(args.base, args.n, args.timeout, args.warmup)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
