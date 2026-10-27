package bitpin

import (
	"context"
	"encoding/json"
	"errors"
	"sync"
	"testing"
	"time"
)

type fakeTransport struct {
	mu       sync.Mutex
	url      string
	getToken func(context.Context) (string, error)
	token    string
	connects int
	closed   bool
	handlers map[string]func([]byte)
	failNext error
}

func (f *fakeTransport) Connect(ctx context.Context) error {
	f.mu.Lock()
	f.connects++
	f.mu.Unlock()
	if f.getToken != nil {
		tok, err := f.getToken(ctx)
		if err != nil {
			return err
		}
		f.mu.Lock()
		f.token = tok
		f.mu.Unlock()
	}
	return nil
}

func (f *fakeTransport) Subscribe(_ context.Context, channel string, onData func([]byte)) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.failNext != nil {
		err := f.failNext
		f.failNext = nil
		return err
	}
	f.handlers[channel] = onData
	return nil
}

func (f *fakeTransport) Close() error { f.mu.Lock(); f.closed = true; f.mu.Unlock(); return nil }

func (f *fakeTransport) push(t *testing.T, channel string, data any) {
	t.Helper()
	var handler func([]byte)
	for i := 0; i < 200 && handler == nil; i++ {
		f.mu.Lock()
		handler = f.handlers[channel]
		f.mu.Unlock()
		if handler == nil {
			time.Sleep(time.Millisecond)
		}
	}
	if handler == nil {
		t.Fatalf("no subscription for %s", channel)
	}
	raw, _ := json.Marshal(data)
	handler(raw)
}

type wsEnv struct {
	env
	ws         *WS
	transports func() []*fakeTransport
	info       *route
}

func newWSEnv(t *testing.T, mutate ...func(*Config)) wsEnv {
	var mu sync.Mutex
	transports := []*fakeTransport{}
	factory := func(url string, getToken func(context.Context) (string, error)) Transport {
		mu.Lock()
		defer mu.Unlock()
		tr := &fakeTransport{url: url, getToken: getToken, handlers: map[string]func([]byte){}}
		transports = append(transports, tr)
		return tr
	}
	e := newEnv(t, append([]func(*Config){func(c *Config) { c.WSTransport = factory }}, mutate...)...)
	info := e.http.endpoint(t, "credentials_post_usr_ws_info")
	list := func() []*fakeTransport {
		mu.Lock()
		defer mu.Unlock()
		return append([]*fakeTransport(nil), transports...)
	}
	return wsEnv{env: e, ws: NewWS(e.client, factory, 0), transports: list, info: info}
}

func (w wsEnv) transport(t *testing.T) *fakeTransport {
	for i := 0; i < 200; i++ {
		if list := w.transports(); len(list) > 0 {
			return list[0]
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatal("no transport")
	return nil
}

func async[T any](fn func() (T, error)) <-chan T {
	ch := make(chan T, 1)
	go func() {
		v, err := fn()
		if err != nil {
			panic(err)
		}
		ch <- v
	}()
	return ch
}

func await[T any](t *testing.T, ch <-chan T) T {
	t.Helper()
	select {
	case v := <-ch:
		return v
	case <-time.After(2 * time.Second):
		t.Fatal("timed out")
		var zero T
		return zero
	}
}

var wsTicker = map[string]any{"price": "3145737420", "change": "0.0258", "min": "3000000000", "max": "3200000000", "mean": "3100000000",
	"value": "1500000000000", "amount": "480.5", "time": "1760873857000", "symbol": "BTC_IRT", "event": "currency_price_update"}

func TestWatchTicker(t *testing.T) {
	w := newWSEnv(t)
	next := async(func() (Ticker, error) { return w.ws.WatchTicker(ctx, "BTC/IRT") })
	tr := w.transport(t)
	tr.push(t, "market:BTC_IRT", map[string]any{"event": "candle_update", "symbol": "BTC_IRT", "candles": []any{}})
	tr.push(t, "market:BTC_IRT", wsTicker)
	tk := await(t, next)
	eq(t, []any{tk.Symbol, tk.Last.String(), tk.Percentage.String(), tk.BaseVolume.String(), *tk.Timestamp}, []any{"BTC/IRT", "3145737420", "2.58", "480.5", 1760873857000})
	eq(t, tr.url, "wss://centrifugo.bitpin.org/connection/websocket")
	eq(t, tr.token, str(asMap(fixtureBody(t, "credentials_post_usr_ws_info"))["ws_token"]))
	_ = w.ws.Close()
	eq(t, tr.closed, true)
	_ = w.ws.Close()
}

func TestWatchFanOutAndFilters(t *testing.T) {
	w := newWSEnv(t)
	candle := map[string]any{"open": "1", "close": "2", "low": "0.5", "high": "3", "volume": "10", "ts": "1760873760.0"}
	one := async(func() ([]OHLCV, error) { return w.ws.WatchOHLCV(ctx, "BTC/IRT", "1m") })
	five := async(func() ([]OHLCV, error) { return w.ws.WatchOHLCV(ctx, "BTC/IRT", "5m") })
	tr := w.transport(t)
	time.Sleep(20 * time.Millisecond)
	c1, c5 := map[string]any{}, map[string]any{}
	for k, v := range candle {
		c1[k], c5[k] = v, v
	}
	c1["resolution"], c5["resolution"] = "1m", "5m"
	tr.push(t, "market:BTC_IRT", []byte("not json"))
	tr.push(t, "market:BTC_IRT", map[string]any{"no": "event"})
	tr.push(t, "market:BTC_IRT", map[string]any{"event": "candle_update", "symbol": "BTC_IRT", "candles": []any{c1, c5}})
	eq(t, await(t, one)[0].Timestamp, 1760873760000)
	eq(t, len(await(t, five)), 1)
	eq(t, tr.connects, 1)
	if _, err := w.ws.WatchOHLCV(ctx, "BTC/IRT", "2h"); !errors.Is(err, ErrBadRequest) {
		t.Error(err)
	}

	book := async(func() (OrderBook, error) { return w.ws.WatchOrderBook(ctx, "BTC_IRT") })
	tr.push(t, "orderbook:BTC_IRT", map[string]any{"asks": []any{[]any{"3160000000", "0.2"}, []any{"3150000000", "0.01"}}, "bids": []any{[]any{"3130000000", "1"}, []any{"3140000000", "0.05"}},
		"symbol": "BTC_IRT", "event_time": "2025-10-19T11:38:27.929164Z", "event": "market_data"})
	ob := await(t, book)
	eq(t, []any{ob.Bids[0].Price.String(), ob.Asks[0].Price.String(), *ob.Timestamp}, []any{"3140000000", "3150000000", 1760873907929})

	trades := async(func() ([]Trade, error) { return w.ws.WatchTrades(ctx, "BTC/IRT") })
	tr.push(t, "matches:BTC_IRT", map[string]any{"event": "matches_update", "symbol": "BTC_IRT", "matches": []any{map[string]any{"id": "1_2", "price": "1", "base_amount": "2", "quote_amount": "2", "side": "buy", "time": 1760873797.149016}}})
	got := await(t, trades)
	eq(t, []any{got[0].ID, *got[0].Timestamp}, []any{"1_2", 1760873797149})

	for _, bad := range []func() error{
		func() error { _, err := w.ws.WatchTicker(ctx, "bad"); return err },
		func() error { _, err := w.ws.WatchOHLCV(ctx, "bad", "1m"); return err },
		func() error { _, err := w.ws.WatchOrderBook(ctx, "bad"); return err },
		func() error { _, err := w.ws.WatchTrades(ctx, "bad"); return err },
		func() error { _, err := w.ws.WatchOrders(ctx, "bad"); return err },
	} {
		if bad() == nil {
			t.Error("bad symbol must fail")
		}
	}
}

func TestWatchPrivate(t *testing.T) {
	w := newWSEnv(t)
	order := asMap(fixtureBody(t, "private_post_odr_orders"))
	with := func(extra map[string]any) map[string]any {
		out := map[string]any{"event": "user_order_update"}
		for k, v := range order {
			out[k] = v
		}
		for k, v := range extra {
			out[k] = v
		}
		return out
	}
	btc := async(func() (Order, error) { return w.ws.WatchOrders(ctx, "BTC/IRT") })
	usdt := async(func() (Order, error) { return w.ws.WatchOrders(ctx, "USDT/IRT") })
	anyMarket := async(func() (Order, error) { return w.ws.WatchOrders(ctx, "") })
	tr := w.transport(t)
	time.Sleep(30 * time.Millisecond)
	ch := "user:order_info#TESTUSR1"
	tr.push(t, ch, with(map[string]any{"symbol": "USDT_IRT", "id": "2"}))
	tr.push(t, ch, with(map[string]any{"symbol": "BTC_IRT", "id": "1"}))
	eq(t, []string{await(t, btc).ID, await(t, usdt).ID, await(t, anyMarket).ID}, []string{"1", "2", "2"})
	eq(t, w.info.count(), 2) // one shared identifier lookup + one connection token

	fill := asMap(asList(fixtureBody(t, "private_get_odr_fills"))[0])
	mine := async(func() (Trade, error) { return w.ws.WatchMyTrades(ctx, "") })
	time.Sleep(20 * time.Millisecond)
	f := map[string]any{"event": "user_match_update"}
	for k, v := range fill {
		f[k] = v
	}
	tr.push(t, ch, f)
	eq(t, await(t, mine).ID, "65375307")
	if _, err := w.ws.WatchMyTrades(ctx, "bad"); err == nil {
		t.Error("bad symbol")
	}
}

func TestWatchErrors(t *testing.T) {
	anon := newWSEnv(t, func(c *Config) { c.APIKey, c.SecretKey = "", "" })
	if _, err := anon.ws.WatchOrders(ctx, ""); !errors.Is(err, ErrAuthentication) {
		t.Error(err)
	}
	pub := async(func() ([]Trade, error) { return anon.ws.WatchTrades(ctx, "BTC/IRT") })
	tr := anon.transport(t)
	if tr.getToken != nil {
		t.Error("public-only clients connect without a token")
	}
	tr.push(t, "matches:BTC_IRT", map[string]any{"event": "matches_update", "symbol": "BTC_IRT", "matches": []any{}})
	await(t, pub)
	if _, err := anon.ws.wsInfo(ctx); !errors.Is(err, ErrAuthentication) {
		t.Error(err)
	}

	failing := newWSEnv(t)
	failing.http.endpoint(t, "credentials_post_usr_ws_info", reply{status: 503})
	if _, err := failing.ws.WatchOrders(ctx, ""); !errors.Is(err, ErrExchangeNotAvailable) {
		t.Error(err)
	}
	if _, err := failing.ws.WatchTicker(ctx, "BTC/IRT"); !errors.Is(err, ErrExchangeNotAvailable) {
		t.Errorf("connect error: %v", err)
	}
	failing.http.endpoint(t, "credentials_post_usr_ws_info")
	sub := newWSEnv(t)
	go func() { _, _ = sub.ws.WatchTicker(ctx, "USDT/IRT") }()
	str := sub.transport(t)
	time.Sleep(20 * time.Millisecond)
	str.mu.Lock()
	str.failNext = errors.New("subscribe failed")
	str.mu.Unlock()
	if _, err := sub.ws.WatchTrades(ctx, "USDT/IRT"); err == nil {
		t.Error("subscribe error expected")
	}

	cancelled, cancel := context.WithCancel(ctx)
	go func() { time.Sleep(20 * time.Millisecond); cancel() }()
	if _, err := sub.ws.WatchOrderBook(cancelled, "USDT/IRT"); !errors.Is(err, context.Canceled) {
		t.Error(err)
	}
}

func TestQueueDropsOldest(t *testing.T) {
	q := &queue{size: 2, notify: make(chan struct{}, 1), accept: all}
	for _, p := range []string{"0", "1", "2", "3"} {
		q.push(Info{"price": p})
	}
	eq(t, must[Info](t)(q.next(ctx))["price"], "2")
	eq(t, must[Info](t)(q.next(ctx))["price"], "3")
}

func TestClientWatchDelegates(t *testing.T) {
	w := newWSEnv(t)
	c := w.client
	type result struct{ err error }
	done := make(chan result, 6)
	run := func(fn func() error) { go func() { done <- result{fn()} }() }
	run(func() error { _, err := c.WatchTicker(ctx, "BTC/IRT"); return err })
	run(func() error { _, err := c.WatchOHLCV(ctx, "BTC/IRT", "1m"); return err })
	run(func() error { _, err := c.WatchOrderBook(ctx, "BTC/IRT"); return err })
	run(func() error { _, err := c.WatchTrades(ctx, "BTC/IRT"); return err })
	run(func() error { _, err := c.WatchOrders(ctx, ""); return err })
	run(func() error { _, err := c.WatchMyTrades(ctx, ""); return err })
	tr := w.transport(t)
	time.Sleep(50 * time.Millisecond)
	tr.push(t, "market:BTC_IRT", wsTicker)
	tr.push(t, "market:BTC_IRT", map[string]any{"event": "candle_update", "symbol": "BTC_IRT", "candles": []any{map[string]any{"resolution": "1m", "ts": "1"}}})
	tr.push(t, "orderbook:BTC_IRT", map[string]any{"event": "market_data", "symbol": "BTC_IRT"})
	tr.push(t, "matches:BTC_IRT", map[string]any{"event": "matches_update", "symbol": "BTC_IRT"})
	tr.push(t, "user:order_info#TESTUSR1", map[string]any{"event": "user_order_update", "id": "1", "symbol": "BTC_IRT"})
	tr.push(t, "user:order_info#TESTUSR1", map[string]any{"event": "user_match_update", "id": "1", "symbol": "BTC_IRT"})
	for i := 0; i < 6; i++ {
		if r := await(t, done); r.err != nil {
			t.Error(r.err)
		}
	}
	if err := c.Close(); err != nil {
		t.Error(err)
	}
	eq(t, tr.closed, true)
	_ = c.Close()
	if NewWS(c, nil, 0).factory == nil {
		t.Error("default transport")
	}
	if _, ok := newCentrifugeTransport("wss://example.invalid", func(context.Context) (string, error) { return "t", nil }).(*centrifugeTransport); !ok {
		t.Error("centrifuge transport")
	}
}
