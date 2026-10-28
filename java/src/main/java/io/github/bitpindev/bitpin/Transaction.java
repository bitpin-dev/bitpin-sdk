package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.Map;

/**
 * A deposit or withdrawal. {@code type} is {@code deposit} or {@code withdrawal}; {@code status} is
 * {@code pending}, {@code ok}, {@code failed} or {@code canceled}.
 */
public record Transaction(
    String id,
    String txid,
    Long timestamp,
    String datetime,
    String network,
    String address,
    String addressTo,
    String tag,
    String type,
    BigDecimal amount,
    String currency,
    String status,
    Long updated,
    Fee fee,
    Boolean internal,
    String comment,
    Map<String, Object> info) {}
