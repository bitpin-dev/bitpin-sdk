package io.github.bitpindev.bitpin;

import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * At most {@code limit} requests per {@code period} ({@code sec}, {@code min}, {@code hour} or
 * {@code day}).
 */
public record RateLimit(int limit, String period) {
  private static final Map<String, Double> PERIOD_SECONDS =
      Map.of("sec", 1.0, "min", 60.0, "hour", 3600.0, "day", 86400.0);
  private static final Pattern PATTERN = Pattern.compile("^(\\d+)/(sec|min|hour|day)$");

  /** Checks the values. */
  public RateLimit {
    if (limit < 1) {
      throw new IllegalArgumentException("rate limit count must be at least 1");
    }
    if (!PERIOD_SECONDS.containsKey(period)) {
      throw new IllegalArgumentException("rate limit period must be sec, min, hour or day");
    }
  }

  /** The length of the window in seconds. */
  public double periodSeconds() {
    return PERIOD_SECONDS.get(period);
  }

  /** Reads {@code "10800/min"}. */
  public static RateLimit parse(String value) {
    Matcher m = PATTERN.matcher(value == null ? "" : value);
    if (!m.matches()) {
      throw new IllegalArgumentException(
          "invalid rate limit \"" + value + "\"; use '<count>/<sec|min|hour|day>', e.g. '60/min'");
    }
    int limit;
    try {
      limit = Integer.parseInt(m.group(1));
    } catch (NumberFormatException e) {
      throw new IllegalArgumentException(
          "invalid rate limit \"" + value + "\"; the count is too large", e);
    }
    if (limit < 1) {
      throw new IllegalArgumentException(
          "invalid rate limit \"" + value + "\"; the count must be at least 1");
    }
    return new RateLimit(limit, m.group(2));
  }

  @Override
  public String toString() {
    return limit + "/" + period;
  }
}
