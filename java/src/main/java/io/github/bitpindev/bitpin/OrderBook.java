package io.github.bitpindev.bitpin;

import java.util.List;

/** An order book: bids best (highest) first, asks best (lowest) first. */
public record OrderBook(
    String symbol, List<PriceLevel> bids, List<PriceLevel> asks, Long timestamp, String datetime) {}
