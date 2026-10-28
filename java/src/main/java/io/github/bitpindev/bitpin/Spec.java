// Code generated from spec/bitpin.yaml by scripts/gen_java.py. DO NOT EDIT.

package io.github.bitpindev.bitpin;

import java.util.List;
import java.util.Map;

/** The values of spec/bitpin.yaml. */
final class Spec {
  private Spec() {}

  /** Domains Bitpin serves the API on; REST and WebSocket switch together. */
  static final Map<String, List<String>> DOMAINS =
      Map.ofEntries(
          Map.entry("ir", List.of("https://api.bitpin.ir", "wss://centrifugo.bitpin.ir/connection/websocket")),
          Map.entry("market", List.of("https://api.bitpin.market", "wss://centrifugo.bitpin.market/connection/websocket")),
          Map.entry("org", List.of("https://api.bitpin.org", "wss://centrifugo.bitpin.org/connection/websocket")));

  static final String DEFAULT_DOMAIN = "org";

  static final String DOCS_URL = "https://docs.bitpin.ir";

  static final Map<String, Integer> CONSTANTS =
      Map.ofEntries(
          Map.entry("access_token_ttl_seconds", 900),
          Map.entry("bulk_orders_max", 10),
          Map.entry("candles_max_per_request", 10000),
          Map.entry("fills_max_age_seconds", 86400),
          Map.entry("fills_max_page_size", 250),
          Map.entry("order_history_default_limit", 50),
          Map.entry("order_history_max_limit", 200),
          Map.entry("order_history_max_range_days", 90),
          Map.entry("orderbook_default_limit", 20),
          Map.entry("orderbook_max_limit", 50),
          Map.entry("orders_max_page_size", 250),
          Map.entry("refresh_token_ttl_seconds", 2592000),
          Map.entry("token_refresh_margin_seconds", 120),
          Map.entry("wallet_lists_max_page_size", 1000),
          Map.entry("wallets_max_page_size", 1000));

  static final Map<String, RateLimit> RATE_LIMITS =
      Map.ofEntries(
          Map.entry("auth", new RateLimit(3, "min")),
          Map.entry("candles", new RateLimit(300, "min")),
          Map.entry("commissions", new RateLimit(10000, "day")),
          Map.entry("currency_networks", new RateLimit(60, "min")),
          Map.entry("deposit_address", new RateLimit(60, "min")),
          Map.entry("deposits", new RateLimit(60, "min")),
          Map.entry("fills", new RateLimit(300, "min")),
          Map.entry("market_public", new RateLimit(200, "min")),
          Map.entry("market_suspensions", new RateLimit(2, "min")),
          Map.entry("matches", new RateLimit(60, "min")),
          Map.entry("order_bulk_cancel", new RateLimit(1800, "hour")),
          Map.entry("order_bulk_create", new RateLimit(1800, "hour")),
          Map.entry("order_cancel", new RateLimit(18000, "hour")),
          Map.entry("order_create", new RateLimit(18000, "hour")),
          Map.entry("order_history", new RateLimit(5, "sec")),
          Map.entry("order_read", new RateLimit(18000, "hour")),
          Map.entry("orderbook", new RateLimit(60, "min")),
          Map.entry("refresh", new RateLimit(20, "min")),
          Map.entry("tickers", new RateLimit(300, "min")),
          Map.entry("wallet", new RateLimit(60, "min")),
          Map.entry("withdraw_otp", new RateLimit(10000, "day")),
          Map.entry("withdraws", new RateLimit(60, "min")),
          Map.entry("ws_info", new RateLimit(10, "min")));

  static final Map<String, Endpoint> ENDPOINTS =
      Map.ofEntries(
          Map.entry(
              "credentials_post_usr_authenticate",
              new Endpoint(
                  "credentials_post_usr_authenticate",
                  "POST",
                  "/api/v1/usr/authenticate/",
                  "credentials",
                  List.of("auth"),
                  false)),
          Map.entry(
              "credentials_post_usr_refresh_token",
              new Endpoint(
                  "credentials_post_usr_refresh_token",
                  "POST",
                  "/api/v1/usr/refresh_token/",
                  "credentials",
                  List.of("refresh"),
                  false)),
          Map.entry(
              "credentials_post_usr_ws_info",
              new Endpoint(
                  "credentials_post_usr_ws_info",
                  "POST",
                  "/api/v1/usr/ws-info/",
                  "credentials",
                  List.of("ws_info"),
                  false)),
          Map.entry(
              "private_delete_odr_orders_bulk",
              new Endpoint(
                  "private_delete_odr_orders_bulk",
                  "DELETE",
                  "/api/v1/odr/orders/bulk/",
                  "private",
                  List.of("order_bulk_cancel"),
                  false)),
          Map.entry(
              "private_delete_odr_orders_id",
              new Endpoint(
                  "private_delete_odr_orders_id",
                  "DELETE",
                  "/api/v1/odr/orders/{id}/",
                  "private",
                  List.of("order_cancel"),
                  false)),
          Map.entry(
              "private_delete_odr_orders_identifier_identifier",
              new Endpoint(
                  "private_delete_odr_orders_identifier_identifier",
                  "DELETE",
                  "/api/v1/odr/orders/identifier/{identifier}/",
                  "private",
                  List.of("order_cancel"),
                  false)),
          Map.entry(
              "private_get_mkt_commissions",
              new Endpoint(
                  "private_get_mkt_commissions",
                  "GET",
                  "/api/v1/mkt/commissions/",
                  "private",
                  List.of("commissions"),
                  true)),
          Map.entry(
              "private_get_mkt_markets_suspensions",
              new Endpoint(
                  "private_get_mkt_markets_suspensions",
                  "GET",
                  "/api/v1/mkt/markets/suspensions/",
                  "private",
                  List.of("market_suspensions"),
                  true)),
          Map.entry(
              "private_get_odr_fills",
              new Endpoint(
                  "private_get_odr_fills",
                  "GET",
                  "/api/v1/odr/fills/",
                  "private",
                  List.of("fills"),
                  true)),
          Map.entry(
              "private_get_odr_order_history",
              new Endpoint(
                  "private_get_odr_order_history",
                  "GET",
                  "/api/v1/odr/order_history/",
                  "private",
                  List.of("order_history"),
                  true)),
          Map.entry(
              "private_get_odr_orders",
              new Endpoint(
                  "private_get_odr_orders",
                  "GET",
                  "/api/v1/odr/orders/",
                  "private",
                  List.of("order_read"),
                  true)),
          Map.entry(
              "private_get_odr_orders_id",
              new Endpoint(
                  "private_get_odr_orders_id",
                  "GET",
                  "/api/v1/odr/orders/{id}/",
                  "private",
                  List.of("order_read"),
                  true)),
          Map.entry(
              "private_get_wlt_account_numbers",
              new Endpoint(
                  "private_get_wlt_account_numbers",
                  "GET",
                  "/api/v1/wlt/account_numbers/",
                  "private",
                  List.of("wallet"),
                  true)),
          Map.entry(
              "private_get_wlt_deposits",
              new Endpoint(
                  "private_get_wlt_deposits",
                  "GET",
                  "/api/v2/wlt/deposits/",
                  "private",
                  List.of("deposits"),
                  true)),
          Map.entry(
              "private_get_wlt_networks",
              new Endpoint(
                  "private_get_wlt_networks",
                  "GET",
                  "/api/v2/wlt/networks/",
                  "private",
                  List.of("currency_networks"),
                  true)),
          Map.entry(
              "private_get_wlt_wallets",
              new Endpoint(
                  "private_get_wlt_wallets",
                  "GET",
                  "/api/v1/wlt/wallets/",
                  "private",
                  List.of("wallet"),
                  true)),
          Map.entry(
              "private_get_wlt_withdraws",
              new Endpoint(
                  "private_get_wlt_withdraws",
                  "GET",
                  "/api/v2/wlt/withdraws/",
                  "private",
                  List.of("withdraws"),
                  true)),
          Map.entry(
              "private_post_odr_orders",
              new Endpoint(
                  "private_post_odr_orders",
                  "POST",
                  "/api/v1/odr/orders/",
                  "private",
                  List.of("order_create"),
                  false)),
          Map.entry(
              "private_post_odr_orders_bulk",
              new Endpoint(
                  "private_post_odr_orders_bulk",
                  "POST",
                  "/api/v1/odr/orders/bulk/",
                  "private",
                  List.of("order_bulk_create", "order_bulk_cancel"),
                  false)),
          Map.entry(
              "private_post_wlt_address",
              new Endpoint(
                  "private_post_wlt_address",
                  "POST",
                  "/api/v2/wlt/address/",
                  "private",
                  List.of("deposit_address"),
                  true)),
          Map.entry(
              "private_post_wlt_withdraws",
              new Endpoint(
                  "private_post_wlt_withdraws",
                  "POST",
                  "/api/v2/wlt/withdraws/",
                  "private",
                  List.of("withdraws"),
                  false)),
          Map.entry(
              "private_post_wlt_withdraws_retry_id",
              new Endpoint(
                  "private_post_wlt_withdraws_retry_id",
                  "POST",
                  "/api/v1/wlt/withdraws/retry/{id}/",
                  "private",
                  List.of("withdraw_otp"),
                  false)),
          Map.entry(
              "private_post_wlt_withdraws_verify_otp_id",
              new Endpoint(
                  "private_post_wlt_withdraws_verify_otp_id",
                  "POST",
                  "/api/v1/wlt/withdraws/verify/otp/{id}/",
                  "private",
                  List.of("withdraw_otp"),
                  false)),
          Map.entry(
              "public_get_mkt_candles",
              new Endpoint(
                  "public_get_mkt_candles",
                  "GET",
                  "/api/v1/mkt/candles/",
                  "public",
                  List.of("candles"),
                  true)),
          Map.entry(
              "public_get_mkt_currencies",
              new Endpoint(
                  "public_get_mkt_currencies",
                  "GET",
                  "/api/v1/mkt/currencies/",
                  "public",
                  List.of("market_public"),
                  true)),
          Map.entry(
              "public_get_mkt_markets",
              new Endpoint(
                  "public_get_mkt_markets",
                  "GET",
                  "/api/v1/mkt/markets/",
                  "public",
                  List.of("market_public"),
                  true)),
          Map.entry(
              "public_get_mkt_networks",
              new Endpoint(
                  "public_get_mkt_networks",
                  "GET",
                  "/api/v1/mkt/networks/",
                  "public",
                  List.of("market_public"),
                  true)),
          Map.entry(
              "public_get_mkt_tickers",
              new Endpoint(
                  "public_get_mkt_tickers",
                  "GET",
                  "/api/v1/mkt/tickers/",
                  "public",
                  List.of("tickers"),
                  true)),
          Map.entry(
              "public_get_mth_matches_symbol",
              new Endpoint(
                  "public_get_mth_matches_symbol",
                  "GET",
                  "/api/v1/mth/matches/{symbol}/",
                  "public",
                  List.of("matches"),
                  true)),
          Map.entry(
              "public_get_mth_orderbook_symbol",
              new Endpoint(
                  "public_get_mth_orderbook_symbol",
                  "GET",
                  "/api/v1/mth/orderbook/{symbol}/",
                  "public",
                  List.of("orderbook"),
                  true)));

  static final List<ErrorRule> ERROR_RULES =
      List.of(
          new ErrorRule(429, "RateLimitExceeded", List.of(), List.of()),
          new ErrorRule(401, "AuthenticationError", List.of(), List.of()),
          new ErrorRule(406, "AuthenticationError", List.of("credentials_post_usr_authenticate", "credentials_post_usr_ws_info"), List.of()),
          new ErrorRule(403, "PermissionDenied", List.of(), List.of()),
          new ErrorRule(404, "OrderNotFound", List.of("private_get_odr_orders_id", "private_delete_odr_orders"), List.of()),
          new ErrorRule(404, "BadRequest", List.of(), List.of()),
          new ErrorRule(406, "InsufficientFunds", List.of(), List.of("insufficent_balance", "insufficent_frozen", "insufficent_pool_balance", "insufficient")),
          new ErrorRule(406, "InvalidOrder", List.of(), List.of("cancel_order_not_allowed", "not allowed")),
          new ErrorRule(400, "InvalidOTP", List.of(), List.of("invalid_otp", "otp1_already_verified", "extra_try")),
          new ErrorRule(400, "InvalidOrder", List.of("private_post_odr_orders"), List.of()),
          new ErrorRule(400, "BadRequest", List.of(), List.of()),
          new ErrorRule(406, "ExchangeError", List.of(), List.of()),
          new ErrorRule(500, "ExchangeNotAvailable", List.of(), List.of()),
          new ErrorRule(502, "ExchangeNotAvailable", List.of(), List.of()),
          new ErrorRule(503, "ExchangeNotAvailable", List.of(), List.of()),
          new ErrorRule(504, "ExchangeNotAvailable", List.of(), List.of()));

  /** The ccxt-style capability map: false means Bitpin doesn't offer it yet. */
  static final Map<String, Boolean> HAS =
      Map.ofEntries(
          Map.entry("cancelAllOrders", false),
          Map.entry("cancelOrder", true),
          Map.entry("cancelOrders", true),
          Map.entry("createDepositAddress", false),
          Map.entry("createOrder", true),
          Map.entry("createOrders", true),
          Map.entry("editOrder", false),
          Map.entry("fetchAccounts", false),
          Map.entry("fetchBalance", true),
          Map.entry("fetchClosedOrders", true),
          Map.entry("fetchCurrencies", true),
          Map.entry("fetchDepositAddress", true),
          Map.entry("fetchDepositWithdrawFees", false),
          Map.entry("fetchDeposits", true),
          Map.entry("fetchLedger", false),
          Map.entry("fetchMarkets", true),
          Map.entry("fetchMyTrades", true),
          Map.entry("fetchOHLCV", true),
          Map.entry("fetchOpenOrders", true),
          Map.entry("fetchOrder", true),
          Map.entry("fetchOrderBook", true),
          Map.entry("fetchOrders", true),
          Map.entry("fetchPositions", false),
          Map.entry("fetchTicker", true),
          Map.entry("fetchTickers", true),
          Map.entry("fetchTrades", true),
          Map.entry("fetchTradingFee", true),
          Map.entry("fetchTradingFees", true),
          Map.entry("fetchWithdrawals", true),
          Map.entry("sandbox", false),
          Map.entry("setLeverage", false),
          Map.entry("transfer", false),
          Map.entry("watchBalance", false),
          Map.entry("watchMyTrades", true),
          Map.entry("watchOHLCV", true),
          Map.entry("watchOrderBook", true),
          Map.entry("watchOrders", true),
          Map.entry("watchTicker", true),
          Map.entry("watchTickers", false),
          Map.entry("watchTrades", true),
          Map.entry("withdraw", true));

  /** English and Persian messages for each missing capability. */
  static final Map<String, List<String>> NOT_SUPPORTED =
      Map.ofEntries(
          Map.entry(
              "cancelAllOrders",
              List.of(
                  "Bitpin doesn't offer cancel-all yet. Use cancel_orders() with up to 10 ids at a time.",
                  "بیت\u200cپین فعلاً لغو همهٔ سفارش\u200cها را ارائه نمی\u200cدهد. از cancel_orders() با حداکثر ۱۰ شناسه در هر درخواست استفاده کنید.")),
          Map.entry(
              "createDepositAddress",
              List.of(
                  "Bitpin gives each user one address per network. Use fetch_deposit_address(), which creates it on first use.",
                  "بیت\u200cپین برای هر کاربر روی هر شبکه یک آدرس می\u200cدهد. از fetch_deposit_address() استفاده کنید؛ بار اول آدرس را می\u200cسازد.")),
          Map.entry(
              "editOrder",
              List.of(
                  "Bitpin doesn't support editing orders yet. Cancel the order and place a new one.",
                  "بیت\u200cپین فعلاً ویرایش سفارش را پشتیبانی نمی\u200cکند. سفارش را لغو کنید و سفارش جدید ثبت کنید.")),
          Map.entry(
              "fetchAccounts",
              List.of(
                  "Bitpin doesn't offer account or user info through the public API yet.",
                  "بیت\u200cپین فعلاً اطلاعات حساب کاربری را از طریق API عمومی ارائه نمی\u200cدهد.")),
          Map.entry(
              "fetchDepositWithdrawFees",
              List.of(
                  "Bitpin doesn't offer a deposit/withdraw fee endpoint yet. The fee of a withdrawal is returned when you create it.",
                  "بیت\u200cپین فعلاً سرویس کارمزد واریز و برداشت ارائه نمی\u200cدهد. کارمزد هر برداشت هنگام ثبت آن برگردانده می\u200cشود.")),
          Map.entry(
              "fetchLedger",
              List.of(
                  "Bitpin doesn't offer a ledger endpoint yet. Use fetch_deposits(), fetch_withdrawals() and fetch_my_trades().",
                  "بیت\u200cپین فعلاً دفتر کل (ledger) ارائه نمی\u200cدهد. از fetch_deposits()، fetch_withdrawals() و fetch_my_trades() استفاده کنید.")),
          Map.entry(
              "fetchPositions",
              List.of(
                  "Bitpin doesn't offer margin or positions through the public API yet.",
                  "بیت\u200cپین فعلاً معاملات اهرمی و پوزیشن\u200cها را از طریق API عمومی ارائه نمی\u200cدهد.")),
          Map.entry(
              "sandbox",
              List.of(
                  "Bitpin has no sandbox or testnet. Every call reaches the real exchange; the examples default to dry-run.",
                  "بیت\u200cپین محیط آزمایشی (sandbox) ندارد. هر درخواست به صرافی واقعی می\u200cرسد؛ مثال\u200cها به\u200cصورت پیش\u200cفرض اجرای آزمایشی دارند.")),
          Map.entry(
              "setLeverage",
              List.of(
                  "Bitpin doesn't offer margin or leverage through the public API yet.",
                  "بیت\u200cپین فعلاً معاملات اهرمی را از طریق API عمومی ارائه نمی\u200cدهد.")),
          Map.entry(
              "transfer",
              List.of(
                  "Bitpin doesn't offer transfers between wallet services through the public API yet.",
                  "بیت\u200cپین فعلاً انتقال بین سرویس\u200cهای کیف پول را از طریق API عمومی ارائه نمی\u200cدهد.")),
          Map.entry(
              "watchBalance",
              List.of(
                  "Bitpin doesn't publish balance updates over WebSocket yet. Poll fetch_balance().",
                  "بیت\u200cپین فعلاً تغییرات موجودی را روی وب\u200cسوکت منتشر نمی\u200cکند. از fetch_balance() استفاده کنید.")),
          Map.entry(
              "watchTickers",
              List.of(
                  "Bitpin doesn't document an all-markets ticker channel yet. Use watch_ticker() per symbol or fetch_tickers().",
                  "بیت\u200cپین فعلاً کانال قیمت همهٔ بازارها را مستند نکرده است. از watch_ticker() برای هر بازار یا fetch_tickers() استفاده کنید.")));

  static final Map<String, String> WS_CHANNELS =
      Map.ofEntries(
          Map.entry("market", "market:{symbol}"),
          Map.entry("matches", "matches:{symbol}"),
          Map.entry("orderbook", "orderbook:{symbol}"),
          Map.entry("user_orders", "user:order_info#{user_identifier}"));
}
