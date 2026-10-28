// Read-only tour: markets, a ticker, the order book, and your balance if keys are set.
//
//   ./mvnw -q compile && java -cp "target/classes:$(cat target/classpath.txt)"
// examples/Quickstart.java BTC/IRT

import io.github.bitpindev.bitpin.Balances;
import io.github.bitpindev.bitpin.Bitpin;
import io.github.bitpindev.bitpin.Config;
import io.github.bitpindev.bitpin.OrderBook;
import io.github.bitpindev.bitpin.Ticker;
import java.math.BigDecimal;

public class Quickstart {
  public static void main(String[] args) {
    String symbol = args.length > 0 ? args[0] : "BTC/IRT";
    // BITPIN_API_KEY, BITPIN_SECRET_KEY, BITPIN_DOMAIN
    try (Bitpin client = new Bitpin(Config.fromEnv().build())) {
      System.out.printf("%d markets%n", client.loadMarkets().size());
      Ticker ticker = client.fetchTicker(symbol);
      System.out.printf(
          "%s last %s (24h %s%%)%n", ticker.symbol(), ticker.last(), ticker.percentage());
      OrderBook book = client.fetchOrderBook(symbol, 5);
      if (!book.bids().isEmpty() && !book.asks().isEmpty()) {
        System.out.printf(
            "best bid %s / ask %s%n", book.bids().get(0).price(), book.asks().get(0).price());
      }
      if (System.getenv("BITPIN_API_KEY") == null) {
        System.out.println("Set BITPIN_API_KEY and BITPIN_SECRET_KEY to see your balance.");
        return;
      }
      Balances balance = client.fetchBalance();
      balance
          .total()
          .forEach(
              (code, total) -> {
                if (total.compareTo(BigDecimal.ZERO) != 0) {
                  System.out.println(code + " " + total.toPlainString());
                }
              });
    }
  }
}
