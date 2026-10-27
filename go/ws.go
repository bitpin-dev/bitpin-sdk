package bitpin

import (
	"context"
	"encoding/json"
	"strings"
	"sync"

	"github.com/centrifugal/centrifuge-go"
)

// Transport is the Centrifugo connection. Tests replace it with a fake.
type Transport interface {
	Connect(ctx context.Context) error
	Subscribe(ctx context.Context, channel string, onData func(data []byte)) error
	Close() error
}

// TransportFactory builds a Transport; getToken is nil for public-only clients.
type TransportFactory func(url string, getToken func(ctx context.Context) (string, error)) Transport

type centrifugeTransport struct {
	client *centrifuge.Client
}

func newCentrifugeTransport(url string, getToken func(ctx context.Context) (string, error)) Transport {
	cfg := centrifuge.Config{Name: "bitpin-sdk-go", Version: Version}
	if getToken != nil {
		cfg.GetToken = func(centrifuge.ConnectionTokenEvent) (string, error) { return getToken(context.Background()) }
	}
	return &centrifugeTransport{client: centrifuge.NewJsonClient(url, cfg)}
}

func (t *centrifugeTransport) Connect(context.Context) error { return t.client.Connect() }

func (t *centrifugeTransport) Subscribe(_ context.Context, channel string, onData func([]byte)) error {
	sub, err := t.client.NewSubscription(channel)
	if err != nil {
		return err
	}
	sub.OnPublication(func(e centrifuge.PublicationEvent) { onData(e.Data) })
	return sub.Subscribe()
}

func (t *centrifugeTransport) Close() error {
	t.client.Close()
	return nil
}

// queue buffers the updates of one watch; the oldest is dropped when full.
type queue struct {
	mu     sync.Mutex
	items  []Info
	size   int
	notify chan struct{}
	accept func(Info) bool
}

func (q *queue) push(item Info) {
	q.mu.Lock()
	if len(q.items) >= q.size {
		q.items = q.items[1:]
	}
	q.items = append(q.items, item)
	q.mu.Unlock()
	select {
	case q.notify <- struct{}{}:
	default:
	}
}

func (q *queue) next(ctx context.Context) (Info, error) {
	for {
		q.mu.Lock()
		if len(q.items) > 0 {
			item := q.items[0]
			q.items = q.items[1:]
			q.mu.Unlock()
			return item, nil
		}
		q.mu.Unlock()
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-q.notify:
		}
	}
}

// WS gives ccxt.pro-style Watch* methods over Bitpin's Centrifugo server. Each distinct
// watch (method, symbol, timeframe) has its own queue, so every watcher sees its updates.
// Two goroutines calling the same watch split its updates.
type WS struct {
	client    *Client
	factory   TransportFactory
	queueSize int

	mu        sync.Mutex
	transport Transport
	channels  map[string]bool
	queues    map[[3]string]*queue
	userID    string
}

// NewWS builds a WebSocket client for c; usually you call the Watch* methods on Client instead.
func NewWS(c *Client, factory TransportFactory, queueSize int) *WS {
	if factory == nil {
		factory = newCentrifugeTransport
	}
	if queueSize <= 0 {
		queueSize = 1000
	}
	return &WS{client: c, factory: factory, queueSize: queueSize, channels: map[string]bool{}, queues: map[[3]string]*queue{}}
}

// Close disconnects.
func (w *WS) Close() error {
	w.mu.Lock()
	t := w.transport
	w.transport, w.channels = nil, map[string]bool{}
	w.mu.Unlock()
	if t != nil {
		return t.Close()
	}
	return nil
}

func (w *WS) wsInfo(ctx context.Context) (Info, error) {
	creds, err := w.client.credentials()
	if err != nil {
		return nil, err
	}
	data, err := w.client.Request(ctx, "credentials_post_usr_ws_info", nil, nil, creds)
	return asMap(data), err
}

func (w *WS) onData(channel string) func([]byte) {
	return func(raw []byte) {
		var data Info
		if json.Unmarshal(raw, &data) != nil {
			return
		}
		event, ok := data["event"].(string)
		if !ok {
			return
		}
		data = normalizeNumbers(data).(Info)
		w.mu.Lock()
		var targets []*queue
		for key, q := range w.queues {
			if key[0] == channel && key[1] == event && q.accept(data) {
				targets = append(targets, q)
			}
		}
		w.mu.Unlock()
		for _, q := range targets {
			q.push(data)
		}
	}
}

func (w *WS) next(ctx context.Context, channel, event, key string, accept func(Info) bool) (Info, error) {
	w.mu.Lock()
	name := [3]string{channel, event, key}
	q, ok := w.queues[name]
	if !ok {
		q = &queue{size: w.queueSize, notify: make(chan struct{}, 1), accept: accept}
		w.queues[name] = q
	}
	if w.transport == nil {
		var getToken func(context.Context) (string, error)
		if w.client.cfg.hasCredentials() {
			getToken = func(ctx context.Context) (string, error) {
				info, err := w.wsInfo(ctx)
				return str(info["ws_token"]), err
			}
		}
		t := w.factory(w.client.cfg.WSURL, getToken)
		if err := t.Connect(ctx); err != nil {
			w.mu.Unlock()
			return nil, err
		}
		w.transport = t
	}
	if !w.channels[channel] {
		if err := w.transport.Subscribe(ctx, channel, w.onData(channel)); err != nil {
			w.mu.Unlock()
			return nil, err
		}
		w.channels[channel] = true
	}
	w.mu.Unlock()
	return q.next(ctx)
}

func (w *WS) userChannel(ctx context.Context) (string, error) {
	if !w.client.cfg.hasCredentials() {
		return "", newError(ErrAuthentication, "APIKey and SecretKey are required for private channels")
	}
	w.mu.Lock()
	defer w.mu.Unlock() // one lookup shared by every concurrent watcher (ws-info: 10 per minute)
	if w.userID == "" {
		info, err := w.wsInfo(ctx)
		if err != nil {
			return "", err
		}
		w.userID = str(info["user_identifier"])
	}
	return strings.ReplaceAll(specWSChannels["user_orders"], "{user_identifier}", w.userID), nil
}

func channelFor(kind, symbol string) (string, error) {
	id, err := MarketID(symbol)
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(specWSChannels[kind], "{symbol}", id), nil
}

func all(Info) bool { return true }

// WatchTicker waits for the next 24h ticker update of symbol.
func (w *WS) WatchTicker(ctx context.Context, symbol string) (Ticker, error) {
	ch, err := channelFor("market", symbol)
	if err != nil {
		return Ticker{}, err
	}
	data, err := w.next(ctx, ch, "currency_price_update", "", all)
	if err != nil {
		return Ticker{}, err
	}
	var ts *int64
	if d := dec(data["time"]); d != nil {
		n := d.IntPart()
		ts = &n
	}
	last := dec(data["price"])
	return Ticker{Symbol: symbolOrRaw(data["symbol"]), Timestamp: ts, Datetime: msToISO(ts), High: dec(data["max"]), Low: dec(data["min"]),
		Last: last, Close: last, Percentage: ratioToPercent(data["change"]), Average: dec(data["mean"]),
		BaseVolume: dec(data["amount"]), QuoteVolume: dec(data["value"]), Info: data}, nil
}

// WatchOHLCV waits for the next candles of timeframe (Bitpin pushes every 10 s and on trades).
func (w *WS) WatchOHLCV(ctx context.Context, symbol, timeframe string) ([]OHLCV, error) {
	if _, ok := Timeframes[timeframe]; !ok {
		return nil, newError(ErrBadRequest, "timeframe %q is not supported", timeframe)
	}
	ch, err := channelFor("market", symbol)
	if err != nil {
		return nil, err
	}
	match := func(c any) bool { return str(asMap(c)["resolution"]) == timeframe }
	accept := func(d Info) bool {
		for _, c := range asList(d["candles"]) {
			if match(c) {
				return true
			}
		}
		return false
	}
	data, err := w.next(ctx, ch, "candle_update", timeframe, accept)
	if err != nil {
		return nil, err
	}
	out := []OHLCV{}
	for _, c := range asList(data["candles"]) {
		if match(c) {
			out = append(out, parseOHLCV(asMap(c)))
		}
	}
	return out, nil
}

// WatchOrderBook waits for the next order-book update of symbol.
func (w *WS) WatchOrderBook(ctx context.Context, symbol string) (OrderBook, error) {
	ch, err := channelFor("orderbook", symbol)
	if err != nil {
		return OrderBook{}, err
	}
	data, err := w.next(ctx, ch, "market_data", "", all)
	if err != nil {
		return OrderBook{}, err
	}
	return parseOrderBook(data, symbolOrRaw(data["symbol"]), isoToMs(data["event_time"])), nil
}

// WatchTrades waits for the next public trades of symbol.
func (w *WS) WatchTrades(ctx context.Context, symbol string) ([]Trade, error) {
	ch, err := channelFor("matches", symbol)
	if err != nil {
		return nil, err
	}
	data, err := w.next(ctx, ch, "matches_update", "", all)
	if err != nil {
		return nil, err
	}
	out := []Trade{}
	for _, row := range asList(data["matches"]) {
		out = append(out, parseTrade(asMap(row), symbolOrRaw(data["symbol"])))
	}
	return out, nil
}

func (w *WS) private(ctx context.Context, event, symbol string) (Info, error) {
	ch, err := w.userChannel(ctx)
	if err != nil {
		return nil, err
	}
	wanted := ""
	if symbol != "" {
		if wanted, err = MarketID(symbol); err != nil {
			return nil, err
		}
	}
	key := wanted
	if key == "" {
		key = "*"
	}
	return w.next(ctx, ch, event, key, func(d Info) bool { return wanted == "" || str(d["symbol"]) == wanted })
}

// WatchOrders waits for the next update of one of your orders ("" for every market).
func (w *WS) WatchOrders(ctx context.Context, symbol string) (Order, error) {
	data, err := w.private(ctx, "user_order_update", symbol)
	if err != nil {
		return Order{}, err
	}
	return parseOrder(data), nil
}

// WatchMyTrades waits for your next fill ("" for every market).
func (w *WS) WatchMyTrades(ctx context.Context, symbol string) (Trade, error) {
	data, err := w.private(ctx, "user_match_update", symbol)
	if err != nil {
		return Trade{}, err
	}
	return parseMyTrade(data), nil
}

func (c *Client) websocket() *WS {
	c.wsMu.Lock()
	defer c.wsMu.Unlock()
	if c.ws == nil {
		c.ws = NewWS(c, c.cfg.WSTransport, 0)
	}
	return c.ws
}

// WatchTicker waits for the next 24h ticker update of symbol.
func (c *Client) WatchTicker(ctx context.Context, symbol string) (Ticker, error) {
	return c.websocket().WatchTicker(ctx, symbol)
}

// WatchOHLCV waits for the next candles of timeframe.
func (c *Client) WatchOHLCV(ctx context.Context, symbol, timeframe string) ([]OHLCV, error) {
	return c.websocket().WatchOHLCV(ctx, symbol, timeframe)
}

// WatchOrderBook waits for the next order-book update of symbol.
func (c *Client) WatchOrderBook(ctx context.Context, symbol string) (OrderBook, error) {
	return c.websocket().WatchOrderBook(ctx, symbol)
}

// WatchTrades waits for the next public trades of symbol.
func (c *Client) WatchTrades(ctx context.Context, symbol string) ([]Trade, error) {
	return c.websocket().WatchTrades(ctx, symbol)
}

// WatchOrders waits for the next update of one of your orders.
func (c *Client) WatchOrders(ctx context.Context, symbol string) (Order, error) {
	return c.websocket().WatchOrders(ctx, symbol)
}

// WatchMyTrades waits for your next fill.
func (c *Client) WatchMyTrades(ctx context.Context, symbol string) (Trade, error) {
	return c.websocket().WatchMyTrades(ctx, symbol)
}
