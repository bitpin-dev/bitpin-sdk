package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.Map;

/**
 * A market, as ccxt returns it. {@code precision} holds tick sizes ({@code 0.01}, not a digit
 * count); {@code active} is false when the market is suspended or not tradable.
 */
public record Market(
    String id,
    String symbol,
    String base,
    String quote,
    String baseId,
    String quoteId,
    boolean active,
    String type,
    boolean spot,
    boolean margin,
    boolean swap,
    boolean future,
    boolean option,
    boolean contract,
    Precision precision,
    Limits limits,
    Map<String, Object> info) {

  /** Tick sizes of the amount, the price and the cost. */
  public record Precision(BigDecimal amount, BigDecimal price, BigDecimal cost) {}

  /** Limits of the amount, the price and the cost. */
  public record Limits(MinMax amount, MinMax price, MinMax cost) {}
}
