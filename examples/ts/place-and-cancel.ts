// Place a limit order with your own client order id, read it back, then cancel it.
//   node --experimental-strip-types examples/ts/place-and-cancel.ts --price 90000 --amount 10 [--live]
import { randomUUID } from "node:crypto";
import { Bitpin, type BitpinOptions } from "@bitpin-dev/bitpin-sdk";
import { args, dryRun, show } from "./common.ts";

export async function main(argv: string[], options: BitpinOptions = {}): Promise<number> {
  const opts = args(argv, {
    symbol: { type: "string", default: "USDT/IRT" },
    side: { type: "string", default: "buy" },
    price: { type: "string" },
    amount: { type: "string" },
  });
  if (!opts.price || !opts.amount) throw new Error("--price and --amount are required");
  const clientOrderId = `example-${randomUUID().slice(0, 12)}`;
  const order = { symbol: String(opts.symbol), type: "limit", side: String(opts.side), amount: String(opts.amount), price: String(opts.price), params: { clientOrderId } };
  if (!opts.live) {
    dryRun("createOrder", order);
    dryRun("cancelOrderByIdentifier", { identifier: clientOrderId });
    return 0;
  }
  const client = new Bitpin(options);
  const created = await client.createOrder(order.symbol, order.type, order.side, order.amount, order.price, order.params);
  show("created", created);
  show("fetched", await client.fetchOrder(created.id));
  await client.cancelOrderByIdentifier(clientOrderId);
  console.log(`cancel requested for ${clientOrderId}`);
  return 0;
}

if (import.meta.url === `file://${process.argv[1]}`) process.exitCode = await main(process.argv.slice(2));
