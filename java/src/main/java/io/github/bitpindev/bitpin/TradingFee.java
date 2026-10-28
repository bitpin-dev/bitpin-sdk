package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.Map;

/**
 * Your fee in one market. {@code maker} and {@code taker} are ratios: 0.003 is 0.3 %. {@code
 * percentage} and {@code tierBased} are ccxt's flags.
 */
public record TradingFee(
    String symbol,
    BigDecimal maker,
    BigDecimal taker,
    boolean percentage,
    boolean tierBased,
    Map<String, Object> info) {}
