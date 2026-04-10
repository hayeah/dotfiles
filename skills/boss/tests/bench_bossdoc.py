"""Micro benchmark: parse BOSS.md 1000x, report median."""

import statistics
import time
from pathlib import Path

from boss.bossdoc import parse_sections

FIXTURES = Path(__file__).parent / "fixtures"


def bench(n: int = 1000) -> None:
    text = (FIXTURES / "BOSS.md").read_text()
    times: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        parse_sections(text)
        times.append(time.perf_counter() - t0)
    times.sort()
    median = statistics.median(times)
    p95 = times[int(n * 0.95)]
    p99 = times[int(n * 0.99)]
    print(f"BOSS.md ({len(text)} chars, {text.count(chr(10))} lines)")
    print(f"  n={n}  median={median*1e6:.0f}µs  p95={p95*1e6:.0f}µs  p99={p99*1e6:.0f}µs")


if __name__ == "__main__":
    bench()
