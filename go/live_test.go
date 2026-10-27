//go:build live

// Live, read-only checks against the real Bitpin API. Never run in CI.
//
//	BITPIN_LIVE=1 [BITPIN_API_KEY=... BITPIN_SECRET_KEY=...] go test -tags live -run Live ./...
package bitpin

import (
	"fmt"
	"net/http"
	"os"
	"testing"
)

var allowedWrites = map[string]bool{"/api/v1/usr/authenticate/": true, "/api/v1/usr/refresh_token/": true, "/api/v1/usr/ws-info/": true}

type readOnly struct{ next http.RoundTripper }

func (r readOnly) RoundTrip(req *http.Request) (*http.Response, error) {
	if req.Method != http.MethodGet && !allowedWrites[req.URL.Path] {
		return nil, fmt.Errorf("live tests are read-only: refused %s %s", req.Method, req.URL.Path)
	}
	return r.next.RoundTrip(req)
}

func liveClient(t *testing.T) *Client {
	if os.Getenv("BITPIN_LIVE") != "1" {
		t.Skip("set BITPIN_LIVE=1")
	}
	cfg := ConfigFromEnv()
	cfg.HTTPClient = &http.Client{Transport: readOnly{http.DefaultTransport}}
	cfg.MaxRetries = Int(1)
	c, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	return c
}

// shapeOf checks every key of the fixture's first row exists live with the same JSON type.
func checkShape(t *testing.T, endpointID string, live any) {
	first := func(v any) Info {
		if l := asList(v); len(l) > 0 {
			return asMap(l[0])
		}
		if m := asMap(v); m != nil {
			if r := asList(m["results"]); len(r) > 0 {
				return asMap(r[0])
			}
			return m
		}
		return nil
	}
	want, got := first(fixtureBody(t, endpointID)), first(live)
	if want == nil || got == nil {
		return
	}
	for key, value := range want {
		actual, ok := got[key]
		if !ok {
			t.Errorf("%s: missing field %s", endpointID, key)
			continue
		}
		if value != nil && actual != nil && fmt.Sprintf("%T", value) != fmt.Sprintf("%T", actual) {
			t.Errorf("%s.%s: type %T, fixture %T", endpointID, key, actual, value)
		}
	}
}

func TestLivePublic(t *testing.T) {
	c := liveClient(t)
	for _, id := range []string{"public_get_mkt_currencies", "public_get_mkt_markets", "public_get_mkt_networks", "public_get_mkt_tickers"} {
		checkShape(t, id, must[any](t)(c.Request(ctx, id, nil, nil, nil)))
	}
	checkShape(t, "public_get_mth_orderbook_symbol", must[any](t)(c.Request(ctx, "public_get_mth_orderbook_symbol", Params{"symbol": "USDT_IRT"}, nil, nil)))
	if len(must[map[string]Market](t)(c.LoadMarkets(ctx, false))) == 0 {
		t.Error("no markets")
	}
	must[Ticker](t)(c.FetchTicker(ctx, "USDT/IRT"))
	must[[]OHLCV](t)(c.FetchOHLCV(ctx, "USDT/IRT", "1h", 0, 5, nil))
}

func TestLivePrivateReads(t *testing.T) {
	c := liveClient(t)
	if os.Getenv("BITPIN_API_KEY") == "" {
		t.Skip("set BITPIN_API_KEY and BITPIN_SECRET_KEY")
	}
	for _, id := range []string{"private_get_mkt_commissions", "private_get_odr_orders", "private_get_odr_fills", "private_get_wlt_wallets", "private_get_wlt_deposits", "private_get_wlt_withdraws"} {
		checkShape(t, id, must[any](t)(c.Request(ctx, id, nil, Params{"limit": 5}, nil)))
	}
	must[Balances](t)(c.FetchBalance(ctx, nil))
	if _, err := c.CreateOrder(ctx, "USDT/IRT", "limit", "buy", "1", "1", nil); err == nil {
		t.Error("the read-only guard must refuse writes")
	}
}
