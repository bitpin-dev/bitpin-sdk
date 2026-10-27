// Read-only tour: markets, a ticker, the order book, and your balance if keys are set.
//   node --experimental-strip-types examples/ts/quickstart.ts --symbol BTC/IRT
import { Bitpin, type BitpinOptions } from "bitpin-sdk";
import { args, show } from "./common.ts";

export async function main(argv: string[], options: BitpinOptions = {}): Promise<number> {
  const { symbol } = args(argv, { symbol: { type: "string", default: "BTC/IRT" } });
  const client = new Bitpin(options);
  const markets = await client.loadMarkets();
  console.log(`${Object.keys(markets).length} markets, e.g. ${Object.keys(markets).slice(0, 5).join(", ")}`);
  show(`ticker ${symbol}`, await client.fetchTicker(String(symbol)));
  const book = await client.fetchOrderBook(String(symbol), 5);
  show("best bid / ask", { bid: book.bids[0], ask: book.asks[0] });
  if (client.config.hasCredentials) {
    const balance = await client.fetchBalance();
    show("non-zero balances", Object.fromEntries(Object.entries(balance.total).filter(([, v]) => !v.isZero())));
  } else {
    console.log("Set BITPIN_API_KEY and BITPIN_SECRET_KEY to see your balance.");
  }
  return 0;
}

if (import.meta.url === `file://${process.argv[1]}`) process.exitCode = await main(process.argv.slice(2));
