package io.github.bitpindev.bitpin;

/** A cached access/refresh pair with their expiry times in Unix seconds. */
public record Tokens(String access, String refresh, double accessExp, double refreshExp) {
  /** Hides the token values. */
  @Override
  public String toString() {
    return "Tokens{accessExp=" + accessExp + ", refreshExp=" + refreshExp + "}";
  }
}
