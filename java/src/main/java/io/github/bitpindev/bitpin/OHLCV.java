package io.github.bitpindev.bitpin;

import java.math.BigDecimal;

/** One candle: {@code timestamp} in milliseconds, then open, high, low, close and volume. */
public record OHLCV(
    long timestamp,
    BigDecimal open,
    BigDecimal high,
    BigDecimal low,
    BigDecimal close,
    BigDecimal volume) {}
