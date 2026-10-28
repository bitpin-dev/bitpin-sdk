package io.github.bitpindev.bitpin;

import java.util.Map;

/** One of your bank accounts; pass {@code id} as {@code accountNumber} to withdraw IRT. */
public record BankAccount(
    String id,
    String currency,
    String iban,
    String card,
    String status,
    Map<String, Object> info) {}
