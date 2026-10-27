package bitpin

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

var ctx = context.Background()

func TestTransport(t *testing.T) {
	e := newEnv(t)
	tickers := e.http.endpoint(t, "public_get_mkt_tickers")
	must[any](t)(e.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil))
	eq(t, []string{tickers.last().Header.Get("Authorization"), tickers.last().Header.Get("User-Agent"), tickers.last().Header.Get("Accept")}, []string{"", "bitpin-sdk-go/" + Version, "application/json"})

	wallets := e.http.endpoint(t, "private_get_wlt_wallets")
	must[any](t)(e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	must[any](t)(e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	eq(t, e.auth.count(), 1)
	eq(t, e.auth.last().Body, map[string]any{"api_key": "test-key", "secret_key": "test-secret"})
	eq(t, wallets.last().Header.Get("Authorization"), "Bearer "+str(asMap(fixtureBody(t, "credentials_post_usr_authenticate"))["access"]))

	anon, _ := New(Config{HTTPClient: &http.Client{Transport: e.http}})
	if _, err := anon.Request(ctx, "private_get_wlt_wallets", nil, nil, nil); !errors.Is(err, ErrAuthentication) {
		t.Error(err)
	}
	if _, err := New(Config{Domain: "com"}); err == nil {
		t.Error("bad config")
	}
	if _, err := e.client.Request(ctx, "nope", nil, nil, nil); err == nil {
		t.Error("unknown endpoint")
	}
}

func TestRefreshAndReauthenticate(t *testing.T) {
	e := newEnv(t)
	auth := e.http.endpoint(t, "credentials_post_usr_authenticate", reply{status: 200, body: map[string]any{"access": makeJWT(testNow + 900), "refresh": makeJWT(testNow + 86400)}})
	refresh := e.http.endpoint(t, "credentials_post_usr_refresh_token", reply{status: 200, body: map[string]any{"access": makeJWT(testNow + 1800)}})
	wallets := e.http.endpoint(t, "private_get_wlt_wallets")
	must[any](t)(e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	e.time.advance(840)
	must[any](t)(e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	eq(t, refresh.count(), 1)
	eq(t, refresh.last().Body, map[string]any{"refresh": makeJWT(testNow + 86400)})
	eq(t, wallets.last().Header.Get("Authorization"), "Bearer "+makeJWT(testNow+1800))
	e.http.endpoint(t, "credentials_post_usr_refresh_token", reply{status: 401, body: map[string]any{"detail": "expired"}})
	e.time.advance(1800)
	must[any](t)(e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	eq(t, auth.count(), 2)
	e.http.endpoint(t, "credentials_post_usr_refresh_token", reply{status: 503})
	e.time.advance(1800)
	if _, err := e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil); !errors.Is(err, ErrExchangeNotAvailable) {
		t.Error(err)
	}
}

func TestUnauthorizedRetriesOnce(t *testing.T) {
	e := newEnv(t)
	e.http.endpoint(t, "credentials_post_usr_refresh_token")
	w := e.http.on("GET", "/api/v1/wlt/wallets/", reply{status: 401, body: map[string]any{"detail": "revoked"}}, reply{status: 200, body: []any{}})
	must[any](t)(e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	eq(t, []int{w.count(), e.auth.count()}, []int{2, 1})
	e.http.endpoint(t, "private_get_wlt_wallets", reply{status: 401, body: map[string]any{"detail": "revoked"}})
	if _, err := e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil); !errors.Is(err, ErrAuthentication) {
		t.Error(err)
	}
}

func TestConcurrentCallsAuthenticateOnce(t *testing.T) {
	e := newEnv(t)
	e.http.endpoint(t, "private_get_wlt_wallets")
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil)
		}()
	}
	wg.Wait()
	eq(t, e.auth.count(), 1)
}

func TestTokenStoreSharing(t *testing.T) {
	store := &MemoryTokenStore{}
	a := newEnv(t, func(c *Config) { c.TokenStore = store })
	a.http.endpoint(t, "private_get_wlt_wallets")
	must[any](t)(a.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	b, _ := New(Config{APIKey: "test-key", SecretKey: "test-secret", HTTPClient: &http.Client{Transport: a.http}, TokenStore: store, Clock: a.time.Clock, Sleep: a.time.Sleep})
	must[any](t)(b.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	eq(t, a.auth.count(), 1)
}

func TestRetries(t *testing.T) {
	e := newEnv(t)
	tk := e.http.on("GET", "/api/v1/mkt/tickers/", reply{err: errors.New("connection reset")}, reply{status: 200, body: []any{}})
	must[any](t)(e.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil))
	eq(t, []any{tk.count(), e.time.slept()}, []any{2, []float64{0.5}})

	few := newEnv(t, func(c *Config) { c.MaxRetries = Int(2) })
	down := few.http.endpoint(t, "public_get_mkt_tickers", reply{status: 503})
	if _, err := few.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil); !errors.Is(err, ErrExchangeNotAvailable) {
		t.Error(err)
	}
	eq(t, []any{down.count(), few.time.slept()}, []any{3, []float64{0.5, 1}})

	for _, failure := range []reply{{status: 429, body: map[string]any{"detail": "Expected available in 1 seconds."}}, {err: timeoutErr{}}, {status: 503}} {
		w := newEnv(t)
		orders := w.http.on("POST", "/api/v1/odr/orders/", failure, reply{status: 201, body: map[string]any{}})
		if _, err := w.client.Request(ctx, "private_post_odr_orders", nil, nil, Params{"symbol": "BTC_IRT"}); !errors.Is(err, ErrNetwork) {
			t.Error(err)
		}
		eq(t, orders.count(), 1)
	}

	short := newEnv(t)
	short.http.on("GET", "/api/v1/mkt/tickers/", reply{status: 429, body: map[string]any{"detail": "Expected available in 2 seconds."}}, reply{status: 200, body: []any{}})
	must[any](t)(short.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil))
	eq(t, short.time.slept(), []float64{2})
	short.http.endpoint(t, "public_get_mkt_tickers", reply{status: 429, body: map[string]any{"detail": "Expected available in 86398 seconds."}})
	_, err := short.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil)
	var be *Error
	if !errors.As(err, &be) || be.RetryAfter != 86398 {
		t.Error(err)
	}

	none := newEnv(t, func(c *Config) { c.MaxRetries = Int(0) })
	none.http.on("GET", "/api/v1/mkt/tickers/", reply{err: timeoutErr{}})
	if _, err := none.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil); !errors.Is(err, ErrRequestTimeout) {
		t.Error(err)
	}
	none.http.on("GET", "/api/v1/mkt/tickers/", reply{err: errors.New("down")})
	_, err = none.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil)
	if !errors.As(err, &be) || be.Kind != error(ErrNetwork) || errors.Unwrap(err) == nil {
		t.Error(err)
	}
}

type timeoutErr struct{}

func (timeoutErr) Error() string   { return "timeout" }
func (timeoutErr) Timeout() bool   { return true }
func (timeoutErr) Temporary() bool { return true }

func TestLimiterInClient(t *testing.T) {
	e := newEnv(t, func(c *Config) { c.RateLimits = map[string]string{"tickers": "2/min"} })
	e.http.endpoint(t, "public_get_mkt_tickers")
	for i := 0; i < 3; i++ {
		must[any](t)(e.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil))
	}
	eq(t, e.time.slept(), []float64{60})
	off := newEnv(t, func(c *Config) { c.RateLimits = map[string]string{"tickers": "1/min"}; c.DisableRateLimit = true })
	off.http.endpoint(t, "public_get_mkt_tickers")
	for i := 0; i < 3; i++ {
		must[any](t)(off.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil))
	}
	eq(t, len(off.time.slept()), 0)

	var mu sync.Mutex
	var sleeps []float64
	burst := newEnv(t, func(c *Config) {
		c.RateLimits = map[string]string{"orderbook": "2/sec"}
		c.Sleep = func(d time.Duration) <-chan time.Time {
			mu.Lock()
			sleeps = append(sleeps, d.Seconds())
			mu.Unlock()
			ch := make(chan time.Time, 1)
			ch <- time.Time{}
			return ch
		}
	})
	burst.http.endpoint(t, "public_get_mth_orderbook_symbol")
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); _, _ = burst.client.FetchOrderBook(ctx, "BTC/IRT", 0) }()
	}
	wg.Wait()
	sort.Float64s(sleeps)
	eq(t, sleeps, []float64{1, 1, 2, 2, 3, 3})

	cancelled, cancel := context.WithCancel(ctx)
	cancel()
	slow := newEnv(t, func(c *Config) {
		c.RateLimits = map[string]string{"tickers": "1/min"}
		c.Sleep = func(time.Duration) <-chan time.Time { return make(chan time.Time) }
	})
	slow.http.endpoint(t, "public_get_mkt_tickers")
	must[any](t)(slow.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil))
	if _, err := slow.client.Request(cancelled, "public_get_mkt_tickers", nil, nil, nil); !errors.Is(err, context.Canceled) {
		t.Error(err)
	}
}

func TestResponsesAndSecrets(t *testing.T) {
	e := newEnv(t, func(c *Config) { c.MaxRetries = Int(0) })
	e.http.endpoint(t, "private_delete_odr_orders_id")
	if v := must[any](t)(e.client.Request(ctx, "private_delete_odr_orders_id", Params{"id": 1}, nil, nil)); v != nil {
		t.Error("204 should be nil")
	}
	e.http.on("GET", "/api/v1/mkt/tickers/", reply{status: 502, text: "<html>bad gateway</html>"})
	_, err := e.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil)
	var be *Error
	if !errors.As(err, &be) || be.Body != "<html>bad gateway</html>" {
		t.Error(err)
	}
	e.http.on("GET", "/api/v1/mkt/tickers/", reply{status: 200, text: "not json"})
	if _, err := e.client.Request(ctx, "public_get_mkt_tickers", nil, nil, nil); err == nil || !strings.Contains(err.Error(), "invalid JSON") {
		t.Error(err)
	}
	fresh := newEnv(t, func(c *Config) { c.MaxRetries = Int(0) })
	fresh.http.endpoint(t, "credentials_post_usr_authenticate", reply{status: 406, body: map[string]any{"detail": "api_credential_wrong"}})
	_, err = fresh.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil)
	text := fmt.Sprintf("%v %+v %v %#v", err, err, fresh.client, fresh.client.Config())
	if !errors.Is(err, ErrAuthentication) || strings.Contains(text, "test-secret") || strings.Contains(text, "test-key") {
		t.Error(text)
	}
	fresh.http.on("POST", "/api/v1/usr/authenticate/", reply{err: errors.New("down")})
	_, err = fresh.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil)
	if !errors.Is(err, ErrNetwork) || errors.Unwrap(err) != nil {
		t.Errorf("credentials errors must not chain the request: %v", err)
	}
	cancelled, cancel := context.WithCancel(ctx)
	cancel()
	e.http.endpoint(t, "public_get_mkt_tickers")
	if _, err := e.client.Request(cancelled, "public_get_mkt_tickers", nil, nil, nil); !errors.Is(err, context.Canceled) {
		t.Error(err)
	}
}

func TestLate401DoesNotRefreshAgain(t *testing.T) {
	e := newEnv(t)
	first := str(asMap(fixtureBody(t, "credentials_post_usr_authenticate"))["access"])
	refresh := e.http.endpoint(t, "credentials_post_usr_refresh_token", reply{status: 200, body: map[string]any{"access": makeJWT(testNow + 5000)}})
	e.http.endpoint(t, "private_get_wlt_wallets")
	must[any](t)(e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	e.client.tokens.setAccess(makeJWT(testNow + 4000))
	e.client.tokens.expireAccess(first)
	must[any](t)(e.client.Request(ctx, "private_get_wlt_wallets", nil, nil, nil))
	eq(t, refresh.count(), 0)
}

func TestMarketData(t *testing.T) {
	e := newEnv(t)
	markets := e.http.endpoint(t, "public_get_mkt_markets")
	if _, err := e.client.Market("BTC/IRT"); err == nil {
		t.Error("not loaded")
	}
	got := must[map[string]Market](t)(e.client.LoadMarkets(ctx, false))
	must[map[string]Market](t)(e.client.LoadMarkets(ctx, false))
	eq(t, []any{len(got), markets.count(), must[Market](t)(e.client.Market("btc_irt")).ID}, []any{3, 1, "BTC_IRT"})
	if _, err := e.client.Market("DOGE/IRT"); !errors.Is(err, ErrBadSymbol) {
		t.Error(err)
	}
	if _, err := e.client.Market("bad"); !errors.Is(err, ErrBadSymbol) {
		t.Error(err)
	}
	must[map[string]Market](t)(e.client.LoadMarkets(ctx, true))
	eq(t, markets.count(), 2)

	e.http.endpoint(t, "public_get_mkt_currencies")
	eq(t, must[map[string]Currency](t)(e.client.FetchCurrencies(ctx))["BTC"].Precision.String(), "0.00000001")
	nets := e.http.endpoint(t, "public_get_mkt_networks")
	eq(t, len(must[[]Network](t)(e.client.FetchNetworks(ctx, Params{"can_deposit": true}))), 2)
	eq(t, nets.last().Query["can_deposit"], "true")
	e.http.endpoint(t, "private_get_mkt_markets_suspensions")
	eq(t, must[map[string]bool](t)(e.client.FetchMarketSuspensions(ctx)), map[string]bool{"BTC/IRT": false, "ETH/USDT": true})

	e.http.endpoint(t, "public_get_mkt_tickers")
	eq(t, len(must[map[string]Ticker](t)(e.client.FetchTickers(ctx))), 2)
	eq(t, len(must[map[string]Ticker](t)(e.client.FetchTickers(ctx, "usdt/irt"))), 1)
	eq(t, must[Ticker](t)(e.client.FetchTicker(ctx, "BTC_IRT")).Last.String(), "3145737420")
	if _, err := e.client.FetchTicker(ctx, "DOGE/IRT"); !errors.Is(err, ErrBadSymbol) {
		t.Error(err)
	}
	if _, err := e.client.FetchTickers(ctx, "bad"); !errors.Is(err, ErrBadSymbol) {
		t.Error(err)
	}

	book := e.http.endpoint(t, "public_get_mth_orderbook_symbol")
	ob := must[OrderBook](t)(e.client.FetchOrderBook(ctx, "BTC/IRT", 50))
	eq(t, []string{book.last().Path, book.last().Query["limit"], ob.Bids[0].Price.String(), ob.Asks[0].Price.String()}, []string{"/api/v1/mth/orderbook/BTC_IRT/", "50", "3140000000", "3150000000"})
	if _, err := e.client.FetchOrderBook(ctx, "BTC/IRT", 51); !errors.Is(err, ErrBadRequest) {
		t.Error(err)
	}

	e.http.endpoint(t, "public_get_mth_matches_symbol")
	ids := func(ts []Trade) []string {
		out := []string{}
		for _, x := range ts {
			out = append(out, x.ID)
		}
		return out
	}
	eq(t, ids(must[[]Trade](t)(e.client.FetchTrades(ctx, "BTC/IRT", 0, 0))), []string{"73802970_73807080", "73802972_73807087"})
	eq(t, ids(must[[]Trade](t)(e.client.FetchTrades(ctx, "BTC/IRT", 1761550510000, 0))), []string{"73802972_73807087"})
	eq(t, ids(must[[]Trade](t)(e.client.FetchTrades(ctx, "BTC/IRT", 0, 1))), []string{"73802972_73807087"})

	candles := e.http.endpoint(t, "public_get_mkt_candles")
	rows := must[[]OHLCV](t)(e.client.FetchOHLCV(ctx, "BTC/IRT", "30m", 1761550200000, 2, nil))
	q := candles.last().Query
	eq(t, []string{q["symbol"], q["res"], q["from"], q["to"]}, []string{"BTC_IRT", "30m", "1761550200", fmt.Sprint(1761550200 + 3600)})
	eq(t, rows[0].Timestamp, 1761550200000)
	must[[]OHLCV](t)(e.client.FetchOHLCV(ctx, "BTC/IRT", "1h", 0, 0, nil))
	eq(t, []string{candles.last().Query["to"], candles.last().Query["from"]}, []string{fmt.Sprint(testNow), fmt.Sprint(testNow - 500*3600)})
	eq(t, len(must[[]OHLCV](t)(e.client.FetchOHLCV(ctx, "BTC/IRT", "", 0, 1, nil))), 1)
	eq(t, len(must[[]OHLCV](t)(e.client.FetchOHLCV(ctx, "BTC/IRT", "30m", 1, 1, nil))), 1)
	for _, bad := range []struct {
		tf    string
		limit int
	}{{"2h", 0}, {"1m", 10001}, {"1m", -1}} {
		if _, err := e.client.FetchOHLCV(ctx, "BTC/IRT", bad.tf, 0, bad.limit, nil); !errors.Is(err, ErrBadRequest) {
			t.Error(bad, err)
		}
	}

	e.http.endpoint(t, "private_get_mkt_commissions")
	eq(t, must[map[string]TradingFee](t)(e.client.FetchTradingFees(ctx))["BTC/IRT"].Maker.String(), "0.003")
	eq(t, must[TradingFee](t)(e.client.FetchTradingFee(ctx, "USDT/IRT")).Taker.String(), "0.0015")
	if _, err := e.client.FetchTradingFee(ctx, "DOGE/IRT"); !errors.Is(err, ErrBadSymbol) {
		t.Error(err)
	}
	eq(t, e.client.RateLimits()["auth"], RateLimit{3, "min"})
	eq(t, e.client.Has()["editOrder"], false)
	eq(t, e.client.Config().Domain, DomainOrg)
}

func TestOrders(t *testing.T) {
	e := newEnv(t)
	orders := e.http.endpoint(t, "private_post_odr_orders")
	o := must[Order](t)(e.client.CreateOrder(ctx, "BTC/IRT", "limit", "buy", decimal.RequireFromString("0.001"), 3100000000, Params{"clientOrderId": "mm-bid-1"}))
	eq(t, orders.last().Body, map[string]any{"symbol": "BTC_IRT", "type": "limit", "side": "buy", "base_amount": "0.001", "price": "3100000000", "identifier": "mm-bid-1"})
	eq(t, []string{o.ID, o.Status}, []string{"535179385", "open"})
	must[Order](t)(e.client.CreateOrder(ctx, "USDT/IRT", "market", "buy", nil, 5, Params{"quoteAmount": "1000000"}))
	eq(t, orders.last().Body, map[string]any{"symbol": "USDT_IRT", "type": "market", "side": "buy", "quote_amount": "1000000"})
	must[Order](t)(e.client.CreateOrder(ctx, "BTC/USDT", "oco", "sell", 1, 57990, Params{"triggerPrice": 58000, "takeProfitPrice": 70000}))
	eq(t, orders.last().Body, map[string]any{"symbol": "BTC_USDT", "type": "oco", "side": "sell", "base_amount": "1", "price": "57990", "stop_price": "58000", "oco_target_price": "70000"})

	before := orders.count()
	for _, bad := range []struct {
		sym, typ, side string
		amount, price  any
		params         Params
		msg            string
	}{
		{"BTC/IRT", "limit", "buy", nil, 1, nil, "amount"},
		{"BTC/IRT", "limit", "buy", 1, nil, nil, "price"},
		{"BTC/IRT", "market", "buy", nil, nil, nil, "amount or params"},
		{"BTC/IRT", "market", "buy", 1, nil, Params{"quoteAmount": 10}, "only one"},
		{"BTC/IRT", "stop_limit", "buy", 1, 1, nil, "stopPrice"},
		{"BTC/IRT", "oco", "buy", 1, 1, Params{"stopPrice": 1}, "takeProfitPrice"},
		{"BTC/IRT", "trailing", "buy", 1, 1, nil, "type"},
		{"BTC/IRT", "limit", "long", 1, 1, nil, "side"},
		{"BTC/IRT", "limit", "buy", 0, 1, nil, "amount"},
		{"BTC/IRT", "limit", "buy", 1, -5, nil, "price"},
		{"BTC/IRT", "stop_limit", "buy", 1, 1, Params{"stopPrice": 1, "triggerPrice": 2}, "both"},
		{"BTC/IRT", "limit", "buy", "abc", 1, nil, "amount"},
		{"BTC-IRT", "limit", "buy", 1, 1, nil, "invalid symbol"},
	} {
		_, err := e.client.CreateOrder(ctx, bad.sym, bad.typ, bad.side, bad.amount, bad.price, bad.params)
		if err == nil || !strings.Contains(err.Error(), bad.msg) {
			t.Errorf("%v: %v", bad, err)
		}
	}
	eq(t, orders.count(), before)
	e.http.endpoint(t, "private_post_odr_orders", reply{status: 406, body: map[string]any{"detail": "insufficent_balance"}})
	if _, err := e.client.CreateOrder(ctx, "BTC/IRT", "limit", "buy", 1, 1, nil); !errors.Is(err, ErrInsufficientFunds) {
		t.Error(err)
	}

	bulk := e.http.endpoint(t, "private_post_odr_orders_bulk")
	created := must[[]Order](t)(e.client.CreateOrders(ctx, []OrderRequest{
		{Symbol: "BTC/IRT", Type: "limit", Side: "buy", Amount: "0.001", Price: "3100000000", Params: Params{"clientOrderId": "a"}},
		{Symbol: "BTC/IRT", Type: "limit", Side: "buy", Amount: "0.001", Price: "3090000000"},
	}))
	eq(t, len(created), 2)
	eq(t, bulk.last().Body, []any{map[string]any{"symbol": "BTC_IRT", "type": "limit", "side": "buy", "base_amount": "0.001", "price": "3100000000", "identifier": "a"}, map[string]any{"symbol": "BTC_IRT", "type": "limit", "side": "buy", "base_amount": "0.001", "price": "3090000000"}})
	one := OrderRequest{Symbol: "BTC/IRT", Type: "limit", Side: "buy", Amount: 1, Price: 1}
	for _, list := range [][]OrderRequest{{}, make([]OrderRequest, 11), {{Symbol: "BTC/IRT", Type: "x"}}} {
		for i := range list {
			if list[i].Symbol == "" {
				list[i] = one
			}
		}
		if _, err := e.client.CreateOrders(ctx, list); err == nil {
			t.Error("bulk validation")
		}
	}

	e.http.endpoint(t, "private_get_odr_orders_id")
	eq(t, must[Order](t)(e.client.FetchOrder(ctx, "535179385")).ClientOrderID, "mm-bid-1")
	e.http.endpoint(t, "private_get_odr_orders_id", reply{status: 404, body: map[string]any{"detail": "Not found."}})
	if _, err := e.client.FetchOrder(ctx, "1"); !errors.Is(err, ErrOrderNotFound) {
		t.Error(err)
	}

	list := e.http.endpoint(t, "private_get_odr_orders")
	got := must[[]Order](t)(e.client.FetchOrders(ctx, FetchOrdersOptions{Symbol: "BTC/IRT", Since: tOrder, Limit: 2, Params: Params{"side": "buy"}}))
	q := list.last().Query
	eq(t, []string{q["symbol"], q["limit"], q["side"], q["start"]}, []string{"BTC_IRT", "2", "buy", "2026-10-27T06:45:30.123+00:00"})
	eq(t, []string{got[0].ID, got[1].ID}, []string{"535179300", "535179385"})
	must[[]Order](t)(e.client.FetchOpenOrders(ctx, FetchOrdersOptions{}))
	eq(t, list.last().Query["state"], "initial,active")
	must[[]Order](t)(e.client.FetchClosedOrders(ctx, FetchOrdersOptions{}))
	eq(t, list.last().Query["state"], "closed")
	if _, err := e.client.FetchOrders(ctx, FetchOrdersOptions{Symbol: "bad"}); err == nil {
		t.Error("bad symbol")
	}
}

func orderPage(t *testing.T, ids ...int) reply {
	base := asMap(fixtureBody(t, "private_post_odr_orders"))
	rows := []any{}
	for _, id := range ids {
		row := Info{}
		for k, v := range base {
			row[k] = v
		}
		row["id"] = fmt.Sprint(id)
		rows = append(rows, row)
	}
	return reply{status: 200, body: rows}
}

func TestPagination(t *testing.T) {
	e := newEnv(t)
	r := e.http.on("GET", "/api/v1/odr/orders/", orderPage(t, 30, 20), orderPage(t, 10))
	got := must[[]Order](t)(e.client.FetchOrders(ctx, FetchOrdersOptions{Limit: 2, Params: Params{"paginate": true}}))
	eq(t, len(got), 3)
	eq(t, r.at(1).Query["offset"], "20")
	full := make([]int, 250)
	for i := range full {
		full[i] = 1000 + i
	}
	open := e.http.on("GET", "/api/v1/odr/orders/", orderPage(t, full...), orderPage(t, 5))
	eq(t, len(must[[]Order](t)(e.client.FetchOpenOrders(ctx, FetchOrdersOptions{Params: Params{"paginate": true}}))), 251)
	eq(t, open.at(0).Query["limit"], "250")
	stuck := e.http.on("GET", "/api/v1/odr/orders/", orderPage(t, 2, 1))
	eq(t, len(must[[]Order](t)(e.client.FetchOrders(ctx, FetchOrdersOptions{Limit: 2, Params: Params{"paginate": true}}))), 2)
	eq(t, stuck.count(), 2)
	pages := e.http.on("GET", "/api/v1/odr/orders/", orderPage(t, 92, 91), orderPage(t, 82, 81), orderPage(t, 72, 71), orderPage(t, 62, 61))
	must[[]Order](t)(e.client.FetchOrders(ctx, FetchOrdersOptions{Limit: 2, Params: Params{"paginate": true, "maxPages": 3}}))
	eq(t, pages.count(), 3)
	empty := e.http.on("GET", "/api/v1/odr/orders/", orderPage(t))
	eq(t, len(must[[]Order](t)(e.client.FetchOrders(ctx, FetchOrdersOptions{Params: Params{"paginate": true}}))), 0)
	eq(t, empty.count(), 1)
	e.http.on("GET", "/api/v1/odr/orders/", reply{status: 503})
	if _, err := e.client.FetchOrders(ctx, FetchOrdersOptions{Params: Params{"paginate": true}}); err == nil {
		t.Error("page error")
	}
}

func TestCancels(t *testing.T) {
	e := newEnv(t)
	c := e.http.endpoint(t, "private_delete_odr_orders_id")
	if err := e.client.CancelOrder(ctx, "7"); err != nil {
		t.Error(err)
	}
	eq(t, c.last().Path, "/api/v1/odr/orders/7/")
	byID := e.http.endpoint(t, "private_delete_odr_orders_identifier_identifier")
	if err := e.client.CancelOrderByIdentifier(ctx, "mm-bid-1"); err != nil {
		t.Error(err)
	}
	eq(t, byID.last().Path, "/api/v1/odr/orders/identifier/mm-bid-1/")
	e.http.endpoint(t, "private_delete_odr_orders_id", reply{status: 406, body: map[string]any{"code": "cancel_order_not_allowed"}})
	if err := e.client.CancelOrder(ctx, "7"); !errors.Is(err, ErrInvalidOrder) {
		t.Error(err)
	}
	bulk := e.http.endpoint(t, "private_delete_odr_orders_bulk")
	res := must[CancelResult](t)(e.client.CancelOrders(ctx, []string{"535179385", "535179386"}, nil))
	eq(t, bulk.last().Body, map[string]any{"ids": []any{"535179385", "535179386"}})
	eq(t, []any{res.Canceled, res.NotCanceled}, []any{[]string{"535179385"}, []string{"535179386"}})
	must[CancelResult](t)(e.client.CancelOrders(ctx, nil, []string{"a"}))
	eq(t, bulk.last().Body, map[string]any{"identifiers": []any{"a"}})
	for _, bad := range [][2][]string{{nil, nil}, {{"1"}, {"a"}}, {make([]string, 11), nil}} {
		if _, err := e.client.CancelOrders(ctx, bad[0], bad[1]); !errors.Is(err, ErrBadRequest) {
			t.Error(err)
		}
	}
	e.http.endpoint(t, "private_delete_odr_orders_bulk", reply{status: 503})
	if _, err := e.client.CancelOrders(ctx, []string{"1"}, nil); err == nil {
		t.Error("error")
	}
	both := newEnv(t, func(c *Config) { c.RateLimits = map[string]string{"order_bulk_cancel": "1/hour"} })
	both.http.endpoint(t, "private_post_odr_orders_bulk")
	both.http.endpoint(t, "private_delete_odr_orders_bulk")
	must[[]Order](t)(both.client.CreateOrders(ctx, []OrderRequest{{Symbol: "BTC/IRT", Type: "limit", Side: "buy", Amount: 1, Price: 1}}))
	must[CancelResult](t)(both.client.CancelOrders(ctx, []string{"1"}, nil))
	eq(t, both.time.slept(), []float64{3600})
}

func TestFillsAndHistory(t *testing.T) {
	e := newEnv(t)
	fills := e.http.endpoint(t, "private_get_odr_fills")
	since := int64(testNow*1000 - 3_600_000)
	trades := must[[]Trade](t)(e.client.FetchMyTrades(ctx, FetchOrdersOptions{Symbol: "BTC/IRT", Since: since, Limit: 100}))
	eq(t, []string{fills.last().Query["start"], fills.last().Query["limit"], trades[0].Fee.Currency}, []string{fmt.Sprint(since / 1000), "100", "IRT"})
	if _, err := e.client.FetchMyTrades(ctx, FetchOrdersOptions{Since: testNow*1000 - 86_401_000}); !errors.Is(err, ErrBadRequest) {
		t.Error(err)
	}
	fill := asMap(asList(fixtureBody(t, "private_get_odr_fills"))[0])
	mk := func(id string) Info {
		row := Info{}
		for k, v := range fill {
			row[k] = v
		}
		row["id"] = id
		return row
	}
	e.http.endpoint(t, "private_get_odr_fills", reply{status: 200, body: []any{mk("3"), mk("1")}})
	got := must[[]Trade](t)(e.client.FetchMyTrades(ctx, FetchOrdersOptions{}))
	eq(t, []string{got[0].ID, got[1].ID}, []string{"1", "3"})
	if _, err := e.client.FetchMyTrades(ctx, FetchOrdersOptions{Symbol: "bad"}); err == nil {
		t.Error("bad symbol")
	}

	row := asMap(asList(asMap(fixtureBody(t, "private_get_odr_order_history"))["results"])[0])
	second := Info{}
	for k, v := range row {
		second[k] = v
	}
	second["id"] = "2"
	h := e.http.on("GET", "/api/v1/odr/order_history/",
		reply{status: 200, body: map[string]any{"results": []any{row}, "next_cursor": "c1", "has_next": true}},
		reply{status: 200, body: map[string]any{"results": []any{second}, "next_cursor": "", "has_next": false}})
	res := must[[]Order](t)(e.client.FetchOrderHistory(ctx, OrderHistoryOptions{Symbol: "BTC/IRT", Since: 1, Until: 2, Limit: 1, Params: Params{"side": "buy", "type": "market", "paginate": true}}))
	eq(t, h.at(0).Query, map[string]string{"symbol": "BTC_IRT", "start": "1", "end": "2", "limit": "1", "side": "buy", "type": "market"})
	eq(t, h.at(1).Query, map[string]string{"symbol": "BTC_IRT", "limit": "1", "side": "buy", "type": "market", "cursor": "c1"})
	eq(t, []string{res[0].ID, res[1].ID}, []string{"535100000", "2"})
	same := e.http.on("GET", "/api/v1/odr/order_history/", reply{status: 200, body: map[string]any{"results": []any{row}, "next_cursor": "same", "has_next": true}})
	eq(t, len(must[[]Order](t)(e.client.FetchOrderHistory(ctx, OrderHistoryOptions{Params: Params{"paginate": true}}))), 1)
	eq(t, same.count(), 2)
	for _, bad := range []OrderHistoryOptions{{Limit: 201}, {Limit: -1}, {Since: 1, Until: 91 * 86_400_000}, {Since: 5, Until: 5}, {Symbol: "bad"}} {
		if _, err := e.client.FetchOrderHistory(ctx, bad); err == nil {
			t.Error(bad)
		}
	}
	e.http.on("GET", "/api/v1/odr/order_history/", reply{status: 503})
	if _, err := e.client.FetchOrderHistory(ctx, OrderHistoryOptions{}); err == nil {
		t.Error("error")
	}
}

func TestWallet(t *testing.T) {
	e := newEnv(t)
	wallets := e.http.endpoint(t, "private_get_wlt_wallets")
	bal := must[Balances](t)(e.client.FetchBalance(ctx, nil))
	eq(t, []string{wallets.last().Query["service"], wallets.last().Query["limit"], bal.Currencies["BTC"].Total.String()}, []string{"main", "1000", "0.0135"})
	rows := asList(fixtureBody(t, "private_get_wlt_wallets"))
	page1 := []any{}
	for i := 0; i < 1000; i++ {
		page1 = append(page1, map[string]any{"id": fmt.Sprint(1000 + i), "asset": fmt.Sprintf("C%d", i), "balance": "1", "frozen": "0"})
	}
	paged := e.http.on("GET", "/api/v1/wlt/wallets/", reply{status: 200, body: page1}, reply{status: 200, body: rows})
	all := must[Balances](t)(e.client.FetchBalance(ctx, Params{"service": "stake"}))
	eq(t, []any{paged.count(), paged.at(0).Query["service"], paged.at(1).Query["offset"]}, []any{2, "stake", "1000"})
	if _, ok := all.Currencies["C999"]; !ok {
		t.Error("missing page")
	}
	e.http.on("GET", "/api/v1/wlt/wallets/", reply{status: 503})
	if _, err := e.client.FetchBalance(ctx, nil); err == nil {
		t.Error("error")
	}

	e.http.endpoint(t, "private_get_wlt_account_numbers")
	eq(t, must[[]BankAccount](t)(e.client.FetchBankAccounts(ctx))[0].ID, "123")
	addr := e.http.endpoint(t, "private_post_wlt_address")
	eq(t, must[DepositAddress](t)(e.client.FetchDepositAddress(ctx, "usdt", "trx")).Network, "TRX")
	eq(t, addr.last().Body, map[string]any{"currency": "USDT", "network": "TRX"})
	if _, err := e.client.FetchDepositAddress(ctx, "USDT", ""); !errors.Is(err, ErrBadRequest) {
		t.Error(err)
	}
	nets := e.http.endpoint(t, "private_get_wlt_networks")
	got := must[[]Network](t)(e.client.FetchCurrencyNetworks(ctx, "usdt"))
	eq(t, []any{nets.last().Query["currency_code"], got[0].Withdraw, got[1].Withdraw}, []any{"USDT", false, true})

	deps := e.http.endpoint(t, "private_get_wlt_deposits")
	d := must[[]Transaction](t)(e.client.FetchDeposits(ctx, TransactionsOptions{Code: "usdt", Since: tOrder, Limit: 10}))
	eq(t, []string{deps.last().Query["currency"], deps.last().Query["start"], d[0].Status}, []string{"USDT", "2026-10-27T06:45:30.123+00:00", "ok"})
	must[[]Transaction](t)(e.client.FetchDeposits(ctx, TransactionsOptions{Params: Params{"paginate": true}}))
	eq(t, deps.last().Query["limit"], "1000")
	wd := e.http.endpoint(t, "private_get_wlt_withdraws")
	eq(t, len(must[[]Transaction](t)(e.client.FetchWithdrawals(ctx, TransactionsOptions{Code: "USDT", Since: tOrder}))), 2)
	eq(t, wd.last().Query["start"], "2026-10-27")
	must[[]Transaction](t)(e.client.FetchWithdrawals(ctx, TransactionsOptions{}))

	create := e.http.endpoint(t, "private_post_wlt_withdraws")
	w := must[Transaction](t)(e.client.Withdraw(ctx, "USDT", decimal.NewFromInt(50), "TAddr", "", Params{"network": "trx"}))
	eq(t, create.last().Body, map[string]any{"currency": "USDT", "amount": "50", "address": "TAddr", "network": "TRX"})
	eq(t, []any{w.ID, w.Status, w.Info["is_single_otp"]}, []any{"7003", "pending", false})
	must[Transaction](t)(e.client.Withdraw(ctx, "XRP", 10, "rTest", "12345", Params{"network": "XRP"}))
	eq(t, create.last().Body.(map[string]any)["memo"], "12345")
	must[Transaction](t)(e.client.Withdraw(ctx, "IRT", 5000000, "", "", Params{"accountNumber": 123}))
	eq(t, create.last().Body, map[string]any{"currency": "IRT", "amount": "5000000", "account_number": "123"})
	must[Transaction](t)(e.client.Withdraw(ctx, "USDT", 1, "", "", Params{"alternativeAddress": "user@example.com", "extra": "x"}))
	eq(t, create.last().Body, map[string]any{"currency": "USDT", "amount": "1", "alternative_address": "user@example.com", "extra": "x"})
	before := create.count()
	for _, bad := range []struct {
		amount  any
		address string
		params  Params
	}{{1, "addr", nil}, {1, "", nil}, {0, "a", Params{"network": "TRX"}}, {nil, "a", Params{"network": "TRX"}}} {
		if _, err := e.client.Withdraw(ctx, "USDT", bad.amount, bad.address, "", bad.params); !errors.Is(err, ErrBadRequest) {
			t.Error(bad, err)
		}
	}
	eq(t, create.count(), before)
	never := newEnv(t)
	down := never.http.on("POST", "/api/v2/wlt/withdraws/", reply{err: errors.New("down")})
	if _, err := never.client.Withdraw(ctx, "USDT", 1, "a", "", Params{"network": "TRX"}); !errors.Is(err, ErrNetwork) {
		t.Error(err)
	}
	eq(t, down.count(), 1)

	verify := e.http.endpoint(t, "private_post_wlt_withdraws_verify_otp_id")
	eq(t, must[Info](t)(e.client.VerifyWithdrawOTP(ctx, "7003", "123456", false)), map[string]any{"detail": "success"})
	eq(t, []any{verify.last().Body, verify.last().Path}, []any{map[string]any{"otp": "123456", "is_second_otp": false}, "/api/v1/wlt/withdraws/verify/otp/7003/"})
	e.http.endpoint(t, "private_post_wlt_withdraws_verify_otp_id", reply{status: 400, body: map[string]any{"code": "extra_try"}})
	_, err := e.client.VerifyWithdrawOTP(ctx, "1", "0", true)
	var be *Error
	if !errors.As(err, &be) || !errors.Is(err, ErrInvalidOTP) || be.Code != "extra_try" {
		t.Error(err)
	}
	retry := e.http.endpoint(t, "private_post_wlt_withdraws_retry_id")
	must[Info](t)(e.client.ResendWithdrawOTP(ctx, "7003", false, true))
	eq(t, retry.last().Body, map[string]any{"first": false, "use_voice_call": true})

	for _, call := range []func() error{
		func() error { _, err := e.client.FetchMarkets(context.Background()); return err },
	} {
		e.http.endpoint(t, "public_get_mkt_markets", reply{status: 503})
		if call() == nil {
			t.Error("error expected")
		}
	}
}

func TestErrorsPropagateFromEveryListCall(t *testing.T) {
	e := newEnv(t, func(c *Config) { c.MaxRetries = Int(0) })
	for _, id := range []string{"public_get_mkt_markets", "public_get_mkt_currencies", "public_get_mkt_networks", "private_get_mkt_markets_suspensions",
		"public_get_mkt_tickers", "public_get_mth_orderbook_symbol", "public_get_mth_matches_symbol", "public_get_mkt_candles", "private_get_mkt_commissions",
		"private_post_odr_orders", "private_post_odr_orders_bulk", "private_get_odr_orders_id", "private_get_odr_orders", "private_get_odr_fills",
		"private_get_wlt_account_numbers", "private_post_wlt_address", "private_get_wlt_networks", "private_get_wlt_deposits", "private_get_wlt_withdraws", "private_post_wlt_withdraws"} {
		e.http.endpoint(t, id, reply{status: 503})
	}
	checks := []func() error{
		func() error { _, err := e.client.LoadMarkets(ctx, true); return err },
		func() error { _, err := e.client.FetchCurrencies(ctx); return err },
		func() error { _, err := e.client.FetchNetworks(ctx, nil); return err },
		func() error { _, err := e.client.FetchMarketSuspensions(ctx); return err },
		func() error { _, err := e.client.FetchTicker(ctx, "BTC/IRT"); return err },
		func() error { _, err := e.client.FetchOrderBook(ctx, "BTC/IRT", 0); return err },
		func() error { _, err := e.client.FetchTrades(ctx, "BTC/IRT", 0, 0); return err },
		func() error { _, err := e.client.FetchOHLCV(ctx, "BTC/IRT", "1m", 0, 0, nil); return err },
		func() error { _, err := e.client.FetchTradingFee(ctx, "BTC/IRT"); return err },
		func() error { _, err := e.client.CreateOrder(ctx, "BTC/IRT", "limit", "buy", 1, 1, nil); return err },
		func() error {
			_, err := e.client.CreateOrders(ctx, []OrderRequest{{Symbol: "BTC/IRT", Type: "limit", Side: "buy", Amount: 1, Price: 1}})
			return err
		},
		func() error { _, err := e.client.FetchOrder(ctx, "1"); return err },
		func() error { _, err := e.client.FetchOrders(ctx, FetchOrdersOptions{}); return err },
		func() error { _, err := e.client.FetchMyTrades(ctx, FetchOrdersOptions{}); return err },
		func() error { _, err := e.client.FetchBankAccounts(ctx); return err },
		func() error { _, err := e.client.FetchDepositAddress(ctx, "USDT", "TRX"); return err },
		func() error { _, err := e.client.FetchCurrencyNetworks(ctx, "USDT"); return err },
		func() error { _, err := e.client.FetchDeposits(ctx, TransactionsOptions{}); return err },
		func() error { _, err := e.client.FetchWithdrawals(ctx, TransactionsOptions{}); return err },
		func() error {
			_, err := e.client.Withdraw(ctx, "USDT", 1, "a", "", Params{"network": "TRX"})
			return err
		},
		func() error { _, err := e.client.FetchTrades(ctx, "bad", 0, 0); return err },
		func() error { _, err := e.client.FetchOHLCV(ctx, "bad", "1m", 0, 0, nil); return err },
		func() error { _, err := e.client.FetchOrderBook(ctx, "bad", 0); return err },
		func() error { _, err := e.client.FetchTicker(ctx, "bad"); return err },
		func() error { _, err := e.client.FetchTradingFee(ctx, "bad"); return err },
	}
	for i, check := range checks {
		if check() == nil {
			t.Errorf("check %d: expected an error", i)
		}
	}
}

func TestNotSupported(t *testing.T) {
	e := newEnv(t)
	calls := map[string]func() error{
		"cancelAllOrders": func() error { return e.client.CancelAllOrders(ctx) }, "editOrder": func() error { return e.client.EditOrder(ctx) },
		"fetchAccounts": func() error { return e.client.FetchAccounts(ctx) }, "fetchLedger": func() error { return e.client.FetchLedger(ctx) },
		"transfer": func() error { return e.client.Transfer(ctx) }, "fetchDepositWithdrawFees": func() error { return e.client.FetchDepositWithdrawFees(ctx) },
		"fetchPositions": func() error { return e.client.FetchPositions(ctx) }, "setLeverage": func() error { return e.client.SetLeverage(ctx) },
		"createDepositAddress": func() error { return e.client.CreateDepositAddress(ctx) }, "watchBalance": func() error { return e.client.WatchBalance(ctx) },
		"watchTickers": func() error { return e.client.WatchTickers(ctx) }, "sandbox": func() error { return e.client.SetSandboxMode(true) },
	}
	for feature, ok := range Has {
		if ok {
			continue
		}
		fn, found := calls[feature]
		if !found {
			t.Errorf("no method for %s", feature)
			continue
		}
		var be *Error
		if err := fn(); !errors.As(err, &be) || !errors.Is(err, ErrNotSupported) || be.Feature != feature {
			t.Errorf("%s: %v", feature, err)
		}
	}
}

func TestDomainReachesTheRequests(t *testing.T) {
	e := newEnv(t, func(c *Config) { c.Domain = DomainMarket })
	e.http.endpoint(t, "public_get_mkt_tickers")
	must[map[string]Ticker](t)(e.client.FetchTickers(ctx))
	eq(t, e.client.Config().RestURL, "https://api.bitpin.market")
}
