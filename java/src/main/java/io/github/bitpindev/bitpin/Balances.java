package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/** ccxt's balance structure: per currency, plus the free/used/total maps. */
public record Balances(
    Map<String, BalanceEntry> currencies,
    Map<String, BigDecimal> free,
    Map<String, BigDecimal> used,
    Map<String, BigDecimal> total,
    List<Map<String, Object>> info) {

  /** One currency's balance; zero when you hold none. */
  public BalanceEntry get(String code) {
    return currencies.getOrDefault(
        code, new BalanceEntry(BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO));
  }
}
