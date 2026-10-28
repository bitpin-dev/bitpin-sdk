package io.github.bitpindev.bitpin;

import java.util.Map;

/** Your deposit address; {@code tag} is the memo, empty when the network has none. */
public record DepositAddress(
    String currency, String network, String address, String tag, Map<String, Object> info) {}
