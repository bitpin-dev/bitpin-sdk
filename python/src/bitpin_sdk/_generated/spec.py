# Generated from spec/bitpin.yaml by scripts/gen_python.py. Do not edit.
"""Bitpin API description: endpoints, rate limits, constants and capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Auth = Literal["public", "private", "credentials"]
Method = Literal["GET", "POST", "DELETE"]
Period = Literal["sec", "min", "hour", "day"]


@dataclass(frozen=True)
class Endpoint:
    id: str
    method: Method
    path: str
    auth: Auth
    buckets: tuple[str, ...]
    idempotent: bool


@dataclass(frozen=True)
class ErrorRule:
    status: int
    error: str
    paths: tuple[str, ...] = ()
    detail: tuple[str, ...] = ()

URLS: dict[str, str] = {'docs': 'https://docs.bitpin.ir',
 'rest': 'https://api.bitpin.org',
 'ws': 'wss://centrifugo.bitpin.org/connection/websocket'}

DOMAINS: dict[str, dict[str, str]] = {'ir': {'rest': 'https://api.bitpin.ir',
        'ws': 'wss://centrifugo.bitpin.ir/connection/websocket'},
 'market': {'rest': 'https://api.bitpin.market',
            'ws': 'wss://centrifugo.bitpin.market/connection/websocket'},
 'org': {'rest': 'https://api.bitpin.org',
         'ws': 'wss://centrifugo.bitpin.org/connection/websocket'}}

DEFAULT_DOMAIN = 'org'

CONSTANTS: dict[str, int] = {'access_token_ttl_seconds': 900,
 'bulk_orders_max': 10,
 'candles_max_per_request': 10000,
 'fills_max_age_seconds': 86400,
 'fills_max_page_size': 250,
 'order_history_default_limit': 50,
 'order_history_max_limit': 200,
 'order_history_max_range_days': 90,
 'orderbook_default_limit': 20,
 'orderbook_max_limit': 50,
 'orders_max_page_size': 250,
 'refresh_token_ttl_seconds': 2592000,
 'token_refresh_margin_seconds': 120,
 'wallet_lists_max_page_size': 1000,
 'wallets_max_page_size': 1000}

RATE_LIMITS: dict[str, tuple[int, Period]] = {'auth': (3, 'min'),
 'candles': (300, 'min'),
 'commissions': (10000, 'day'),
 'currency_networks': (60, 'min'),
 'deposit_address': (60, 'min'),
 'deposits': (60, 'min'),
 'fills': (300, 'min'),
 'market_public': (200, 'min'),
 'market_suspensions': (2, 'min'),
 'matches': (60, 'min'),
 'order_bulk_cancel': (1800, 'hour'),
 'order_bulk_create': (1800, 'hour'),
 'order_cancel': (18000, 'hour'),
 'order_create': (18000, 'hour'),
 'order_history': (5, 'sec'),
 'order_read': (18000, 'hour'),
 'orderbook': (60, 'min'),
 'refresh': (20, 'min'),
 'tickers': (300, 'min'),
 'wallet': (60, 'min'),
 'withdraw_otp': (10000, 'day'),
 'withdraws': (60, 'min'),
 'ws_info': (10, 'min')}

ENDPOINTS: dict[str, Endpoint] = {
    'credentials_post_usr_authenticate': Endpoint(
        id='credentials_post_usr_authenticate',
        method='POST',
        path='/api/v1/usr/authenticate/',
        auth='credentials',
        buckets=('auth',),
        idempotent=False,
    ),
    'credentials_post_usr_refresh_token': Endpoint(
        id='credentials_post_usr_refresh_token',
        method='POST',
        path='/api/v1/usr/refresh_token/',
        auth='credentials',
        buckets=('refresh',),
        idempotent=False,
    ),
    'credentials_post_usr_ws_info': Endpoint(
        id='credentials_post_usr_ws_info',
        method='POST',
        path='/api/v1/usr/ws-info/',
        auth='credentials',
        buckets=('ws_info',),
        idempotent=False,
    ),
    'private_delete_odr_orders_bulk': Endpoint(
        id='private_delete_odr_orders_bulk',
        method='DELETE',
        path='/api/v1/odr/orders/bulk/',
        auth='private',
        buckets=('order_bulk_cancel',),
        idempotent=False,
    ),
    'private_delete_odr_orders_id': Endpoint(
        id='private_delete_odr_orders_id',
        method='DELETE',
        path='/api/v1/odr/orders/{id}/',
        auth='private',
        buckets=('order_cancel',),
        idempotent=False,
    ),
    'private_delete_odr_orders_identifier_identifier': Endpoint(
        id='private_delete_odr_orders_identifier_identifier',
        method='DELETE',
        path='/api/v1/odr/orders/identifier/{identifier}/',
        auth='private',
        buckets=('order_cancel',),
        idempotent=False,
    ),
    'private_get_mkt_commissions': Endpoint(
        id='private_get_mkt_commissions',
        method='GET',
        path='/api/v1/mkt/commissions/',
        auth='private',
        buckets=('commissions',),
        idempotent=True,
    ),
    'private_get_mkt_markets_suspensions': Endpoint(
        id='private_get_mkt_markets_suspensions',
        method='GET',
        path='/api/v1/mkt/markets/suspensions/',
        auth='private',
        buckets=('market_suspensions',),
        idempotent=True,
    ),
    'private_get_odr_fills': Endpoint(
        id='private_get_odr_fills',
        method='GET',
        path='/api/v1/odr/fills/',
        auth='private',
        buckets=('fills',),
        idempotent=True,
    ),
    'private_get_odr_order_history': Endpoint(
        id='private_get_odr_order_history',
        method='GET',
        path='/api/v1/odr/order_history/',
        auth='private',
        buckets=('order_history',),
        idempotent=True,
    ),
    'private_get_odr_orders': Endpoint(
        id='private_get_odr_orders',
        method='GET',
        path='/api/v1/odr/orders/',
        auth='private',
        buckets=('order_read',),
        idempotent=True,
    ),
    'private_get_odr_orders_id': Endpoint(
        id='private_get_odr_orders_id',
        method='GET',
        path='/api/v1/odr/orders/{id}/',
        auth='private',
        buckets=('order_read',),
        idempotent=True,
    ),
    'private_get_wlt_account_numbers': Endpoint(
        id='private_get_wlt_account_numbers',
        method='GET',
        path='/api/v1/wlt/account_numbers/',
        auth='private',
        buckets=('wallet',),
        idempotent=True,
    ),
    'private_get_wlt_deposits': Endpoint(
        id='private_get_wlt_deposits',
        method='GET',
        path='/api/v2/wlt/deposits/',
        auth='private',
        buckets=('deposits',),
        idempotent=True,
    ),
    'private_get_wlt_networks': Endpoint(
        id='private_get_wlt_networks',
        method='GET',
        path='/api/v2/wlt/networks/',
        auth='private',
        buckets=('currency_networks',),
        idempotent=True,
    ),
    'private_get_wlt_wallets': Endpoint(
        id='private_get_wlt_wallets',
        method='GET',
        path='/api/v1/wlt/wallets/',
        auth='private',
        buckets=('wallet',),
        idempotent=True,
    ),
    'private_get_wlt_withdraws': Endpoint(
        id='private_get_wlt_withdraws',
        method='GET',
        path='/api/v2/wlt/withdraws/',
        auth='private',
        buckets=('withdraws',),
        idempotent=True,
    ),
    'private_post_odr_orders': Endpoint(
        id='private_post_odr_orders',
        method='POST',
        path='/api/v1/odr/orders/',
        auth='private',
        buckets=('order_create',),
        idempotent=False,
    ),
    'private_post_odr_orders_bulk': Endpoint(
        id='private_post_odr_orders_bulk',
        method='POST',
        path='/api/v1/odr/orders/bulk/',
        auth='private',
        buckets=('order_bulk_create', 'order_bulk_cancel'),
        idempotent=False,
    ),
    'private_post_wlt_address': Endpoint(
        id='private_post_wlt_address',
        method='POST',
        path='/api/v2/wlt/address/',
        auth='private',
        buckets=('deposit_address',),
        idempotent=True,
    ),
    'private_post_wlt_withdraws': Endpoint(
        id='private_post_wlt_withdraws',
        method='POST',
        path='/api/v2/wlt/withdraws/',
        auth='private',
        buckets=('withdraws',),
        idempotent=False,
    ),
    'private_post_wlt_withdraws_retry_id': Endpoint(
        id='private_post_wlt_withdraws_retry_id',
        method='POST',
        path='/api/v1/wlt/withdraws/retry/{id}/',
        auth='private',
        buckets=('withdraw_otp',),
        idempotent=False,
    ),
    'private_post_wlt_withdraws_verify_otp_id': Endpoint(
        id='private_post_wlt_withdraws_verify_otp_id',
        method='POST',
        path='/api/v1/wlt/withdraws/verify/otp/{id}/',
        auth='private',
        buckets=('withdraw_otp',),
        idempotent=False,
    ),
    'public_get_mkt_candles': Endpoint(
        id='public_get_mkt_candles',
        method='GET',
        path='/api/v1/mkt/candles/',
        auth='public',
        buckets=('candles',),
        idempotent=True,
    ),
    'public_get_mkt_currencies': Endpoint(
        id='public_get_mkt_currencies',
        method='GET',
        path='/api/v1/mkt/currencies/',
        auth='public',
        buckets=('market_public',),
        idempotent=True,
    ),
    'public_get_mkt_markets': Endpoint(
        id='public_get_mkt_markets',
        method='GET',
        path='/api/v1/mkt/markets/',
        auth='public',
        buckets=('market_public',),
        idempotent=True,
    ),
    'public_get_mkt_networks': Endpoint(
        id='public_get_mkt_networks',
        method='GET',
        path='/api/v1/mkt/networks/',
        auth='public',
        buckets=('market_public',),
        idempotent=True,
    ),
    'public_get_mkt_tickers': Endpoint(
        id='public_get_mkt_tickers',
        method='GET',
        path='/api/v1/mkt/tickers/',
        auth='public',
        buckets=('tickers',),
        idempotent=True,
    ),
    'public_get_mth_matches_symbol': Endpoint(
        id='public_get_mth_matches_symbol',
        method='GET',
        path='/api/v1/mth/matches/{symbol}/',
        auth='public',
        buckets=('matches',),
        idempotent=True,
    ),
    'public_get_mth_orderbook_symbol': Endpoint(
        id='public_get_mth_orderbook_symbol',
        method='GET',
        path='/api/v1/mth/orderbook/{symbol}/',
        auth='public',
        buckets=('orderbook',),
        idempotent=True,
    ),
}

ERROR_RULES: tuple[ErrorRule, ...] = (
    ErrorRule(status=429, error='RateLimitExceeded', paths=(), detail=()),
    ErrorRule(status=401, error='AuthenticationError', paths=(), detail=()),
    ErrorRule(status=406, error='AuthenticationError', paths=('credentials_post_usr_authenticate', 'credentials_post_usr_ws_info'), detail=()),
    ErrorRule(status=403, error='PermissionDenied', paths=(), detail=()),
    ErrorRule(status=404, error='OrderNotFound', paths=('private_get_odr_orders_id', 'private_delete_odr_orders'), detail=()),
    ErrorRule(status=404, error='BadRequest', paths=(), detail=()),
    ErrorRule(status=406, error='InsufficientFunds', paths=(), detail=('insufficent_balance', 'insufficent_frozen', 'insufficent_pool_balance', 'insufficient')),
    ErrorRule(status=406, error='InvalidOrder', paths=(), detail=('cancel_order_not_allowed', 'not allowed')),
    ErrorRule(status=400, error='InvalidOTP', paths=(), detail=('invalid_otp', 'otp1_already_verified', 'extra_try')),
    ErrorRule(status=400, error='InvalidOrder', paths=('private_post_odr_orders',), detail=()),
    ErrorRule(status=400, error='BadRequest', paths=(), detail=()),
    ErrorRule(status=406, error='ExchangeError', paths=(), detail=()),
    ErrorRule(status=500, error='ExchangeNotAvailable', paths=(), detail=()),
    ErrorRule(status=502, error='ExchangeNotAvailable', paths=(), detail=()),
    ErrorRule(status=503, error='ExchangeNotAvailable', paths=(), detail=()),
    ErrorRule(status=504, error='ExchangeNotAvailable', paths=(), detail=()),
)

HAS: dict[str, bool] = {'cancelAllOrders': False,
 'cancelOrder': True,
 'cancelOrders': True,
 'createDepositAddress': False,
 'createOrder': True,
 'createOrders': True,
 'editOrder': False,
 'fetchAccounts': False,
 'fetchBalance': True,
 'fetchClosedOrders': True,
 'fetchCurrencies': True,
 'fetchDepositAddress': True,
 'fetchDepositWithdrawFees': False,
 'fetchDeposits': True,
 'fetchLedger': False,
 'fetchMarkets': True,
 'fetchMyTrades': True,
 'fetchOHLCV': True,
 'fetchOpenOrders': True,
 'fetchOrder': True,
 'fetchOrderBook': True,
 'fetchOrders': True,
 'fetchPositions': False,
 'fetchTicker': True,
 'fetchTickers': True,
 'fetchTrades': True,
 'fetchTradingFee': True,
 'fetchTradingFees': True,
 'fetchWithdrawals': True,
 'sandbox': False,
 'setLeverage': False,
 'transfer': False,
 'watchBalance': False,
 'watchMyTrades': True,
 'watchOHLCV': True,
 'watchOrderBook': True,
 'watchOrders': True,
 'watchTicker': True,
 'watchTickers': False,
 'watchTrades': True,
 'withdraw': True}

NOT_SUPPORTED: dict[str, tuple[str, str]] = {'cancelAllOrders': ("Bitpin doesn't offer cancel-all yet. Use cancel_orders() with up to 10 "
                     'ids at a time.',
                     'بیت\u200cپین فعلاً لغو همهٔ سفارش\u200cها را ارائه نمی\u200cدهد. از '
                     'cancel_orders() با حداکثر ۱۰ شناسه در هر درخواست استفاده کنید.'),
 'createDepositAddress': ('Bitpin gives each user one address per network. Use '
                          'fetch_deposit_address(), which creates it on first use.',
                          'بیت\u200cپین برای هر کاربر روی هر شبکه یک آدرس می\u200cدهد. از '
                          'fetch_deposit_address() استفاده کنید؛ بار اول آدرس را '
                          'می\u200cسازد.'),
 'editOrder': ("Bitpin doesn't support editing orders yet. Cancel the order and place a new "
               'one.',
               'بیت\u200cپین فعلاً ویرایش سفارش را پشتیبانی نمی\u200cکند. سفارش را لغو کنید و '
               'سفارش جدید ثبت کنید.'),
 'fetchAccounts': ("Bitpin doesn't offer account or user info through the public API yet.",
                   'بیت\u200cپین فعلاً اطلاعات حساب کاربری را از طریق API عمومی ارائه '
                   'نمی\u200cدهد.'),
 'fetchDepositWithdrawFees': ("Bitpin doesn't offer a deposit/withdraw fee endpoint yet. The "
                              'fee of a withdrawal is returned when you create it.',
                              'بیت\u200cپین فعلاً سرویس کارمزد واریز و برداشت ارائه '
                              'نمی\u200cدهد. کارمزد هر برداشت هنگام ثبت آن برگردانده '
                              'می\u200cشود.'),
 'fetchLedger': ("Bitpin doesn't offer a ledger endpoint yet. Use fetch_deposits(), "
                 'fetch_withdrawals() and fetch_my_trades().',
                 'بیت\u200cپین فعلاً دفتر کل (ledger) ارائه نمی\u200cدهد. از fetch_deposits()، '
                 'fetch_withdrawals() و fetch_my_trades() استفاده کنید.'),
 'fetchPositions': ("Bitpin doesn't offer margin or positions through the public API yet.",
                    'بیت\u200cپین فعلاً معاملات اهرمی و پوزیشن\u200cها را از طریق API عمومی '
                    'ارائه نمی\u200cدهد.'),
 'sandbox': ('Bitpin has no sandbox or testnet. Every call reaches the real exchange; the '
             'examples default to dry-run.',
             'بیت\u200cپین محیط آزمایشی (sandbox) ندارد. هر درخواست به صرافی واقعی '
             'می\u200cرسد؛ مثال\u200cها به\u200cصورت پیش\u200cفرض اجرای آزمایشی دارند.'),
 'setLeverage': ("Bitpin doesn't offer margin or leverage through the public API yet.",
                 'بیت\u200cپین فعلاً معاملات اهرمی را از طریق API عمومی ارائه نمی\u200cدهد.'),
 'transfer': ("Bitpin doesn't offer transfers between wallet services through the public API "
              'yet.',
              'بیت\u200cپین فعلاً انتقال بین سرویس\u200cهای کیف پول را از طریق API عمومی ارائه '
              'نمی\u200cدهد.'),
 'watchBalance': ("Bitpin doesn't publish balance updates over WebSocket yet. Poll "
                  'fetch_balance().',
                  'بیت\u200cپین فعلاً تغییرات موجودی را روی وب\u200cسوکت منتشر نمی\u200cکند. '
                  'از fetch_balance() استفاده کنید.'),
 'watchTickers': ("Bitpin doesn't document an all-markets ticker channel yet. Use "
                  'watch_ticker() per symbol or fetch_tickers().',
                  'بیت\u200cپین فعلاً کانال قیمت همهٔ بازارها را مستند نکرده است. از '
                  'watch_ticker() برای هر بازار یا fetch_tickers() استفاده کنید.')}

WS_CHANNELS: dict[str, str] = {'market': 'market:{symbol}',
 'matches': 'matches:{symbol}',
 'orderbook': 'orderbook:{symbol}',
 'user_orders': 'user:order_info#{user_identifier}'}

WS_EVENTS: dict[str, str] = {'candle_update': 'market',
 'currency_price_update': 'market',
 'market_data': 'orderbook',
 'matches_update': 'matches',
 'user_match_update': 'user_orders',
 'user_order_update': 'user_orders'}
