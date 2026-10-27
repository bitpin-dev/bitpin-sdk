// The Centrifugo connection. Tests replace it with a fake that has the same three methods.
export type GetToken = () => Promise<string>;

export interface Transport {
  connect(): Promise<void>;
  subscribe(channel: string, onData: (data: unknown) => void): Promise<void>;
  close(): Promise<void>;
}

/** Wraps the official `centrifuge` client, which reconnects and renews tokens on its own. */
export class CentrifugeTransport implements Transport {
  private client: any = null;

  constructor(
    private readonly url: string,
    private readonly getToken: GetToken | null,
  ) {}

  async connect(): Promise<void> {
    const { Centrifuge } = await import("centrifuge");
    this.client = new Centrifuge(this.url, this.getToken ? { getToken: this.getToken } : {});
    this.client.connect();
    await this.client.ready();
  }

  async subscribe(channel: string, onData: (data: unknown) => void): Promise<void> {
    const subscription = this.client.newSubscription(channel);
    subscription.on("publication", (ctx: { data: unknown }) => onData(ctx.data));
    subscription.subscribe();
    await subscription.ready();
  }

  async close(): Promise<void> {
    this.client?.disconnect();
  }
}
