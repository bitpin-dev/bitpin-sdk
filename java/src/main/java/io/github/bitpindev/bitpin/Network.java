package io.github.bitpindev.bitpin;

import java.util.Map;

/** A blockchain network and whether deposits and withdrawals are open on it. */
public record Network(
    String id,
    String network,
    String name,
    boolean deposit,
    boolean withdraw,
    String addressPattern,
    Map<String, Object> info) {}
