package io.github.bitpindev.bitpin;

import java.math.BigDecimal;

/** A fee paid: its cost and currency (either may be null). */
public record Fee(BigDecimal cost, String currency) {}
