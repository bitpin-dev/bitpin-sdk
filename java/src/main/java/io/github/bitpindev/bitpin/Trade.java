package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.Map;

/** A public trade or one of your fills ({@code order} and {@code fee} are set for fills). */
public record Trade(
    String id,
    String order,
    String symbol,
    String side,
    Long timestamp,
    String datetime,
    BigDecimal price,
    BigDecimal amount,
    BigDecimal cost,
    Fee fee,
    Map<String, Object> info) {}
