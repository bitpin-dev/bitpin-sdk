// A minimal two-sided quoting loop. A starting point, not a strategy.
// Each round: read the book, quote a bid and an ask around the mid at --spread-bps, replace the
// previous quotes. Whatever ends the loop, the last quotes are cancelled. Dry-run unless --live.
//
//   java -cp "target/classes:$(cat target/classpath.txt)" examples/MarketMaker.java --symbol
// USDT/IRT --size 10 [--live]

import io.github.bitpindev.bitpin.Bitpin;
import io.github.bitpindev.bitpin.BitpinException;
import io.github.bitpindev.bitpin.Config;
import io.github.bitpindev.bitpin.Market;
import io.github.bitpindev.bitpin.OrderBook;
import io.github.bitpindev.bitpin.OrderRequest;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

public class MarketMaker {
  static BigDecimal[] quotes(BigDecimal mid, BigDecimal spreadBps, BigDecimal tick) {
    BigDecimal half =
        mid.multiply(spreadBps).divide(BigDecimal.valueOf(20000), 18, RoundingMode.HALF_EVEN);
    BigDecimal bid = mid.subtract(half).divide(tick, 0, RoundingMode.FLOOR).multiply(tick);
    BigDecimal ask = mid.add(half).divide(tick, 0, RoundingMode.CEILING).multiply(tick);
    return new BigDecimal[] {bid, ask};
  }

  public static void main(String[] args) {
    String symbol = "USDT/IRT";
    BigDecimal size = null;
    BigDecimal spreadBps = new BigDecimal("20");
    long intervalMs = 5000;
    int iterations = 10;
    boolean live = false;
    for (int i = 0; i < args.length; i++) {
      switch (args[i]) {
        case "--symbol" -> symbol = args[++i];
        case "--size" -> size = new BigDecimal(args[++i]);
        case "--spread-bps" -> spreadBps = new BigDecimal(args[++i]);
        case "--interval-ms" -> intervalMs = Long.parseLong(args[++i]);
        case "--iterations" -> iterations = Integer.parseInt(args[++i]);
        case "--live" -> live = true;
        default -> throw new IllegalArgumentException("unknown argument " + args[i]);
      }
    }
    if (size == null) {
      throw new IllegalArgumentException("--size is required");
    }
    byte[] buf = new byte[4];
    new SecureRandom().nextBytes(buf);
    String run = "mm-" + HexFormat.of().formatHex(buf); // unique per run, so ids never collide
    List<String> resting = new ArrayList<>();
    // Ctrl-C runs shutdown hooks, not finally blocks: interrupt the loop and wait for its cleanup.
    Thread loop = Thread.currentThread();
    Runtime.getRuntime()
        .addShutdownHook(
            new Thread(
                () -> {
                  loop.interrupt();
                  try {
                    loop.join(10_000);
                  } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                  }
                }));
    try (Bitpin client = new Bitpin(Config.fromEnv().build())) {
      client.loadMarkets();
      Market market = client.market(symbol);
      try {
        for (int i = 0; i < iterations; i++) {
          OrderBook book = client.fetchOrderBook(symbol, 1);
          if (book.bids().isEmpty() || book.asks().isEmpty()) {
            System.out.println("empty book, not quoting");
          } else {
            BigDecimal mid =
                book.bids().get(0).price().add(book.asks().get(0).price()).divide(BigDecimal.TWO);
            BigDecimal[] q = quotes(mid, spreadBps, market.precision().price());
            List<String> ids = List.of(run + "-" + i + "-bid", run + "-" + i + "-ask");
            List<OrderRequest> orders =
                List.of(
                    new OrderRequest(
                        symbol, "limit", "buy", size, q[0], Map.of("clientOrderId", ids.get(0))),
                    new OrderRequest(
                        symbol, "limit", "sell", size, q[1], Map.of("clientOrderId", ids.get(1))));
            if (!live) {
              System.out.printf(
                  "DRY-RUN cancel %s, place bid %s / ask %s (pass --live to send)%n",
                  resting, q[0].toPlainString(), q[1].toPlainString());
            } else {
              if (!resting.isEmpty()) {
                client.cancelOrders(null, resting);
                resting.clear();
              }
              client.createOrders(orders);
            }
            resting.clear();
            resting.addAll(ids);
          }
          Thread.sleep(intervalMs);
        }
      } catch (InterruptedException | BitpinException e) {
        System.out.println("stopping: " + e.getMessage());
      } finally {
        Thread.interrupted(); // clear the flag, or the cancel below would be interrupted too
        if (live && !resting.isEmpty()) { // never leave quotes resting unattended
          client.cancelOrders(null, resting);
        }
      }
    }
  }
}
