package bitpin

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Timeframes are the candle resolutions in seconds (ccxt names; 1m is a minute, 1M a month).
var Timeframes = map[string]int64{
	"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "3h": 10800, "4h": 14400,
	"6h": 21600, "1d": 86400, "1w": 604800, "1M": 2592000,
}

const (
	maxRateLimitWait  = 5.0
	defaultOHLCVLimit = 500
)

var orderTypes = []string{"limit", "market", "stop_limit", "oco"}

var paramAliases = map[string]string{
	"clientOrderId": "identifier", "stopPrice": "stop_price", "triggerPrice": "stop_price",
	"takeProfitPrice": "oco_target_price", "ocoTargetPrice": "oco_target_price",
	"quoteAmount": "quote_amount", "cost": "quote_amount",
}

var maxPageSize = map[string]string{
	"private_get_odr_orders": "orders_max_page_size", "private_get_odr_fills": "fills_max_page_size",
	"private_get_wlt_wallets": "wallets_max_page_size", "private_get_wlt_deposits": "wallet_lists_max_page_size",
	"private_get_wlt_withdraws": "wallet_lists_max_page_size",
}

// Client is the Bitpin exchange client. It is safe for concurrent use.
type Client struct {
	ID   string
	Name string
	cfg  resolvedConfig
	http *http.Client

	limiter *limiter
	authMu  sync.Mutex
	tokens  tokenState
	store   TokenStore
	loaded  bool
	keyID   string

	marketsMu   sync.RWMutex
	markets     map[string]Market
	marketsByID map[string]Market

	wsMu sync.Mutex
	ws   *WS
}

// New builds a client. It returns an error for an invalid Config.
func New(cfg Config) (*Client, error) {
	resolved, err := cfg.resolve()
	if err != nil {
		return nil, err
	}
	c := &Client{ID: "bitpin", Name: "Bitpin", cfg: resolved, http: cfg.HTTPClient, store: cfg.TokenStore}
	if c.http == nil {
		c.http = &http.Client{Timeout: resolved.Timeout}
	}
	if c.store == nil {
		c.store = &MemoryTokenStore{}
	}
	clock := func() float64 { return float64(resolved.Clock().UnixNano()) / 1e9 }
	c.limiter = newLimiter(resolved.rateLimits, clock)
	c.tokens = tokenState{clock: clock}
	return c, nil
}

// String hides the credentials.
func (c *Client) String() string { return "bitpin.Client{" + c.cfg.Config.String() + "}" }

// Config returns the effective settings (domain, URLs, …).
func (c *Client) Config() Config { return c.cfg.Config }

// Has is the ccxt capability map.
func (c *Client) Has() map[string]bool { return Has }

// RateLimits returns the effective per-bucket limits.
func (c *Client) RateLimits() map[string]RateLimit {
	out := make(map[string]RateLimit, len(c.cfg.rateLimits))
	for k, v := range c.cfg.rateLimits {
		out[k] = v
	}
	return out
}

// Close disconnects the WebSocket, if one was opened.
func (c *Client) Close() error {
	c.wsMu.Lock()
	ws := c.ws
	c.ws = nil
	c.wsMu.Unlock()
	if ws != nil {
		return ws.Close()
	}
	return nil
}

// --- transport ------------------------------------------------------------------------------

func (c *Client) sleep(ctx context.Context, seconds float64) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-c.cfg.Sleep(time.Duration(seconds * float64(time.Second))):
		return nil
	}
}

// Request calls one endpoint by its spec id (e.g. "public_get_mkt_tickers") and returns the
// decoded JSON. It rate-limits, authenticates, maps errors, and retries only when safe.
func (c *Client) Request(ctx context.Context, endpointID string, pathParams, params Params, body any) (any, error) {
	req, err := buildRequest(c.cfg, endpointID, pathParams, params, body)
	if err != nil {
		return nil, err
	}
	reauthenticated := false
	attempt := 0
	for {
		token := ""
		if req.auth == "private" {
			if token, err = c.accessToken(ctx); err != nil {
				return nil, err
			}
		}
		result, err := c.send(ctx, req, token)
		if err == nil {
			return result, nil
		}
		var e *Error
		if !errors.As(err, &e) {
			return nil, err
		}
		if errors.Is(e, ErrAuthentication) && req.auth == "private" && !reauthenticated {
			reauthenticated = true
			c.authMu.Lock()
			c.tokens.expireAccess(token)
			c.authMu.Unlock()
			continue
		}
		if errors.Is(e, ErrNetwork) {
			if wait, ok := c.retryDelay(req, e, attempt); ok {
				attempt++
				if err := c.sleep(ctx, wait); err != nil {
					return nil, err
				}
				continue
			}
		}
		return nil, e
	}
}

func (c *Client) retryDelay(req builtRequest, e *Error, attempt int) (float64, bool) {
	if !req.idempotent || attempt >= c.cfg.maxRetries {
		return 0, false
	}
	if errors.Is(e, ErrRateLimitExceeded) {
		if e.RetryAfter < 0 || e.RetryAfter > maxRateLimitWait {
			return 0, false
		}
		return e.RetryAfter, true
	}
	return 0.5 * float64(int(1)<<attempt), true
}

func (c *Client) send(ctx context.Context, req builtRequest, token string) (any, error) {
	if !c.cfg.DisableRateLimit {
		if wait := c.limiter.reserve(req.buckets); wait > 0 {
			if err := c.sleep(ctx, wait); err != nil {
				return nil, err
			}
		}
	}
	target := req.url
	if len(req.query) > 0 {
		target += "?" + req.query.Encode()
	}
	var payload io.Reader
	if req.hasBody {
		data, err := json.Marshal(req.body)
		if err != nil {
			return nil, err
		}
		payload = bytes.NewReader(data)
	}
	httpReq, err := http.NewRequestWithContext(ctx, req.method, target, payload)
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Accept", "application/json")
	agent := c.cfg.UserAgent
	if agent == "" {
		agent = "bitpin-sdk-go/" + Version
	}
	httpReq.Header.Set("User-Agent", agent)
	if req.hasBody {
		httpReq.Header.Set("Content-Type", "application/json")
	}
	if token != "" {
		httpReq.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := c.http.Do(httpReq)
	if err != nil {
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		k, reason := ErrNetwork, "network error"
		var timeout interface{ Timeout() bool }
		if errors.As(err, &timeout) && timeout.Timeout() {
			k, reason = ErrRequestTimeout, "request timed out"
		}
		e := newError(k, "%s: %s", req.id, reason)
		e.EndpointID = req.id
		if req.auth != "credentials" { // the request of a credentials call holds the secret key
			e.cause = err
		}
		return nil, e
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		e := newError(ErrNetwork, "%s: reading the response failed", req.id)
		e.EndpointID, e.cause = req.id, err
		return nil, e
	}
	var data any
	valid := true
	if len(raw) > 0 {
		decoder := json.NewDecoder(bytes.NewReader(raw))
		decoder.UseNumber()
		if decoder.Decode(&data) != nil {
			valid, data = false, string(raw)
		}
	}
	if resp.StatusCode >= 400 {
		return nil, mapError(req.id, resp.StatusCode, data, resp.Header.Get("Retry-After"))
	}
	if !valid {
		e := newError(ErrExchange, "%s: invalid JSON in response", req.id)
		e.Status, e.Body, e.EndpointID = resp.StatusCode, string(raw), req.id
		return nil, e
	}
	return normalizeNumbers(data), nil
}

// normalizeNumbers turns json.Number into strings so prices keep every digit.
func normalizeNumbers(v any) any {
	switch t := v.(type) {
	case json.Number:
		return string(t)
	case map[string]any:
		for k, item := range t {
			t[k] = normalizeNumbers(item)
		}
		return t
	case []any:
		for i, item := range t {
			t[i] = normalizeNumbers(item)
		}
		return t
	default:
		return v
	}
}

// --- authentication -------------------------------------------------------------------------

func (c *Client) credentials() (map[string]any, error) {
	if !c.cfg.hasCredentials() {
		return nil, newError(ErrAuthentication, "APIKey and SecretKey are required for private endpoints")
	}
	return map[string]any{"api_key": c.cfg.APIKey, "secret_key": c.cfg.SecretKey}, nil
}

func (c *Client) accessToken(ctx context.Context) (string, error) {
	c.authMu.Lock()
	defer c.authMu.Unlock()
	creds, err := c.credentials()
	if err != nil {
		return "", err
	}
	if c.keyID == "" {
		c.keyID = KeyID(c.cfg.APIKey) // PBKDF2 is slow on purpose; derive it once
	}
	if !c.loaded {
		c.loaded = true
		if stored, err := c.store.Load(ctx, c.keyID); err == nil && stored != nil {
			c.tokens.tokens = stored
		}
	}
	action := c.tokens.action()
	if action == actionRefresh {
		req, _ := buildRequest(c.cfg, "credentials_post_usr_refresh_token", nil, nil, map[string]any{"refresh": c.tokens.tokens.Refresh})
		data, err := c.send(ctx, req, "")
		switch {
		case err == nil:
			if err := c.store.Save(ctx, c.keyID, c.tokens.setAccess(str(asMap(data)["access"]))); err != nil {
				return "", err
			}
			action = actionOK
		case errors.Is(err, ErrAuthentication) || errors.Is(err, ErrBadRequest):
			action = actionAuthenticate
		default:
			return "", err
		}
	}
	if action == actionAuthenticate {
		req, _ := buildRequest(c.cfg, "credentials_post_usr_authenticate", nil, nil, creds)
		data, err := c.send(ctx, req, "")
		if err != nil {
			return "", err
		}
		m := asMap(data)
		if err := c.store.Save(ctx, c.keyID, c.tokens.setTokens(str(m["access"]), str(m["refresh"]))); err != nil {
			return "", err
		}
	}
	return c.tokens.tokens.Access, nil
}

// --- helpers --------------------------------------------------------------------------------

func (c *Client) list(ctx context.Context, endpointID string, pathParams, params Params) ([]any, error) {
	data, err := c.Request(ctx, endpointID, pathParams, params, nil)
	if err != nil {
		return nil, err
	}
	return asList(data), nil
}

func optionalMarketID(symbol string) (any, error) {
	if symbol == "" {
		return nil, nil
	}
	return MarketID(symbol)
}

func merge(base Params, extra Params) Params {
	out := Params{}
	for k, v := range base {
		if v != nil {
			out[k] = v
		}
	}
	for k, v := range extra {
		out[k] = v
	}
	return out
}

func isoParam(ms int64) any {
	if ms == 0 {
		return nil
	}
	return time.UnixMilli(ms).UTC().Format("2006-01-02T15:04:05.000+00:00")
}

func limitParam(limit int) any {
	if limit == 0 {
		return nil
	}
	return limit
}

// --- markets --------------------------------------------------------------------------------

// FetchMarkets returns every market, with precision (tick sizes) and Active.
func (c *Client) FetchMarkets(ctx context.Context) ([]Market, error) {
	rows, err := c.list(ctx, "public_get_mkt_markets", nil, nil)
	if err != nil {
		return nil, err
	}
	out := make([]Market, 0, len(rows))
	for _, r := range rows {
		out = append(out, parseMarket(asMap(r)))
	}
	return out, nil
}

// LoadMarkets fetches markets once (or again with reload) and caches them.
func (c *Client) LoadMarkets(ctx context.Context, reload bool) (map[string]Market, error) {
	c.marketsMu.RLock()
	cached := c.markets
	c.marketsMu.RUnlock()
	if cached != nil && !reload {
		return cached, nil
	}
	markets, err := c.FetchMarkets(ctx)
	if err != nil {
		return nil, err
	}
	bySymbol, byID := map[string]Market{}, map[string]Market{}
	for _, m := range markets {
		bySymbol[m.Symbol], byID[m.ID] = m, m
	}
	c.marketsMu.Lock()
	c.markets, c.marketsByID = bySymbol, byID
	c.marketsMu.Unlock()
	return bySymbol, nil
}

// Market returns a cached market for "BTC/IRT" or "BTC_IRT". Call LoadMarkets first.
func (c *Client) Market(symbol string) (Market, error) {
	c.marketsMu.RLock()
	defer c.marketsMu.RUnlock()
	if c.markets == nil {
		return Market{}, newError(ErrBitpin, "markets not loaded; call LoadMarkets first")
	}
	id, err := MarketID(symbol)
	if err != nil {
		return Market{}, err
	}
	m, ok := c.marketsByID[id]
	if !ok {
		return Market{}, newError(ErrBadSymbol, "unknown market %s", symbolOrRaw(id))
	}
	return m, nil
}

// FetchCurrencies returns every currency by code.
func (c *Client) FetchCurrencies(ctx context.Context) (map[string]Currency, error) {
	rows, err := c.list(ctx, "public_get_mkt_currencies", nil, nil)
	if err != nil {
		return nil, err
	}
	out := map[string]Currency{}
	for _, r := range rows {
		cur := parseCurrency(asMap(r))
		out[cur.Code] = cur
	}
	return out, nil
}

// FetchNetworks returns every network; params: code, can_deposit, can_withdraw.
func (c *Client) FetchNetworks(ctx context.Context, params Params) ([]Network, error) {
	rows, err := c.list(ctx, "public_get_mkt_networks", nil, params)
	if err != nil {
		return nil, err
	}
	out := make([]Network, 0, len(rows))
	for _, r := range rows {
		out = append(out, parseNetwork(asMap(r)))
	}
	return out, nil
}

// FetchMarketSuspensions returns {symbol: suspended} for your account (2 requests per minute).
func (c *Client) FetchMarketSuspensions(ctx context.Context) (map[string]bool, error) {
	rows, err := c.list(ctx, "private_get_mkt_markets_suspensions", nil, nil)
	if err != nil {
		return nil, err
	}
	out := map[string]bool{}
	for _, r := range rows {
		m := asMap(r)
		out[symbolOrRaw(m["code"])] = truthy(m["suspended"])
	}
	return out, nil
}

// --- tickers, order book, trades, candles ----------------------------------------------------

// FetchTickers returns tickers by symbol; pass symbols to filter.
func (c *Client) FetchTickers(ctx context.Context, symbols ...string) (map[string]Ticker, error) {
	rows, err := c.list(ctx, "public_get_mkt_tickers", nil, nil)
	if err != nil {
		return nil, err
	}
	wanted := map[string]bool{}
	for _, s := range symbols {
		id, err := MarketID(s)
		if err != nil {
			return nil, err
		}
		wanted[symbolOrRaw(id)] = true
	}
	out := map[string]Ticker{}
	for _, r := range rows {
		t := parseTicker(asMap(r))
		if len(wanted) == 0 || wanted[t.Symbol] {
			out[t.Symbol] = t
		}
	}
	return out, nil
}

// FetchTicker returns one market's 24h ticker.
func (c *Client) FetchTicker(ctx context.Context, symbol string) (Ticker, error) {
	id, err := MarketID(symbol)
	if err != nil {
		return Ticker{}, err
	}
	unified := symbolOrRaw(id)
	tickers, err := c.FetchTickers(ctx, unified)
	if err != nil {
		return Ticker{}, err
	}
	t, ok := tickers[unified]
	if !ok {
		return Ticker{}, newError(ErrBadSymbol, "no ticker for %s", unified)
	}
	return t, nil
}

// FetchOrderBook returns the top of the book: 20 levels by default, limit at most 50.
func (c *Client) FetchOrderBook(ctx context.Context, symbol string, limit int) (OrderBook, error) {
	if max := specConstants["orderbook_max_limit"]; limit > max {
		return OrderBook{}, newError(ErrBadRequest, "order book limit is at most %d", max)
	}
	id, err := MarketID(symbol)
	if err != nil {
		return OrderBook{}, err
	}
	data, err := c.Request(ctx, "public_get_mth_orderbook_symbol", Params{"symbol": id}, Params{"limit": limitParam(limit)}, nil)
	if err != nil {
		return OrderBook{}, err
	}
	return parseOrderBook(asMap(data), symbolOrRaw(id), nil), nil
}

// FetchTrades returns recent public trades, oldest first; since (ms) and limit filter locally.
func (c *Client) FetchTrades(ctx context.Context, symbol string, since int64, limit int) ([]Trade, error) {
	id, err := MarketID(symbol)
	if err != nil {
		return nil, err
	}
	rows, err := c.list(ctx, "public_get_mth_matches_symbol", Params{"symbol": id}, nil)
	if err != nil {
		return nil, err
	}
	trades := []Trade{}
	for _, r := range rows {
		t := parseTrade(asMap(r), symbolOrRaw(id))
		if since == 0 || (t.Timestamp != nil && *t.Timestamp >= since) {
			trades = append(trades, t)
		}
	}
	sort.SliceStable(trades, func(i, j int) bool { return ms(trades[i].Timestamp) < ms(trades[j].Timestamp) })
	if limit > 0 && len(trades) > limit {
		trades = trades[len(trades)-limit:]
	}
	return trades, nil
}

func ms(p *int64) int64 {
	if p == nil {
		return 0
	}
	return *p
}

// FetchOHLCV returns candles, oldest first. Without since: the latest limit candles (500).
func (c *Client) FetchOHLCV(ctx context.Context, symbol, timeframe string, since int64, limit int, params Params) ([]OHLCV, error) {
	if timeframe == "" {
		timeframe = "30m"
	}
	step, ok := Timeframes[timeframe]
	if !ok {
		return nil, newError(ErrBadRequest, "timeframe %q is not supported", timeframe)
	}
	if limit < 0 {
		return nil, newError(ErrBadRequest, "FetchOHLCV limit must be at least 1")
	}
	count := limit
	if count == 0 {
		count = defaultOHLCVLimit
	}
	if max := specConstants["candles_max_per_request"]; count > max {
		return nil, newError(ErrBadRequest, "at most %d candles per request", max)
	}
	id, err := MarketID(symbol)
	if err != nil {
		return nil, err
	}
	var start, end int64
	if since == 0 {
		end = c.cfg.Clock().Unix()
		start = end - int64(count)*step
	} else {
		start = since / 1000
		end = start + int64(count)*step
	}
	rows, err := c.list(ctx, "public_get_mkt_candles", nil, merge(Params{"symbol": id, "res": timeframe, "from": start, "to": end}, params))
	if err != nil {
		return nil, err
	}
	candles := make([]OHLCV, 0, len(rows))
	for _, r := range rows {
		candles = append(candles, parseOHLCV(asMap(r)))
	}
	if len(candles) > count {
		if since == 0 {
			candles = candles[len(candles)-count:]
		} else {
			candles = candles[:count]
		}
	}
	return candles, nil
}

// FetchTradingFees returns your maker/taker fees per market, as ratios (0.003 = 0.3 %).
func (c *Client) FetchTradingFees(ctx context.Context) (map[string]TradingFee, error) {
	rows, err := c.list(ctx, "private_get_mkt_commissions", nil, nil)
	if err != nil {
		return nil, err
	}
	out := map[string]TradingFee{}
	for _, r := range rows {
		f := parseTradingFee(asMap(r))
		out[f.Symbol] = f
	}
	return out, nil
}

// FetchTradingFee returns one market's fee.
func (c *Client) FetchTradingFee(ctx context.Context, symbol string) (TradingFee, error) {
	id, err := MarketID(symbol)
	if err != nil {
		return TradingFee{}, err
	}
	fees, err := c.FetchTradingFees(ctx)
	if err != nil {
		return TradingFee{}, err
	}
	f, ok := fees[symbolOrRaw(id)]
	if !ok {
		return TradingFee{}, newError(ErrBadSymbol, "no trading fee for %s", symbolOrRaw(id))
	}
	return f, nil
}

// --- orders ---------------------------------------------------------------------------------

func checkPositive(name string, value any) error {
	if value == nil {
		return nil
	}
	d, err := toDecimal(value)
	if err != nil || (d != nil && !d.IsPositive()) {
		return newError(ErrInvalidOrder, "%s must be positive", name)
	}
	return nil
}

// orderBody validates an order locally and builds the request body.
func orderBody(symbol, typ, side string, amount, price any, params Params) (Params, error) {
	known := false
	for _, t := range orderTypes {
		known = known || t == typ
	}
	if !known {
		return nil, newError(ErrInvalidOrder, "order type must be one of %s", strings.Join(orderTypes, ", "))
	}
	if side != "buy" && side != "sell" {
		return nil, newError(ErrInvalidOrder, "order side must be 'buy' or 'sell'")
	}
	id, err := MarketID(symbol)
	if err != nil {
		return nil, err
	}
	extra := Params{}
	keys := make([]string, 0, len(params))
	for k := range params {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		name := k
		if alias, ok := paramAliases[k]; ok {
			name = alias
		}
		if prev, ok := extra[name]; ok && fmt.Sprint(prev) != fmt.Sprint(params[k]) {
			return nil, newError(ErrInvalidOrder, "params set %s twice (%q); pass only one of both", name, k)
		}
		extra[name] = params[k]
	}
	body := Params{"symbol": id, "type": typ, "side": side}
	if amount != nil {
		body["base_amount"] = amount
	}
	if price != nil && typ != "market" {
		body["price"] = price
	}
	for k, v := range extra {
		if v != nil {
			body[k] = v
		}
	}
	for field, name := range map[string]string{"base_amount": "amount", "price": "price", "stop_price": "params.stopPrice",
		"oco_target_price": "params.takeProfitPrice", "quote_amount": "params.quoteAmount"} {
		if err := checkPositive(name, body[field]); err != nil {
			return nil, err
		}
	}
	_, hasBase := body["base_amount"]
	_, hasQuote := body["quote_amount"]
	if typ == "market" {
		if hasBase && hasQuote {
			return nil, newError(ErrInvalidOrder, "market orders take only one of amount or quoteAmount")
		}
		if !hasBase && !hasQuote {
			return nil, newError(ErrInvalidOrder, "market orders need amount or params.quoteAmount")
		}
		return body, nil
	}
	if !hasBase {
		return nil, newError(ErrInvalidOrder, "%s orders need an amount", typ)
	}
	if _, ok := body["price"]; !ok {
		return nil, newError(ErrInvalidOrder, "%s orders need a price", typ)
	}
	if _, ok := body["stop_price"]; !ok && (typ == "stop_limit" || typ == "oco") {
		return nil, newError(ErrInvalidOrder, "%s orders need params.stopPrice", typ)
	}
	if _, ok := body["oco_target_price"]; !ok && typ == "oco" {
		return nil, newError(ErrInvalidOrder, "oco orders need params.takeProfitPrice")
	}
	return body, nil
}

// CreateOrder places an order. typ: limit, market, stop_limit or oco. amount and price are
// Decimal, string or number (nil when not needed). params: clientOrderId, quoteAmount (market
// by quote), stopPrice/triggerPrice, takeProfitPrice (oco). It is never retried.
func (c *Client) CreateOrder(ctx context.Context, symbol, typ, side string, amount, price any, params Params) (Order, error) {
	body, err := orderBody(symbol, typ, side, amount, price, params)
	if err != nil {
		return Order{}, err
	}
	data, err := c.Request(ctx, "private_post_odr_orders", nil, nil, body)
	if err != nil {
		return Order{}, err
	}
	return parseOrder(asMap(data)), nil
}

// CreateOrders places up to 10 orders in one atomic request.
func (c *Client) CreateOrders(ctx context.Context, orders []OrderRequest) ([]Order, error) {
	max := specConstants["bulk_orders_max"]
	if len(orders) == 0 {
		return nil, newError(ErrBadRequest, "CreateOrders needs at least one order")
	}
	if len(orders) > max {
		return nil, newError(ErrBadRequest, "CreateOrders takes at most %d orders", max)
	}
	bodies := make([]any, 0, len(orders))
	for _, o := range orders {
		b, err := orderBody(o.Symbol, o.Type, o.Side, o.Amount, o.Price, o.Params)
		if err != nil {
			return nil, err
		}
		bodies = append(bodies, b)
	}
	data, err := c.Request(ctx, "private_post_odr_orders_bulk", nil, nil, bodies)
	if err != nil {
		return nil, err
	}
	return parseBulkOrders(data), nil
}

// FetchOrder returns one of your orders.
func (c *Client) FetchOrder(ctx context.Context, id string) (Order, error) {
	data, err := c.Request(ctx, "private_get_odr_orders_id", Params{"id": id}, nil, nil)
	if err != nil {
		return Order{}, err
	}
	return parseOrder(asMap(data)), nil
}

// FetchOrdersOptions are the ccxt optional arguments; Params also takes paginate (bool) and
// maxPages (int).
type FetchOrdersOptions struct {
	Symbol string
	Since  int64 // ms
	Limit  int
	Params Params
}

func sortOrders(orders []Order) {
	sort.SliceStable(orders, func(i, j int) bool {
		if ms(orders[i].Timestamp) != ms(orders[j].Timestamp) {
			return ms(orders[i].Timestamp) < ms(orders[j].Timestamp)
		}
		a, _ := strconv.ParseInt(orders[i].ID, 10, 64)
		b, _ := strconv.ParseInt(orders[j].ID, 10, 64)
		return a < b
	})
}

// FetchOrders returns active orders and orders closed in the last 7 days, oldest first.
func (c *Client) FetchOrders(ctx context.Context, opts FetchOrdersOptions) ([]Order, error) {
	id, err := optionalMarketID(opts.Symbol)
	if err != nil {
		return nil, err
	}
	rows, err := c.paged(ctx, "private_get_odr_orders", Params{"symbol": id, "start": isoParam(opts.Since), "limit": limitParam(opts.Limit)}, opts.Params)
	if err != nil {
		return nil, err
	}
	orders := make([]Order, 0, len(rows))
	for _, r := range rows {
		orders = append(orders, parseOrder(asMap(r)))
	}
	sortOrders(orders)
	return orders, nil
}

// FetchOpenOrders returns initial and active orders.
func (c *Client) FetchOpenOrders(ctx context.Context, opts FetchOrdersOptions) ([]Order, error) {
	opts.Params = merge(opts.Params, Params{"state": []string{"initial", "active"}})
	return c.FetchOrders(ctx, opts)
}

// FetchClosedOrders returns orders closed in the last 7 days; older ones: FetchOrderHistory.
func (c *Client) FetchClosedOrders(ctx context.Context, opts FetchOrdersOptions) ([]Order, error) {
	opts.Params = merge(opts.Params, Params{"state": "closed"})
	return c.FetchOrders(ctx, opts)
}

// CancelOrder asks the engine to cancel; the order closes a moment later. Never retried.
func (c *Client) CancelOrder(ctx context.Context, id string) error {
	_, err := c.Request(ctx, "private_delete_odr_orders_id", Params{"id": id}, nil, nil)
	return err
}

// CancelOrderByIdentifier cancels by your clientOrderId.
func (c *Client) CancelOrderByIdentifier(ctx context.Context, identifier string) error {
	_, err := c.Request(ctx, "private_delete_odr_orders_identifier_identifier", Params{"identifier": identifier}, nil, nil)
	return err
}

// CancelOrders cancels up to 10 orders by ids or by identifiers (exactly one of them).
func (c *Client) CancelOrders(ctx context.Context, ids, identifiers []string) (CancelResult, error) {
	if (len(ids) == 0) == (len(identifiers) == 0) {
		return CancelResult{}, newError(ErrBadRequest, "CancelOrders needs exactly one of ids or identifiers")
	}
	key, values := "ids", ids
	if len(identifiers) > 0 {
		key, values = "identifiers", identifiers
	}
	if max := specConstants["bulk_orders_max"]; len(values) > max {
		return CancelResult{}, newError(ErrBadRequest, "CancelOrders takes at most %d orders", max)
	}
	data, err := c.Request(ctx, "private_delete_odr_orders_bulk", nil, nil, Params{key: values})
	if err != nil {
		return CancelResult{}, err
	}
	m := asMap(data)
	strs := func(v any) []string {
		out := []string{}
		for _, item := range asList(v) {
			out = append(out, str(item))
		}
		return out
	}
	return CancelResult{Canceled: strs(m["canceled_orders"]), NotCanceled: strs(m["not_canceled_orders"]), Info: m}, nil
}

// FetchMyTrades returns your fills from the last 24 hours, oldest first.
func (c *Client) FetchMyTrades(ctx context.Context, opts FetchOrdersOptions) ([]Trade, error) {
	if opts.Since != 0 && float64(opts.Since) < float64(c.cfg.Clock().Unix()-int64(specConstants["fills_max_age_seconds"]))*1000 {
		return nil, newError(ErrBadRequest, "FetchMyTrades only covers the last 24 hours")
	}
	id, err := optionalMarketID(opts.Symbol)
	if err != nil {
		return nil, err
	}
	var start any
	if opts.Since != 0 {
		start = opts.Since / 1000
	}
	rows, err := c.paged(ctx, "private_get_odr_fills", Params{"symbol": id, "start": start, "limit": limitParam(opts.Limit)}, opts.Params)
	if err != nil {
		return nil, err
	}
	trades := make([]Trade, 0, len(rows))
	for _, r := range rows {
		trades = append(trades, parseMyTrade(asMap(r)))
	}
	sort.SliceStable(trades, func(i, j int) bool {
		if ms(trades[i].Timestamp) != ms(trades[j].Timestamp) {
			return ms(trades[i].Timestamp) < ms(trades[j].Timestamp)
		}
		a, _ := strconv.ParseInt(trades[i].ID, 10, 64)
		b, _ := strconv.ParseInt(trades[j].ID, 10, 64)
		return a < b
	})
	return trades, nil
}

// OrderHistoryOptions: Since/Until in ms (range at most 90 days), Limit 1..200, Params: side,
// type, service, paginate.
type OrderHistoryOptions struct {
	Symbol       string
	Since, Until int64
	Limit        int
	Params       Params
}

// FetchOrderHistory returns closed orders with at least one fill, newest first.
func (c *Client) FetchOrderHistory(ctx context.Context, opts OrderHistoryOptions) ([]Order, error) {
	max := specConstants["order_history_max_limit"]
	if opts.Limit != 0 && (opts.Limit < 1 || opts.Limit > max) {
		return nil, newError(ErrBadRequest, "order history limit must be 1..%d", max)
	}
	if opts.Limit < 0 {
		return nil, newError(ErrBadRequest, "order history limit must be 1..%d", max)
	}
	if opts.Since != 0 && opts.Until != 0 {
		if opts.Since >= opts.Until {
			return nil, newError(ErrBadRequest, "order history since must be before until")
		}
		if opts.Until-opts.Since > int64(specConstants["order_history_max_range_days"])*86_400_000 {
			return nil, newError(ErrBadRequest, "order history range is at most 90 days")
		}
	}
	id, err := optionalMarketID(opts.Symbol)
	if err != nil {
		return nil, err
	}
	extra := merge(nil, opts.Params)
	paginate := truthy(extra["paginate"])
	delete(extra, "paginate")
	filters := merge(Params{"symbol": id, "limit": limitParam(opts.Limit)}, extra)
	query := merge(filters, Params{"start": nilIfZero(opts.Since), "end": nilIfZero(opts.Until)})
	orders := []Order{}
	seenIDs, seenCursors := map[string]bool{}, map[string]bool{}
	for {
		data, err := c.Request(ctx, "private_get_odr_order_history", nil, query, nil)
		if err != nil {
			return nil, err
		}
		m := asMap(data)
		for _, r := range asList(m["results"]) {
			o := parseHistoryOrder(asMap(r))
			if !seenIDs[o.ID] {
				seenIDs[o.ID] = true
				orders = append(orders, o)
			}
		}
		cursor := str(m["next_cursor"])
		if !paginate || !truthy(m["has_next"]) || cursor == "" || seenCursors[cursor] {
			return orders, nil
		}
		seenCursors[cursor] = true
		// The cursor replaces start/end; the server doesn't keep the other filters.
		query = merge(filters, Params{"cursor": cursor})
	}
}

func nilIfZero(v int64) any {
	if v == 0 {
		return nil
	}
	return v
}

// --- wallet ---------------------------------------------------------------------------------

// FetchBalance returns the main wallet's balances (params: service for others).
func (c *Client) FetchBalance(ctx context.Context, params Params) (Balances, error) {
	rows, err := c.allPages(ctx, "private_get_wlt_wallets", merge(Params{"service": "main", "limit": specConstants["wallets_max_page_size"]}, params))
	if err != nil {
		return Balances{}, err
	}
	return parseBalance(rows), nil
}

// FetchBankAccounts returns your bank accounts; use an ID as accountNumber for IRT withdrawals.
func (c *Client) FetchBankAccounts(ctx context.Context) ([]BankAccount, error) {
	rows, err := c.list(ctx, "private_get_wlt_account_numbers", nil, nil)
	if err != nil {
		return nil, err
	}
	out := make([]BankAccount, 0, len(rows))
	for _, r := range rows {
		out = append(out, parseBankAccount(asMap(r)))
	}
	return out, nil
}

// FetchDepositAddress returns your address for code on network (created on first use).
func (c *Client) FetchDepositAddress(ctx context.Context, code, network string) (DepositAddress, error) {
	if network == "" {
		return DepositAddress{}, newError(ErrBadRequest, "FetchDepositAddress needs a network code, e.g. 'TRX'")
	}
	body := Params{"currency": strings.ToUpper(code), "network": strings.ToUpper(network)}
	data, err := c.Request(ctx, "private_post_wlt_address", nil, nil, body)
	if err != nil {
		return DepositAddress{}, err
	}
	return parseDepositAddress(asMap(data), strings.ToUpper(network)), nil
}

// FetchCurrencyNetworks returns one currency's networks with deposit/withdraw availability.
func (c *Client) FetchCurrencyNetworks(ctx context.Context, code string) ([]Network, error) {
	rows, err := c.list(ctx, "private_get_wlt_networks", nil, Params{"currency_code": strings.ToUpper(code)})
	if err != nil {
		return nil, err
	}
	out := make([]Network, 0, len(rows))
	for _, r := range rows {
		out = append(out, parseCurrencyNetwork(asMap(r)))
	}
	return out, nil
}

// TransactionsOptions: Code, Since (ms), Limit; Params: network, state, end, paginate, …
type TransactionsOptions struct {
	Code   string
	Since  int64
	Limit  int
	Params Params
}

// FetchDeposits returns your deposits.
func (c *Client) FetchDeposits(ctx context.Context, opts TransactionsOptions) ([]Transaction, error) {
	rows, err := c.paged(ctx, "private_get_wlt_deposits", Params{"currency": upperOrNil(opts.Code), "start": isoParam(opts.Since), "limit": limitParam(opts.Limit)}, opts.Params)
	if err != nil {
		return nil, err
	}
	out := make([]Transaction, 0, len(rows))
	for _, r := range rows {
		out = append(out, parseDeposit(asMap(r)))
	}
	return out, nil
}

// FetchWithdrawals returns your withdrawals; Since is applied per day.
func (c *Client) FetchWithdrawals(ctx context.Context, opts TransactionsOptions) ([]Transaction, error) {
	var start any
	if opts.Since != 0 {
		start = time.UnixMilli(opts.Since).UTC().Format("2006-01-02")
	}
	rows, err := c.paged(ctx, "private_get_wlt_withdraws", Params{"currency": upperOrNil(opts.Code), "start": start, "limit": limitParam(opts.Limit)}, opts.Params)
	if err != nil {
		return nil, err
	}
	out := make([]Transaction, 0, len(rows))
	for _, r := range rows {
		out = append(out, parseWithdrawal(asMap(r)))
	}
	return out, nil
}

func upperOrNil(s string) any {
	if s == "" {
		return nil
	}
	return strings.ToUpper(s)
}

// Withdraw creates a withdrawal, sent only after VerifyWithdrawOTP (twice unless
// Info["is_single_otp"]). Crypto: address + params{"network": "TRX"} (tag = memo);
// IRT: params{"accountNumber": id}; internal transfer: params{"alternativeAddress": phone or email}.
func (c *Client) Withdraw(ctx context.Context, code string, amount any, address, tag string, params Params) (Transaction, error) {
	if err := checkPositive("withdraw amount", amount); err != nil || amount == nil {
		return Transaction{}, newError(ErrBadRequest, "withdraw amount must be positive")
	}
	extra := merge(nil, params)
	take := func(keys ...string) any {
		for _, k := range keys {
			if v, ok := extra[k]; ok {
				delete(extra, k)
				return v
			}
		}
		return nil
	}
	network := take("network")
	account := take("accountNumber", "account_number")
	alternative := take("alternativeAddress", "alternative_address")
	body := Params{"currency": strings.ToUpper(code), "amount": amount}
	switch {
	case alternative != nil:
		body["alternative_address"] = alternative
	case account != nil:
		body["account_number"] = str(account)
	case address != "":
		if network == nil {
			return Transaction{}, newError(ErrBadRequest, "crypto withdrawals need params[\"network\"]")
		}
		body["address"] = address
		body["network"] = strings.ToUpper(str(network))
		if tag != "" {
			body["memo"] = tag
		}
	default:
		return Transaction{}, newError(ErrBadRequest, "Withdraw needs an address, params[\"accountNumber\"] or params[\"alternativeAddress\"]")
	}
	for k, v := range extra {
		body[k] = v
	}
	data, err := c.Request(ctx, "private_post_wlt_withdraws", nil, nil, body)
	if err != nil {
		return Transaction{}, err
	}
	return parseWithdrawal(asMap(data)), nil
}

// VerifyWithdrawOTP confirms a withdrawal: first your authenticator code, then (second=true)
// the code sent to you.
func (c *Client) VerifyWithdrawOTP(ctx context.Context, id, otp string, second bool) (Info, error) {
	data, err := c.Request(ctx, "private_post_wlt_withdraws_verify_otp_id", Params{"id": id}, nil, Params{"otp": otp, "is_second_otp": second})
	return asMap(data), err
}

// ResendWithdrawOTP sends the OTP of a withdrawal in the initial state again.
func (c *Client) ResendWithdrawOTP(ctx context.Context, id string, first, voiceCall bool) (Info, error) {
	data, err := c.Request(ctx, "private_post_wlt_withdraws_retry_id", Params{"id": id}, nil, Params{"first": first, "use_voice_call": voiceCall})
	return asMap(data), err
}

// --- pagination -----------------------------------------------------------------------------

func (c *Client) paged(ctx context.Context, endpointID string, query, params Params) ([]any, error) {
	merged := merge(query, params)
	if truthy(merged["paginate"]) {
		delete(merged, "paginate")
		return c.allPages(ctx, endpointID, merged)
	}
	delete(merged, "paginate")
	delete(merged, "maxPages")
	return c.list(ctx, endpointID, nil, merged)
}

// allPages walks an id-cursor list: offset means "ids below this", not a row count.
func (c *Client) allPages(ctx context.Context, endpointID string, query Params) ([]any, error) {
	maxPages := 100
	if v, ok := query["maxPages"].(int); ok {
		maxPages = v
	}
	delete(query, "maxPages")
	if query["limit"] == nil {
		query["limit"] = specConstants[maxPageSize[endpointID]]
	}
	limit, _ := strconv.Atoi(fmt.Sprint(query["limit"]))
	rows := []any{}
	var offset *int64
	for page := 0; page < maxPages; page++ {
		batch, err := c.list(ctx, endpointID, nil, query)
		if err != nil {
			return nil, err
		}
		if len(batch) == 0 {
			break
		}
		lowest := int64(-1)
		for _, r := range batch {
			id, _ := strconv.ParseInt(str(asMap(r)["id"]), 10, 64)
			if lowest < 0 || id < lowest {
				lowest = id
			}
		}
		if offset != nil && lowest >= *offset {
			break // the server didn't move past the last page
		}
		rows = append(rows, batch...)
		if len(batch) < limit {
			break
		}
		offset = &lowest
		query["offset"] = lowest
	}
	return rows, nil
}

// --- not offered by Bitpin yet ----------------------------------------------------------------

func (c *Client) CancelAllOrders(context.Context) error { return notSupported("cancelAllOrders") }
func (c *Client) EditOrder(context.Context) error       { return notSupported("editOrder") }
func (c *Client) FetchAccounts(context.Context) error   { return notSupported("fetchAccounts") }
func (c *Client) FetchLedger(context.Context) error     { return notSupported("fetchLedger") }
func (c *Client) Transfer(context.Context) error        { return notSupported("transfer") }
func (c *Client) FetchDepositWithdrawFees(context.Context) error {
	return notSupported("fetchDepositWithdrawFees")
}
func (c *Client) FetchPositions(context.Context) error { return notSupported("fetchPositions") }
func (c *Client) SetLeverage(context.Context) error    { return notSupported("setLeverage") }
func (c *Client) CreateDepositAddress(context.Context) error {
	return notSupported("createDepositAddress")
}
func (c *Client) WatchBalance(context.Context) error { return notSupported("watchBalance") }
func (c *Client) WatchTickers(context.Context) error { return notSupported("watchTickers") }
func (c *Client) SetSandboxMode(bool) error          { return notSupported("sandbox") }
