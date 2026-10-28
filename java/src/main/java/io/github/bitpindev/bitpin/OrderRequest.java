package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.Map;

/**
 * One order of {@link Bitpin#createOrders}. {@code amount} and {@code price} may be null when the
 * order type doesn't need them; {@code params} takes the same keys as {@link Bitpin#createOrder}.
 */
public record OrderRequest(
    String symbol,
    String type,
    String side,
    BigDecimal amount,
    BigDecimal price,
    Map<String, ?> params) {

  /** An order without params. */
  public OrderRequest(
      String symbol, String type, String side, BigDecimal amount, BigDecimal price) {
    this(symbol, type, side, amount, price, Map.of());
  }
}
