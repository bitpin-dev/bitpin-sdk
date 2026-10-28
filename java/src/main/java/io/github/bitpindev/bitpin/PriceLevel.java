package io.github.bitpindev.bitpin;

import java.math.BigDecimal;

/** One {@code [price, amount]} row of an order book. */
public record PriceLevel(BigDecimal price, BigDecimal amount) {}
