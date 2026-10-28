package io.github.bitpindev.bitpin;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.function.DoubleSupplier;

/**
 * Decides between using, refreshing and re-authenticating. Not thread-safe on its own; the client
 * holds its auth lock.
 */
final class TokenState {
  enum Action {
    OK,
    REFRESH,
    AUTHENTICATE
  }

  private final DoubleSupplier clock;
  Tokens tokens;

  TokenState(DoubleSupplier clock) {
    this.clock = clock;
  }

  /** A JWT's exp claim, read without verifying it; null when unreadable. */
  static Double jwtExp(String token) {
    String[] parts = token == null ? new String[0] : token.split("\\.", -1);
    if (parts.length != 3) {
      return null;
    }
    try {
      String payload =
          new String(
              Base64.getUrlDecoder().decode(parts[1].replaceAll("=+$", "")),
              StandardCharsets.UTF_8);
      Object exp = Json.asMap(Json.parse(payload)).get("exp");
      if (exp instanceof Number n && Double.isFinite(n.doubleValue())) {
        return n.doubleValue();
      }
    } catch (IllegalArgumentException e) {
      // not base64 or not JSON
    }
    return null;
  }

  Action action() {
    if (tokens == null) {
      return Action.AUTHENTICATE;
    }
    double now = clock.getAsDouble();
    if (now >= tokens.refreshExp()) {
      return Action.AUTHENTICATE;
    }
    if (now >= tokens.accessExp() - Spec.CONSTANTS.get("token_refresh_margin_seconds")) {
      return Action.REFRESH;
    }
    return Action.OK;
  }

  private double exp(String token, String ttl) {
    Double exp = jwtExp(token);
    return exp != null ? exp : clock.getAsDouble() + Spec.CONSTANTS.get(ttl);
  }

  Tokens setTokens(String access, String refresh) {
    tokens =
        new Tokens(
            access,
            refresh,
            exp(access, "access_token_ttl_seconds"),
            exp(refresh, "refresh_token_ttl_seconds"));
    return tokens;
  }

  Tokens setAccess(String access) {
    tokens =
        new Tokens(
            access, tokens.refresh(), exp(access, "access_token_ttl_seconds"), tokens.refreshExp());
    return tokens;
  }

  /** Makes the next call refresh, but only if {@code token} is still the current one. */
  void expireAccess(String token) {
    if (tokens != null && tokens.access().equals(token)) {
      tokens = new Tokens(tokens.access(), tokens.refresh(), 0, tokens.refreshExp());
    }
  }
}
