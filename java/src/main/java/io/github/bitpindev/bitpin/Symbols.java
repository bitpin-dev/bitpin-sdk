package io.github.bitpindev.bitpin;

import java.util.Locale;
import java.util.regex.Pattern;

/** Converts between ccxt symbols ({@code BTC/IRT}) and Bitpin market ids ({@code BTC_IRT}). */
public final class Symbols {
  private Symbols() {}

  private static final Pattern PART = Pattern.compile("^[A-Z0-9]+$");

  private static String[] split(String value, String sep) {
    String[] parts = value.split(Pattern.quote(sep), -1);
    if (parts.length != 2
        || !PART.matcher(parts[0]).matches()
        || !PART.matcher(parts[1]).matches()) {
      return null;
    }
    return parts;
  }

  /** {@code "btc/irt"}, {@code "BTC/IRT"} or {@code "BTC_IRT"} to Bitpin's id {@code "BTC_IRT"}. */
  public static String marketId(String symbol) {
    String value = symbol == null ? "" : symbol.trim().toUpperCase(Locale.ROOT);
    for (String sep : new String[] {"/", "_"}) {
      if (value.contains(sep)) {
        String[] parts = split(value, sep);
        if (parts != null) {
          return parts[0] + "_" + parts[1];
        }
      }
    }
    throw new BadSymbolException(
        "invalid symbol \"" + symbol + "\"; use 'BASE/QUOTE', e.g. 'BTC/IRT'");
  }

  /** Bitpin's id {@code "BTC_IRT"} to the ccxt symbol {@code "BTC/IRT"}. */
  public static String symbol(String marketId) {
    String[] parts = marketId == null ? null : split(marketId, "_");
    if (parts == null) {
      throw new BadSymbolException("invalid market id \"" + marketId + "\"");
    }
    return parts[0] + "/" + parts[1];
  }

  /** The ccxt symbol for a market id, or the raw value when it isn't one. */
  static String symbolOrRaw(Object marketId) {
    String id = marketId instanceof String s ? s : "";
    String[] parts = split(id, "_");
    return parts == null ? id : parts[0] + "/" + parts[1];
  }
}
