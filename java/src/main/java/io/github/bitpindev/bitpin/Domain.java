package io.github.bitpindev.bitpin;

/** The domain the API is served on. REST and WebSocket switch together. */
public enum Domain {
  /** {@code api.bitpin.org}, the default. */
  ORG("org"),
  /** {@code api.bitpin.ir}. */
  IR("ir"),
  /** {@code api.bitpin.market}. */
  MARKET("market");

  private final String key;

  Domain(String key) {
    this.key = key;
  }

  /** The spec name: {@code org}, {@code ir} or {@code market}. */
  public String key() {
    return key;
  }

  /** The REST base URL, e.g. {@code https://api.bitpin.org}. */
  public String restUrl() {
    return Spec.DOMAINS.get(key).get(0);
  }

  /** The Centrifugo WebSocket URL. */
  public String wsUrl() {
    return Spec.DOMAINS.get(key).get(1);
  }

  /**
   * Reads {@code org}, {@code ir} or {@code market} (any case); empty or null means the default.
   */
  public static Domain parse(String value) {
    String name = value == null || value.isBlank() ? Spec.DEFAULT_DOMAIN : value.trim();
    for (Domain d : values()) {
      if (d.key.equalsIgnoreCase(name)) {
        return d;
      }
    }
    throw new IllegalArgumentException(
        "unknown domain \""
            + value
            + "\"; use one of: "
            + String.join(", ", Spec.DOMAINS.keySet().stream().sorted().toList()));
  }
}
