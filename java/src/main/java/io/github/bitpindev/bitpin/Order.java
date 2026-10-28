package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.Map;

/**
 * An order. {@code status} is {@code open}, {@code closed} or {@code canceled}; {@code amount},
 * {@code filled} and {@code remaining} are in the base currency, {@code cost} in the quote.
 */
public record Order(
    String id,
    String clientOrderId,
    String symbol,
    String type,
    String side,
    String status,
    Long timestamp,
    String datetime,
    Long lastTradeTimestamp,
    BigDecimal price,
    BigDecimal stopPrice,
    BigDecimal triggerPrice,
    BigDecimal takeProfitPrice,
    BigDecimal average,
    BigDecimal amount,
    BigDecimal cost,
    BigDecimal filled,
    BigDecimal remaining,
    Fee fee,
    Map<String, Object> info) {}
