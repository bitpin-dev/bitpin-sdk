# bitpin-sdk (TypeScript)

The official TypeScript and JavaScript SDK for the [Bitpin](https://bitpin.ir) exchange API. It uses ccxt JS method names and result structures, `Decimal` numbers, and automatic token refresh. It also has client-side rate limiting with overridable VIP limits, and WebSocket streams.

SDK رسمی تایپ‌اسکریپت برای API صرافی بیت‌پین. [مستندات فارسی](https://bitpin-dev.github.io/bitpin-sdk/fa/typescript/)

```bash
npm install bitpin-sdk     # Node 22+
```

```ts
import { Bitpin } from "bitpin-sdk";

const client = new Bitpin(); // reads BITPIN_API_KEY and BITPIN_SECRET_KEY
console.log((await client.fetchTicker("BTC/IRT")).last?.toString());
await client.createOrder("USDT/IRT", "limit", "buy", "10", "90000", { clientOrderId: "bot-1" });
await client.cancelOrderByIdentifier("bot-1");
```

Bitpin has no sandbox, so every call is real.

- [TypeScript guide](https://bitpin-dev.github.io/bitpin-sdk/typescript/) and the [full docs](https://bitpin-dev.github.io/bitpin-sdk/) (English and Persian)
- [Examples](https://github.com/bitpin-dev/bitpin-sdk/tree/main/examples/ts)
- [Changelog](https://github.com/bitpin-dev/bitpin-sdk/blob/main/ts/CHANGELOG.md) · [Security](https://github.com/bitpin-dev/bitpin-sdk/blob/main/SECURITY.md)
