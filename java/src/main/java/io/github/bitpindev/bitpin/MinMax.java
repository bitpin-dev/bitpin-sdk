package io.github.bitpindev.bitpin;

import java.math.BigDecimal;

/** A min/max range; null when the server doesn't say. */
public record MinMax(BigDecimal min, BigDecimal max) {}
