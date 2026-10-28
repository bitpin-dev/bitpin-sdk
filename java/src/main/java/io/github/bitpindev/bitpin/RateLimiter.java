package io.github.bitpindev.bitpin;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.DoubleSupplier;

/**
 * A client-side sliding window per bucket. {@link #reserve} books a send time atomically, so
 * concurrent callers queue up behind each other instead of bursting.
 */
final class RateLimiter {
  private final ReentrantLock lock = new ReentrantLock();
  private final Map<String, RateLimit> rules;
  private final Map<String, List<Double>> calls = new HashMap<>();
  private final DoubleSupplier clock;

  RateLimiter(Map<String, RateLimit> rules, DoubleSupplier clock) {
    this.rules = rules;
    this.clock = clock;
  }

  private void prune(double now) {
    calls.forEach(
        (name, list) -> {
          double cut = now - rules.get(name).periodSeconds();
          list.removeIf(at -> at <= cut);
        });
  }

  private static int countAfter(List<Double> list, double t) {
    int n = 0;
    for (double at : list) {
      if (at > t) {
        n++;
      }
    }
    return n;
  }

  private double earliest(List<String> buckets, double now) {
    double at = now;
    for (int round = 0; round <= buckets.size(); round++) {
      boolean moved = false;
      for (String bucket : buckets) {
        RateLimit rule = rules.get(bucket);
        if (rule == null) {
          continue;
        }
        List<Double> list = calls.getOrDefault(bucket, List.of());
        if (countAfter(list, at - rule.periodSeconds()) >= rule.limit()) {
          double next = list.get(list.size() - rule.limit()) + rule.periodSeconds();
          if (next > at) {
            at = next;
          }
          moved = true;
        }
      }
      if (!moved) {
        break;
      }
    }
    return at;
  }

  /** Books the next free send time for the buckets and returns the seconds to wait. */
  double reserve(List<String> buckets) {
    lock.lock();
    try {
      double now = clock.getAsDouble();
      prune(now);
      double at = earliest(buckets, now);
      for (String bucket : buckets) {
        if (rules.containsKey(bucket)) {
          List<Double> list = calls.computeIfAbsent(bucket, k -> new ArrayList<>());
          int i = 0;
          while (i < list.size() && list.get(i) <= at) {
            i++;
          }
          list.add(i, at);
        }
      }
      return at - now;
    } finally {
      lock.unlock();
    }
  }
}
