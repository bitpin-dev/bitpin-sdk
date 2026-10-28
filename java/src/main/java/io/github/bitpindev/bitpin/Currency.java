package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.Map;

/** A currency; {@code precision} is its tick size. */
public record Currency(
    String id,
    String code,
    String name,
    boolean active,
    BigDecimal precision,
    Map<String, Object> info) {}
