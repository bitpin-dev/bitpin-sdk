// Shared test harness: fixtures, a fake clock, and a fetch mock that records requests.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { ENDPOINTS } from "../src/generated/spec.js";
import { Bitpin, type BitpinOptions } from "../src/index.js";

const FIXTURES = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "fixtures");
export const NOW = 4_000_000_000; // seconds; before the fixture tokens expire

export function fixture(endpointId: string): { status: number; body: any } {
  return JSON.parse(readFileSync(join(FIXTURES, `${endpointId}.json`), "utf8"));
}

export function body(endpointId: string): any {
  return fixture(endpointId).body;
}

export function makeJwt(exp: number): string {
  const b64 = (s: string) => Buffer.from(s).toString("base64url");
  return `${b64("{}")}.${b64(JSON.stringify({ exp }))}.c2ln`;
}

export class FakeTime {
  now = NOW;
  sleeps: number[] = [];
  clock = (): number => this.now;
  sleep = async (seconds: number): Promise<void> => {
    this.sleeps.push(seconds);
    this.now += seconds;
  };
}

export interface Call {
  method: string;
  url: URL;
  headers: Headers;
  body: any;
}

type Reply =
  | { status: number; body?: unknown; text?: string; headers?: Record<string, string> }
  | Error;

export class Route {
  calls: Call[] = [];
  constructor(
    readonly method: string,
    readonly path: string,
    readonly prefix: boolean,
    private replies: Reply[] | ((call: Call) => Reply),
  ) {}
  get count(): number {
    return this.calls.length;
  }
  get last(): Call {
    return this.calls[this.calls.length - 1]!;
  }
  reply(call: Call): Reply {
    if (typeof this.replies === "function") return this.replies(call);
    const next = this.replies.length > 1 ? this.replies.shift()! : this.replies[0]!;
    return next;
  }
  matches(method: string, path: string): boolean {
    return (
      method === this.method && (this.prefix ? path.startsWith(this.path) : path === this.path)
    );
  }
}

export class MockFetch {
  routes: Route[] = [];
  calls: Call[] = [];

  on(method: string, path: string, replies: Reply | Reply[] | ((call: Call) => Reply)): Route {
    const prefix = path.endsWith("*");
    const list =
      typeof replies === "function" ? replies : Array.isArray(replies) ? replies : [replies];
    const route = new Route(method, prefix ? path.slice(0, -1) : path, prefix, list);
    this.routes.unshift(route); // newest wins, like respx overrides
    return route;
  }

  /** Mock one spec endpoint with its shared fixture (or the given status/body). */
  endpoint(endpointId: string, override: { status?: number; body?: unknown } = {}): Route {
    const endpoint = ENDPOINTS[endpointId]!;
    const data = fixture(endpointId);
    const status = override.status ?? data.status;
    const reply = { status, body: "body" in override ? override.body : data.body };
    const braces = endpoint.path.indexOf("{");
    const path = braces >= 0 ? `${endpoint.path.slice(0, braces)}*` : endpoint.path;
    return this.on(endpoint.method, path, reply);
  }

  fetch = async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = new URL(String(input));
    const method = init?.method ?? "GET";
    const raw = init?.body;
    const call: Call = {
      method,
      url,
      headers: new Headers(init?.headers),
      body: typeof raw === "string" && raw ? JSON.parse(raw) : undefined,
    };
    this.calls.push(call);
    const route = this.routes.find((r) => r.matches(method, url.pathname));
    if (!route) throw new Error(`not mocked: ${method} ${url.pathname}`);
    route.calls.push(call);
    const reply = route.reply(call);
    if (reply instanceof Error) throw reply;
    if (reply.status === 204 || (reply.body === undefined && reply.text === undefined)) {
      return new Response(null, { status: reply.status, headers: reply.headers });
    }
    const text = reply.text ?? JSON.stringify(reply.body);
    return new Response(text, { status: reply.status, headers: reply.headers });
  };
}

export function makeClient(
  mock: MockFetch,
  time: FakeTime,
  options: Partial<BitpinOptions> = {},
): Bitpin {
  return new Bitpin({
    apiKey: "test-key",
    secretKey: "test-secret",
    fetch: mock.fetch,
    clock: time.clock,
    sleep: time.sleep,
    ...options,
  });
}

/** A client whose authenticate call is already mocked. */
export function setup(options: Partial<BitpinOptions> = {}): {
  client: Bitpin;
  mock: MockFetch;
  time: FakeTime;
  auth: Route;
} {
  const mock = new MockFetch();
  const time = new FakeTime();
  const auth = mock.endpoint("credentials_post_usr_authenticate");
  return { client: makeClient(mock, time, options), mock, time, auth };
}
