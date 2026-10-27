// Generated from spec/bitpin.yaml by scripts/gen_ts.py. Do not edit.

export type Auth = "public" | "private" | "credentials";
export type Method = "GET" | "POST" | "DELETE";
export type Period = "sec" | "min" | "hour" | "day";

export interface Endpoint {
  readonly id: string;
  readonly method: Method;
  readonly path: string;
  readonly auth: Auth;
  readonly buckets: readonly string[];
  readonly idempotent: boolean;
  readonly implicit: string;
}

export interface ErrorRule {
  readonly status: number;
  readonly error: string;
  readonly paths: readonly string[];
  readonly detail: readonly string[];
}

export const URLS = {
  "docs": "https://docs.bitpin.ir",
  "rest": "https://api.bitpin.org",
  "ws": "wss://centrifugo.bitpin.org/connection/websocket"
} as const;

export const DOMAINS = {
  "ir": {
    "rest": "https://api.bitpin.ir",
    "ws": "wss://centrifugo.bitpin.ir/connection/websocket"
  },
  "market": {
    "rest": "https://api.bitpin.market",
    "ws": "wss://centrifugo.bitpin.market/connection/websocket"
  },
  "org": {
    "rest": "https://api.bitpin.org",
    "ws": "wss://centrifugo.bitpin.org/connection/websocket"
  }
} as const;

export type Domain = keyof typeof DOMAINS;

export const DEFAULT_DOMAIN: Domain = "org";

export const CONSTANTS = {
  "access_token_ttl_seconds": 900,
  "bulk_orders_max": 10,
  "candles_max_per_request": 10000,
  "fills_max_age_seconds": 86400,
  "fills_max_page_size": 250,
  "order_history_default_limit": 50,
  "order_history_max_limit": 200,
  "order_history_max_range_days": 90,
  "orderbook_default_limit": 20,
  "orderbook_max_limit": 50,
  "orders_max_page_size": 250,
  "refresh_token_ttl_seconds": 2592000,
  "token_refresh_margin_seconds": 120,
  "wallet_lists_max_page_size": 1000,
  "wallets_max_page_size": 1000
} as const;

export const RATE_LIMITS: Readonly<Record<string, readonly [number, Period]>> = {
  "auth": [
    3,
    "min"
  ],
  "candles": [
    300,
    "min"
  ],
  "commissions": [
    10000,
    "day"
  ],
  "currency_networks": [
    60,
    "min"
  ],
  "deposit_address": [
    60,
    "min"
  ],
  "deposits": [
    60,
    "min"
  ],
  "fills": [
    300,
    "min"
  ],
  "market_public": [
    200,
    "min"
  ],
  "market_suspensions": [
    2,
    "min"
  ],
  "matches": [
    60,
    "min"
  ],
  "order_bulk_cancel": [
    1800,
    "hour"
  ],
  "order_bulk_create": [
    1800,
    "hour"
  ],
  "order_cancel": [
    18000,
    "hour"
  ],
  "order_create": [
    18000,
    "hour"
  ],
  "order_history": [
    5,
    "sec"
  ],
  "order_read": [
    18000,
    "hour"
  ],
  "orderbook": [
    60,
    "min"
  ],
  "refresh": [
    20,
    "min"
  ],
  "tickers": [
    300,
    "min"
  ],
  "wallet": [
    60,
    "min"
  ],
  "withdraw_otp": [
    10000,
    "day"
  ],
  "withdraws": [
    60,
    "min"
  ],
  "ws_info": [
    10,
    "min"
  ]
};

export const ENDPOINTS: Readonly<Record<string, Endpoint>> = {
  "credentials_post_usr_authenticate": {
    "auth": "credentials",
    "buckets": [
      "auth"
    ],
    "id": "credentials_post_usr_authenticate",
    "idempotent": false,
    "implicit": "credentialsPostUsrAuthenticate",
    "method": "POST",
    "path": "/api/v1/usr/authenticate/"
  },
  "credentials_post_usr_refresh_token": {
    "auth": "credentials",
    "buckets": [
      "refresh"
    ],
    "id": "credentials_post_usr_refresh_token",
    "idempotent": false,
    "implicit": "credentialsPostUsrRefreshToken",
    "method": "POST",
    "path": "/api/v1/usr/refresh_token/"
  },
  "credentials_post_usr_ws_info": {
    "auth": "credentials",
    "buckets": [
      "ws_info"
    ],
    "id": "credentials_post_usr_ws_info",
    "idempotent": false,
    "implicit": "credentialsPostUsrWsInfo",
    "method": "POST",
    "path": "/api/v1/usr/ws-info/"
  },
  "private_delete_odr_orders_bulk": {
    "auth": "private",
    "buckets": [
      "order_bulk_cancel"
    ],
    "id": "private_delete_odr_orders_bulk",
    "idempotent": false,
    "implicit": "privateDeleteOdrOrdersBulk",
    "method": "DELETE",
    "path": "/api/v1/odr/orders/bulk/"
  },
  "private_delete_odr_orders_id": {
    "auth": "private",
    "buckets": [
      "order_cancel"
    ],
    "id": "private_delete_odr_orders_id",
    "idempotent": false,
    "implicit": "privateDeleteOdrOrdersId",
    "method": "DELETE",
    "path": "/api/v1/odr/orders/{id}/"
  },
  "private_delete_odr_orders_identifier_identifier": {
    "auth": "private",
    "buckets": [
      "order_cancel"
    ],
    "id": "private_delete_odr_orders_identifier_identifier",
    "idempotent": false,
    "implicit": "privateDeleteOdrOrdersIdentifierIdentifier",
    "method": "DELETE",
    "path": "/api/v1/odr/orders/identifier/{identifier}/"
  },
  "private_get_mkt_commissions": {
    "auth": "private",
    "buckets": [
      "commissions"
    ],
    "id": "private_get_mkt_commissions",
    "idempotent": true,
    "implicit": "privateGetMktCommissions",
    "method": "GET",
    "path": "/api/v1/mkt/commissions/"
  },
  "private_get_mkt_markets_suspensions": {
    "auth": "private",
    "buckets": [
      "market_suspensions"
    ],
    "id": "private_get_mkt_markets_suspensions",
    "idempotent": true,
    "implicit": "privateGetMktMarketsSuspensions",
    "method": "GET",
    "path": "/api/v1/mkt/markets/suspensions/"
  },
  "private_get_odr_fills": {
    "auth": "private",
    "buckets": [
      "fills"
    ],
    "id": "private_get_odr_fills",
    "idempotent": true,
    "implicit": "privateGetOdrFills",
    "method": "GET",
    "path": "/api/v1/odr/fills/"
  },
  "private_get_odr_order_history": {
    "auth": "private",
    "buckets": [
      "order_history"
    ],
    "id": "private_get_odr_order_history",
    "idempotent": true,
    "implicit": "privateGetOdrOrderHistory",
    "method": "GET",
    "path": "/api/v1/odr/order_history/"
  },
  "private_get_odr_orders": {
    "auth": "private",
    "buckets": [
      "order_read"
    ],
    "id": "private_get_odr_orders",
    "idempotent": true,
    "implicit": "privateGetOdrOrders",
    "method": "GET",
    "path": "/api/v1/odr/orders/"
  },
  "private_get_odr_orders_id": {
    "auth": "private",
    "buckets": [
      "order_read"
    ],
    "id": "private_get_odr_orders_id",
    "idempotent": true,
    "implicit": "privateGetOdrOrdersId",
    "method": "GET",
    "path": "/api/v1/odr/orders/{id}/"
  },
  "private_get_wlt_account_numbers": {
    "auth": "private",
    "buckets": [
      "wallet"
    ],
    "id": "private_get_wlt_account_numbers",
    "idempotent": true,
    "implicit": "privateGetWltAccountNumbers",
    "method": "GET",
    "path": "/api/v1/wlt/account_numbers/"
  },
  "private_get_wlt_deposits": {
    "auth": "private",
    "buckets": [
      "deposits"
    ],
    "id": "private_get_wlt_deposits",
    "idempotent": true,
    "implicit": "privateGetWltDeposits",
    "method": "GET",
    "path": "/api/v2/wlt/deposits/"
  },
  "private_get_wlt_networks": {
    "auth": "private",
    "buckets": [
      "currency_networks"
    ],
    "id": "private_get_wlt_networks",
    "idempotent": true,
    "implicit": "privateGetWltNetworks",
    "method": "GET",
    "path": "/api/v2/wlt/networks/"
  },
  "private_get_wlt_wallets": {
    "auth": "private",
    "buckets": [
      "wallet"
    ],
    "id": "private_get_wlt_wallets",
    "idempotent": true,
    "implicit": "privateGetWltWallets",
    "method": "GET",
    "path": "/api/v1/wlt/wallets/"
  },
  "private_get_wlt_withdraws": {
    "auth": "private",
    "buckets": [
      "withdraws"
    ],
    "id": "private_get_wlt_withdraws",
    "idempotent": true,
    "implicit": "privateGetWltWithdraws",
    "method": "GET",
    "path": "/api/v2/wlt/withdraws/"
  },
  "private_post_odr_orders": {
    "auth": "private",
    "buckets": [
      "order_create"
    ],
    "id": "private_post_odr_orders",
    "idempotent": false,
    "implicit": "privatePostOdrOrders",
    "method": "POST",
    "path": "/api/v1/odr/orders/"
  },
  "private_post_odr_orders_bulk": {
    "auth": "private",
    "buckets": [
      "order_bulk_create",
      "order_bulk_cancel"
    ],
    "id": "private_post_odr_orders_bulk",
    "idempotent": false,
    "implicit": "privatePostOdrOrdersBulk",
    "method": "POST",
    "path": "/api/v1/odr/orders/bulk/"
  },
  "private_post_wlt_address": {
    "auth": "private",
    "buckets": [
      "deposit_address"
    ],
    "id": "private_post_wlt_address",
    "idempotent": true,
    "implicit": "privatePostWltAddress",
    "method": "POST",
    "path": "/api/v2/wlt/address/"
  },
  "private_post_wlt_withdraws": {
    "auth": "private",
    "buckets": [
      "withdraws"
    ],
    "id": "private_post_wlt_withdraws",
    "idempotent": false,
    "implicit": "privatePostWltWithdraws",
    "method": "POST",
    "path": "/api/v2/wlt/withdraws/"
  },
  "private_post_wlt_withdraws_retry_id": {
    "auth": "private",
    "buckets": [
      "withdraw_otp"
    ],
    "id": "private_post_wlt_withdraws_retry_id",
    "idempotent": false,
    "implicit": "privatePostWltWithdrawsRetryId",
    "method": "POST",
    "path": "/api/v1/wlt/withdraws/retry/{id}/"
  },
  "private_post_wlt_withdraws_verify_otp_id": {
    "auth": "private",
    "buckets": [
      "withdraw_otp"
    ],
    "id": "private_post_wlt_withdraws_verify_otp_id",
    "idempotent": false,
    "implicit": "privatePostWltWithdrawsVerifyOtpId",
    "method": "POST",
    "path": "/api/v1/wlt/withdraws/verify/otp/{id}/"
  },
  "public_get_mkt_candles": {
    "auth": "public",
    "buckets": [
      "candles"
    ],
    "id": "public_get_mkt_candles",
    "idempotent": true,
    "implicit": "publicGetMktCandles",
    "method": "GET",
    "path": "/api/v1/mkt/candles/"
  },
  "public_get_mkt_currencies": {
    "auth": "public",
    "buckets": [
      "market_public"
    ],
    "id": "public_get_mkt_currencies",
    "idempotent": true,
    "implicit": "publicGetMktCurrencies",
    "method": "GET",
    "path": "/api/v1/mkt/currencies/"
  },
  "public_get_mkt_markets": {
    "auth": "public",
    "buckets": [
      "market_public"
    ],
    "id": "public_get_mkt_markets",
    "idempotent": true,
    "implicit": "publicGetMktMarkets",
    "method": "GET",
    "path": "/api/v1/mkt/markets/"
  },
  "public_get_mkt_networks": {
    "auth": "public",
    "buckets": [
      "market_public"
    ],
    "id": "public_get_mkt_networks",
    "idempotent": true,
    "implicit": "publicGetMktNetworks",
    "method": "GET",
    "path": "/api/v1/mkt/networks/"
  },
  "public_get_mkt_tickers": {
    "auth": "public",
    "buckets": [
      "tickers"
    ],
    "id": "public_get_mkt_tickers",
    "idempotent": true,
    "implicit": "publicGetMktTickers",
    "method": "GET",
    "path": "/api/v1/mkt/tickers/"
  },
  "public_get_mth_matches_symbol": {
    "auth": "public",
    "buckets": [
      "matches"
    ],
    "id": "public_get_mth_matches_symbol",
    "idempotent": true,
    "implicit": "publicGetMthMatchesSymbol",
    "method": "GET",
    "path": "/api/v1/mth/matches/{symbol}/"
  },
  "public_get_mth_orderbook_symbol": {
    "auth": "public",
    "buckets": [
      "orderbook"
    ],
    "id": "public_get_mth_orderbook_symbol",
    "idempotent": true,
    "implicit": "publicGetMthOrderbookSymbol",
    "method": "GET",
    "path": "/api/v1/mth/orderbook/{symbol}/"
  }
};

export const ERROR_RULES: readonly ErrorRule[] = [
  {
    "detail": [],
    "error": "RateLimitExceeded",
    "paths": [],
    "status": 429
  },
  {
    "detail": [],
    "error": "AuthenticationError",
    "paths": [],
    "status": 401
  },
  {
    "detail": [],
    "error": "AuthenticationError",
    "paths": [
      "credentials_post_usr_authenticate",
      "credentials_post_usr_ws_info"
    ],
    "status": 406
  },
  {
    "detail": [],
    "error": "PermissionDenied",
    "paths": [],
    "status": 403
  },
  {
    "detail": [],
    "error": "OrderNotFound",
    "paths": [
      "private_get_odr_orders_id",
      "private_delete_odr_orders"
    ],
    "status": 404
  },
  {
    "detail": [],
    "error": "BadRequest",
    "paths": [],
    "status": 404
  },
  {
    "detail": [
      "insufficent_balance",
      "insufficent_frozen",
      "insufficent_pool_balance",
      "insufficient"
    ],
    "error": "InsufficientFunds",
    "paths": [],
    "status": 406
  },
  {
    "detail": [
      "cancel_order_not_allowed",
      "not allowed"
    ],
    "error": "InvalidOrder",
    "paths": [],
    "status": 406
  },
  {
    "detail": [
      "invalid_otp",
      "otp1_already_verified",
      "extra_try"
    ],
    "error": "InvalidOTP",
    "paths": [],
    "status": 400
  },
  {
    "detail": [],
    "error": "InvalidOrder",
    "paths": [
      "private_post_odr_orders"
    ],
    "status": 400
  },
  {
    "detail": [],
    "error": "BadRequest",
    "paths": [],
    "status": 400
  },
  {
    "detail": [],
    "error": "ExchangeError",
    "paths": [],
    "status": 406
  },
  {
    "detail": [],
    "error": "ExchangeNotAvailable",
    "paths": [],
    "status": 500
  },
  {
    "detail": [],
    "error": "ExchangeNotAvailable",
    "paths": [],
    "status": 502
  },
  {
    "detail": [],
    "error": "ExchangeNotAvailable",
    "paths": [],
    "status": 503
  },
  {
    "detail": [],
    "error": "ExchangeNotAvailable",
    "paths": [],
    "status": 504
  }
];

export const HAS: Readonly<Record<string, boolean>> = {
  "cancelAllOrders": false,
  "cancelOrder": true,
  "cancelOrders": true,
  "createDepositAddress": false,
  "createOrder": true,
  "createOrders": true,
  "editOrder": false,
  "fetchAccounts": false,
  "fetchBalance": true,
  "fetchClosedOrders": true,
  "fetchCurrencies": true,
  "fetchDepositAddress": true,
  "fetchDepositWithdrawFees": false,
  "fetchDeposits": true,
  "fetchLedger": false,
  "fetchMarkets": true,
  "fetchMyTrades": true,
  "fetchOHLCV": true,
  "fetchOpenOrders": true,
  "fetchOrder": true,
  "fetchOrderBook": true,
  "fetchOrders": true,
  "fetchPositions": false,
  "fetchTicker": true,
  "fetchTickers": true,
  "fetchTrades": true,
  "fetchTradingFee": true,
  "fetchTradingFees": true,
  "fetchWithdrawals": true,
  "sandbox": false,
  "setLeverage": false,
  "transfer": false,
  "watchBalance": false,
  "watchMyTrades": true,
  "watchOHLCV": true,
  "watchOrderBook": true,
  "watchOrders": true,
  "watchTicker": true,
  "watchTickers": false,
  "watchTrades": true,
  "withdraw": true
};

export const NOT_SUPPORTED: Readonly<Record<string, readonly [string, string]>> = {
  "cancelAllOrders": [
    "Bitpin doesn't offer cancel-all yet. Use cancel_orders() with up to 10 ids at a time.",
    "بیت‌پین فعلاً لغو همهٔ سفارش‌ها را ارائه نمی‌دهد. از cancel_orders() با حداکثر ۱۰ شناسه در هر درخواست استفاده کنید."
  ],
  "createDepositAddress": [
    "Bitpin gives each user one address per network. Use fetch_deposit_address(), which creates it on first use.",
    "بیت‌پین برای هر کاربر روی هر شبکه یک آدرس می‌دهد. از fetch_deposit_address() استفاده کنید؛ بار اول آدرس را می‌سازد."
  ],
  "editOrder": [
    "Bitpin doesn't support editing orders yet. Cancel the order and place a new one.",
    "بیت‌پین فعلاً ویرایش سفارش را پشتیبانی نمی‌کند. سفارش را لغو کنید و سفارش جدید ثبت کنید."
  ],
  "fetchAccounts": [
    "Bitpin doesn't offer account or user info through the public API yet.",
    "بیت‌پین فعلاً اطلاعات حساب کاربری را از طریق API عمومی ارائه نمی‌دهد."
  ],
  "fetchDepositWithdrawFees": [
    "Bitpin doesn't offer a deposit/withdraw fee endpoint yet. The fee of a withdrawal is returned when you create it.",
    "بیت‌پین فعلاً سرویس کارمزد واریز و برداشت ارائه نمی‌دهد. کارمزد هر برداشت هنگام ثبت آن برگردانده می‌شود."
  ],
  "fetchLedger": [
    "Bitpin doesn't offer a ledger endpoint yet. Use fetch_deposits(), fetch_withdrawals() and fetch_my_trades().",
    "بیت‌پین فعلاً دفتر کل (ledger) ارائه نمی‌دهد. از fetch_deposits()، fetch_withdrawals() و fetch_my_trades() استفاده کنید."
  ],
  "fetchPositions": [
    "Bitpin doesn't offer margin or positions through the public API yet.",
    "بیت‌پین فعلاً معاملات اهرمی و پوزیشن‌ها را از طریق API عمومی ارائه نمی‌دهد."
  ],
  "sandbox": [
    "Bitpin has no sandbox or testnet. Every call reaches the real exchange; the examples default to dry-run.",
    "بیت‌پین محیط آزمایشی (sandbox) ندارد. هر درخواست به صرافی واقعی می‌رسد؛ مثال‌ها به‌صورت پیش‌فرض اجرای آزمایشی دارند."
  ],
  "setLeverage": [
    "Bitpin doesn't offer margin or leverage through the public API yet.",
    "بیت‌پین فعلاً معاملات اهرمی را از طریق API عمومی ارائه نمی‌دهد."
  ],
  "transfer": [
    "Bitpin doesn't offer transfers between wallet services through the public API yet.",
    "بیت‌پین فعلاً انتقال بین سرویس‌های کیف پول را از طریق API عمومی ارائه نمی‌دهد."
  ],
  "watchBalance": [
    "Bitpin doesn't publish balance updates over WebSocket yet. Poll fetch_balance().",
    "بیت‌پین فعلاً تغییرات موجودی را روی وب‌سوکت منتشر نمی‌کند. از fetch_balance() استفاده کنید."
  ],
  "watchTickers": [
    "Bitpin doesn't document an all-markets ticker channel yet. Use watch_ticker() per symbol or fetch_tickers().",
    "بیت‌پین فعلاً کانال قیمت همهٔ بازارها را مستند نکرده است. از watch_ticker() برای هر بازار یا fetch_tickers() استفاده کنید."
  ]
};

export const WS_CHANNELS = {
  "market": "market:{symbol}",
  "matches": "matches:{symbol}",
  "orderbook": "orderbook:{symbol}",
  "user_orders": "user:order_info#{user_identifier}"
} as const;

export const WS_EVENTS: Readonly<Record<string, string>> = {
  "candle_update": "market",
  "currency_price_update": "market",
  "market_data": "orderbook",
  "matches_update": "matches",
  "user_match_update": "user_orders",
  "user_order_update": "user_orders"
};

/** One method per spec endpoint, named in camelCase like ccxt's implicit API. */
export interface ImplicitApi {
  credentialsPostUsrAuthenticate(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  credentialsPostUsrRefreshToken(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  credentialsPostUsrWsInfo(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateDeleteOdrOrdersBulk(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateDeleteOdrOrdersId(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateDeleteOdrOrdersIdentifierIdentifier(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetMktCommissions(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetMktMarketsSuspensions(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetOdrFills(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetOdrOrderHistory(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetOdrOrders(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetOdrOrdersId(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetWltAccountNumbers(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetWltDeposits(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetWltNetworks(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetWltWallets(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privateGetWltWithdraws(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privatePostOdrOrders(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privatePostOdrOrdersBulk(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privatePostWltAddress(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privatePostWltWithdraws(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privatePostWltWithdrawsRetryId(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  privatePostWltWithdrawsVerifyOtpId(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  publicGetMktCandles(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  publicGetMktCurrencies(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  publicGetMktMarkets(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  publicGetMktNetworks(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  publicGetMktTickers(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  publicGetMthMatchesSymbol(params?: Record<string, unknown>, body?: unknown): Promise<any>;
  publicGetMthOrderbookSymbol(params?: Record<string, unknown>, body?: unknown): Promise<any>;
}
