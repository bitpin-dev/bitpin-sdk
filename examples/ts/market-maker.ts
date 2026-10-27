// A minimal two-sided quoting loop. A starting point, not a strategy.
// Each round: read the book, quote a bid and an ask around the mid at --spread-bps, replace the
// previous quotes. Whatever ends the loop, the last quotes are cancelled.
//   node --experimental-strip-types examples/ts/market-maker.ts --symbol USDT/IRT --size 10 [--live]
import { randomUUID } from "node:crypto";
import { Bitpin, type BitpinOptions, Decimal, InsufficientFunds, type OrderRequest } from "@bitpin-dev/bitpin-sdk";
import { args, dryRun, show } from "./common.ts";

export function quotes(mid: Decimal, spreadBps: Decimal, tick: Decimal): [Decimal, Decimal] {
  const half = mid.mul(spreadBps).div(20000);
  const bid = mid.sub(half).div(tick).floor().mul(tick);
  const ask = mid.add(half).div(tick).ceil().mul(tick);
  return [bid, ask];
}

export async function main(argv: string[], options: BitpinOptions = {}, sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))): Promise<number> {
  const opts = args(argv, {
    symbol: { type: "string", default: "USDT/IRT" },
    size: { type: "string" },
    "spread-bps": { type: "string", default: "20" },
    interval: { type: "string", default: "5" },
    iterations: { type: "string", default: "10" },
  });
  if (!opts.size) throw new Error("--size is required");
  const symbol = String(opts.symbol);
  const run = `mm-${randomUUID().slice(0, 8)}`; // unique per run, so ids never collide across restarts
  const client = new Bitpin(options);
  await client.loadMarkets();
  const tick = client.market(symbol).precision.price;
  let live: string[] = [];
  try {
    const iterations = Number(opts.iterations);
    for (let i = 0; i < iterations; i++) {
      const book = await client.fetchOrderBook(symbol, 1);
      const [bestBid, bestAsk] = [book.bids[0], book.asks[0]];
      if (!bestBid || !bestAsk) {
        console.log("empty book, not quoting");
      } else {
        const mid = bestBid[0].add(bestAsk[0]).div(2);
        const [bid, ask] = quotes(mid, new Decimal(String(opts["spread-bps"])), tick);
        const ids = [`${run}-${i}-bid`, `${run}-${i}-ask`];
        const orders: OrderRequest[] = [
          { symbol, type: "limit", side: "buy", amount: String(opts.size), price: bid, params: { clientOrderId: ids[0] } },
          { symbol, type: "limit", side: "sell", amount: String(opts.size), price: ask, params: { clientOrderId: ids[1] } },
        ];
        if (!opts.live) {
          dryRun("cancelOrders", { identifiers: live });
          dryRun("createOrders", orders);
          live = ids;
        } else {
          if (live.length) {
            await client.cancelOrders({ identifiers: live });
            live = [];
          }
          try {
            await client.createOrders(orders);
            live = ids;
          } catch (error) {
            if (!(error instanceof InsufficientFunds)) throw error;
            console.log("insufficient funds, skipping this round");
          }
        }
        show("quotes", { mid, bid, ask });
      }
      if (i + 1 < iterations) await sleep(Number(opts.interval) * 1000);
    }
  } finally {
    // Never leave quotes resting unattended.
    if (opts.live && live.length) await client.cancelOrders({ identifiers: live });
  }
  return 0;
}

if (import.meta.url === `file://${process.argv[1]}`) process.exitCode = await main(process.argv.slice(2));
