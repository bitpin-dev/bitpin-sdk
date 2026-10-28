package io.github.bitpindev.bitpin;

import java.math.BigDecimal;

/** One currency's balance: free to use, used (in open orders), and their total. */
public record BalanceEntry(BigDecimal free, BigDecimal used, BigDecimal total) {}
