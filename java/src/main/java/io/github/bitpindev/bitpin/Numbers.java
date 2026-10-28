package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.math.BigInteger;

/** Decimal conversions: every price and amount is a {@link BigDecimal}. */
final class Numbers {
  private Numbers() {}

  /**
   * Reads a server or user value. Doubles go through their shortest representation, so 0.1 stays
   * 0.1. Returns null for null and "".
   */
  static BigDecimal toDecimal(Object value) {
    try {
      return switch (value) {
        case null -> null;
        case BigDecimal d -> d;
        case String s -> s.isEmpty() ? null : new BigDecimal(s.trim());
        case BigInteger i -> new BigDecimal(i);
        case Long l -> BigDecimal.valueOf(l);
        case Integer i -> BigDecimal.valueOf(i);
        case Short s -> BigDecimal.valueOf(s);
        case Byte b -> BigDecimal.valueOf(b);
        case Double d -> BigDecimal.valueOf(d);
        case Float f -> new BigDecimal(Float.toString(f));
        default -> throw new IllegalArgumentException("not a number: " + value);
      };
    } catch (NumberFormatException e) {
      throw new IllegalArgumentException("not a number: " + value, e);
    }
  }

  /** The plain string the API expects: no exponent, no trailing zeros. */
  static String format(Object value) {
    BigDecimal d = toDecimal(value);
    if (d == null) {
      throw new IllegalArgumentException("not a number: " + value);
    }
    return plain(d);
  }

  static String plain(BigDecimal d) {
    if (d.signum() == 0) {
      return "0";
    }
    return d.stripTrailingZeros().toPlainString();
  }

  /** A lenient parse for server fields: null when absent or not a number. */
  static BigDecimal dec(Object value) {
    try {
      return toDecimal(value);
    } catch (IllegalArgumentException e) {
      return null;
    }
  }
}
