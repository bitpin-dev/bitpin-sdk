package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.Map;

/** A 24-hour ticker; {@code percentage} is the change in percent. Absent values are null. */
public record Ticker(
    String symbol,
    Long timestamp,
    String datetime,
    BigDecimal high,
    BigDecimal low,
    BigDecimal bid,
    BigDecimal ask,
    BigDecimal last,
    BigDecimal close,
    BigDecimal open,
    BigDecimal change,
    BigDecimal percentage,
    BigDecimal average,
    BigDecimal baseVolume,
    BigDecimal quoteVolume,
    Map<String, Object> info) {}
