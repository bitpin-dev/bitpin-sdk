// Client-side sliding-window rate limiter. Pure: it computes waits, the client sleeps.
// `reserve()` books a send time, so concurrent callers queue up instead of bursting.
import type { RateLimit } from "../config.js";

export function insertSorted(list: number[], value: number): void {
  let lo = 0;
  let hi = list.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (list[mid]! <= value) lo = mid + 1;
    else hi = mid;
  }
  list.splice(lo, 0, value);
}

function countAfter(list: number[], value: number): number {
  let lo = 0;
  let hi = list.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (list[mid]! <= value) lo = mid + 1;
    else hi = mid;
  }
  return list.length - lo;
}

export class SlidingWindowLimiter {
  private readonly calls = new Map<string, number[]>();

  constructor(
    private readonly rules: Record<string, RateLimit>,
    private readonly clock: () => number,
  ) {
    for (const name of Object.keys(rules)) this.calls.set(name, []);
  }

  private prune(now: number): void {
    for (const [name, list] of this.calls) {
      const window = this.rules[name]!.periodSeconds;
      while (list.length && list[0]! <= now - window) list.shift();
    }
  }

  private earliest(buckets: readonly string[], now: number): number {
    let at = now;
    for (let round = 0; round <= buckets.length; round++) {
      let moved = false;
      for (const bucket of buckets) {
        const rule = this.rules[bucket];
        const list = this.calls.get(bucket);
        if (!rule || !list) continue;
        if (countAfter(list, at - rule.periodSeconds) >= rule.limit) {
          at = Math.max(at, list[list.length - rule.limit]! + rule.periodSeconds);
          moved = true;
        }
      }
      if (!moved) break;
    }
    return at;
  }

  /** Seconds to wait before a request that consumes `buckets`; 0 when it can go now. */
  delay(buckets: readonly string[]): number {
    const now = this.clock();
    this.prune(now);
    return this.earliest(buckets, now) - now;
  }

  /** Book the next free send time for `buckets` and return the seconds to wait for it. */
  reserve(buckets: readonly string[]): number {
    const now = this.clock();
    this.prune(now);
    const at = this.earliest(buckets, now);
    for (const bucket of buckets) {
      const list = this.calls.get(bucket);
      if (list) insertSorted(list, at);
    }
    return at - now;
  }

  /** Booked sends still inside the window of `bucket` (for tests and diagnostics). */
  size(bucket: string): number {
    return this.calls.get(bucket)?.length ?? 0;
  }
}
