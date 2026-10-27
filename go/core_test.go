package bitpin

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/shopspring/decimal"
)

func TestFormatDecimal(t *testing.T) {
	cases := []struct {
		in   any
		want string
	}{
		{decimal.RequireFromString("1E-8"), "0.00000001"}, {0.1, "0.1"}, {1e-7, "0.0000001"}, {100, "100"},
		{decimal.RequireFromString("1E+3"), "1000"}, {"63.0", "63"}, {"0.000", "0"}, {"-1.50", "-1.5"},
		{int64(3145737420), "3145737420"}, {float32(0.5), "0.5"},
	}
	for _, c := range cases {
		got, err := formatDecimal(c.in)
		if err != nil || got != c.want {
			t.Errorf("formatDecimal(%v) = %q, %v; want %q", c.in, got, err, c.want)
		}
	}
	for _, bad := range []any{"abc", true, nil, struct{}{}} {
		if _, err := formatDecimal(bad); err == nil {
			t.Errorf("formatDecimal(%v) should fail", bad)
		}
	}
	var nilDec *decimal.Decimal
	if d, _ := toDecimal(nilDec); d != nil {
		t.Error("nil *Decimal should be nil")
	}
	d := decimal.NewFromInt(5)
	eq(t, must[*Decimal](t)(toDecimal(&d)).String(), "5")
	if dec("junk") != nil || dec("") != nil {
		t.Error("dec should be lenient")
	}
}

func TestSymbols(t *testing.T) {
	for _, s := range []string{"BTC/IRT", "btc/irt", "BTC_IRT", "btc_irt", " BTC/IRT "} {
		eq(t, must[string](t)(MarketID(s)), "BTC_IRT")
	}
	eq(t, must[string](t)(MarketID("1INCH/USDT")), "1INCH_USDT")
	for _, bad := range []string{"BTCIRT", "BTC-IRT", "BTC/", "/IRT", "BTC/IRT/X", "", "BTC_I RT"} {
		if _, err := MarketID(bad); !errors.Is(err, ErrBadSymbol) {
			t.Errorf("MarketID(%q) = %v, want BadSymbol", bad, err)
		}
	}
	eq(t, must[string](t)(Symbol("BTC_IRT")), "BTC/IRT")
	if _, err := Symbol("BTCIRT"); !errors.Is(err, ErrBadSymbol) {
		t.Error("Symbol should reject")
	}
	eq(t, symbolOrRaw("weird"), "weird")
}

func TestLimiter(t *testing.T) {
	now := 1000.0
	l := newLimiter(map[string]RateLimit{"auth": {3, "min"}}, func() float64 { return now })
	for _, step := range []float64{0, 10, 20} {
		now = 1000 + step
		eq(t, l.reserve([]string{"auth"}), 0)
	}
	now = 1030
	eq(t, l.reserve([]string{"auth"}), 30)

	burst := newLimiter(map[string]RateLimit{"a": {2, "sec"}}, func() float64 { return 1000 })
	var waits []float64
	for i := 0; i < 8; i++ {
		waits = append(waits, burst.reserve([]string{"a"}))
	}
	eq(t, waits, []float64{0, 0, 1, 1, 2, 2, 3, 3})

	multi := newLimiter(map[string]RateLimit{"a": {1, "sec"}, "b": {1, "min"}}, func() float64 { return 1000 })
	eq(t, multi.reserve([]string{"a", "b", "x"}), 0)
	eq(t, multi.reserve([]string{"a", "b"}), 60)

	pruned := newLimiter(map[string]RateLimit{"a": {2, "sec"}}, func() float64 { return now })
	pruned.reserve([]string{"a"})
	pruned.reserve([]string{"a"})
	now += 5
	eq(t, pruned.reserve([]string{"a"}), 0)
	eq(t, len(pruned.calls["a"]), 1)
}

func TestConfigAndDomains(t *testing.T) {
	r := must[resolvedConfig](t)(Config{}.resolve())
	eq(t, []any{r.Domain, r.RestURL, r.WSURL, r.maxRetries, r.Timeout.Seconds()}, []any{"org", "https://api.bitpin.org", "wss://centrifugo.bitpin.org/connection/websocket", 3, 10})
	eq(t, r.rateLimits["auth"], RateLimit{3, "min"})
	for _, c := range []struct{ d, rest, ws string }{
		{"ir", "https://api.bitpin.ir", "wss://centrifugo.bitpin.ir/connection/websocket"},
		{"market", "https://api.bitpin.market", "wss://centrifugo.bitpin.market/connection/websocket"},
	} {
		r := must[resolvedConfig](t)(Config{Domain: Domain(c.d)}.resolve())
		eq(t, []string{r.RestURL, r.WSURL}, []string{c.rest, c.ws})
	}
	custom := must[resolvedConfig](t)(Config{Domain: DomainIR, RestURL: "https://proxy.example"}.resolve())
	eq(t, []string{custom.RestURL, custom.WSURL}, []string{"https://proxy.example", "wss://centrifugo.bitpin.ir/connection/websocket"})
	if _, err := (Config{Domain: "com"}).resolve(); err == nil || err.Error() != `unknown domain "com"; use one of: ir, market, org` {
		t.Errorf("bad domain: %v", err)
	}
	over := must[resolvedConfig](t)(Config{RateLimits: map[string]string{"orderbook": "10800/min"}, MaxRetries: Int(0)}.resolve())
	eq(t, []any{over.rateLimits["orderbook"], over.rateLimits["matches"], over.maxRetries}, []any{RateLimit{10800, "min"}, RateLimit{60, "min"}, 0})
	for _, bad := range []Config{{RateLimits: map[string]string{"orderbok": "1/min"}}, {RateLimits: map[string]string{"orderbook": "x"}}, {MaxRetries: Int(-1)}} {
		if _, err := bad.resolve(); err == nil {
			t.Errorf("%v should fail", bad.RateLimits)
		}
	}
	for _, s := range []string{"10/minute", "x/min", "0/min", "10"} {
		if _, err := ParseRateLimit(s); err == nil {
			t.Errorf("ParseRateLimit(%q) should fail", s)
		}
	}
	eq(t, []float64{RateLimit{1, "sec"}.PeriodSeconds(), RateLimit{1, "day"}.PeriodSeconds()}, []float64{1, 86400})
	text := fmt.Sprintf("%v %#v %s", Config{APIKey: "AKEY", SecretKey: "SKEY"}, Config{APIKey: "AKEY"}, Config{})
	if strings.Contains(text, "AKEY") || strings.Contains(text, "SKEY") || !strings.Contains(text, "***") {
		t.Errorf("config leaks secrets: %s", text)
	}
	t.Setenv("BITPIN_API_KEY", "ek")
	t.Setenv("BITPIN_SECRET_KEY", "es")
	t.Setenv("BITPIN_DOMAIN", "market")
	eq(t, ConfigFromEnv(), Config{APIKey: "ek", SecretKey: "es", Domain: DomainMarket})
}

func TestTokens(t *testing.T) {
	if exp, ok := jwtExp(makeJWT(1234)); !ok || exp != 1234 {
		t.Error("jwtExp")
	}
	b := func(s string) string { return "e30." + strings.TrimRight(base64url(s), "=") + ".sig" }
	for _, bad := range []string{"not-a-jwt", "a.!!!.c", b(`{"no":1}`), b(`{"exp":"soon"}`), b(`[1]`), b(`{"exp":1e999}`)} {
		if _, ok := jwtExp(bad); ok {
			t.Errorf("jwtExp(%q) should fail", bad)
		}
	}
	now := 1_000_000.0
	s := tokenState{clock: func() float64 { return now }}
	eq(t, s.action(), actionAuthenticate)
	s.setTokens(makeJWT(now+900), makeJWT(now+86400))
	eq(t, s.action(), actionOK)
	now += 900 - 121
	eq(t, s.action(), actionOK)
	now++
	eq(t, s.action(), actionRefresh)
	old := s.tokens.Access
	s.setAccess(makeJWT(now + 1800))
	s.expireAccess(old)
	eq(t, s.action(), actionOK)
	s.expireAccess(s.tokens.Access)
	eq(t, s.action(), actionRefresh)
	now = 1_000_000 + 86400
	eq(t, s.action(), actionAuthenticate)
	opaque := tokenState{clock: func() float64 { return 5 }}
	eq(t, opaque.setTokens("a", "r"), Tokens{"a", "r", 905, 5 + 2592000})
	text := fmt.Sprintf("%v %#v", Tokens{Access: "ACCESS-SECRET"}, Tokens{Refresh: "REFRESH-SECRET"})
	if strings.Contains(text, "SECRET") {
		t.Error("tokens leak")
	}
}

func base64url(s string) string { return strings.NewReplacer("+", "-", "/", "_").Replace(b64(s)) }

func b64(s string) string {
	const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
	var out strings.Builder
	data := []byte(s)
	for i := 0; i < len(data); i += 3 {
		var n uint32
		k := 0
		for j := 0; j < 3; j++ {
			n <<= 8
			if i+j < len(data) {
				n |= uint32(data[i+j])
				k++
			}
		}
		for j := 0; j <= k; j++ {
			out.WriteByte(chars[(n>>(18-6*j))&63])
		}
	}
	return out.String()
}

func TestErrorMapping(t *testing.T) {
	cases := []struct {
		id     string
		status int
		body   any
		want   error
	}{
		{"private_get_wlt_wallets", 401, map[string]any{"detail": "x"}, ErrAuthentication},
		{"credentials_post_usr_authenticate", 406, map[string]any{"detail": "api_credential_wrong"}, ErrAuthentication},
		{"private_post_wlt_address", 403, nil, ErrPermissionDenied},
		{"private_get_odr_orders_id", 404, nil, ErrOrderNotFound},
		{"public_get_mth_orderbook_symbol", 404, nil, ErrBadRequest},
		{"private_post_odr_orders", 406, map[string]any{"detail": "insufficent_balance"}, ErrInsufficientFunds},
		{"private_delete_odr_orders_id", 406, map[string]any{"code": "cancel_order_not_allowed"}, ErrInvalidOrder},
		{"private_post_wlt_withdraws_verify_otp_id", 400, map[string]any{"code": "extra_try"}, ErrInvalidOTP},
		{"private_post_odr_orders", 400, map[string]any{"price": []any{"required"}}, ErrInvalidOrder},
		{"private_get_wlt_networks", 406, map[string]any{"detail": "x"}, ErrExchange},
		{"public_get_mkt_tickers", 503, "<html>", ErrExchangeNotAvailable},
		{"public_get_mkt_tickers", 418, nil, ErrExchange},
	}
	for _, c := range cases {
		err := mapError(c.id, c.status, c.body, "")
		if !errors.Is(err, c.want) || !errors.Is(err, ErrBitpin) || err.Status != c.status || err.EndpointID != c.id {
			t.Errorf("%s %d: got %v (%v)", c.id, c.status, err.Kind, err)
		}
	}
	if !errors.Is(mapError("x", 400, map[string]any{"code": "invalid_otp"}, ""), ErrBadRequest) {
		t.Error("InvalidOTP is a BadRequest")
	}
	if errors.Is(mapError("x", 503, nil, ""), ErrExchange) {
		t.Error("network errors are not exchange errors")
	}
	eq(t, mapError("x", 429, map[string]any{"detail": "Expected available in 86398 seconds."}, "").RetryAfter, 86398)
	eq(t, mapError("x", 429, nil, "12").RetryAfter, 12)
	eq(t, mapError("x", 429, nil, "soon").RetryAfter, -1)
	eq(t, mapError("private_post_wlt_withdraws_verify_otp_id", 400, map[string]any{"code": "extra_try"}, "").Code, "extra_try")
	eq(t, mapError("private_post_odr_orders", 406, map[string]any{"detail": "insufficent_balance"}, "").Error(), "406 private_post_odr_orders: insufficent_balance")
	eq(t, mapError("x", 500, nil, "").Error(), "500 x")
	eq(t, len(mapError("x", 418, strings.Repeat("a", 300), "").Error()), len("418 x: ")+200)
	ns := notSupported("editOrder")
	if !errors.Is(ns, ErrNotSupported) || !strings.Contains(ns.Error(), "ویرایش") || ns.Feature != "editOrder" {
		t.Error("notSupported")
	}
	eq(t, ErrInvalidOrder.Error(), "InvalidOrder")
}

func TestBuildRequest(t *testing.T) {
	cfg := must[resolvedConfig](t)(Config{}.resolve())
	req := must[builtRequest](t)(buildRequest(cfg, "private_get_odr_orders", nil, Params{"symbol": "BTC_IRT", "state": []string{"active", "initial"}, "limit": 50, "side": nil, "flag": true, "x": []any{1, "b"}, "d": 1.5}, nil))
	eq(t, req.url, "https://api.bitpin.org/api/v1/odr/orders/")
	eq(t, req.query.Encode(), "d=1.5&flag=true&limit=50&state=active%2Cinitial&symbol=BTC_IRT&x=1%2Cb")
	body := must[builtRequest](t)(buildRequest(cfg, "private_post_odr_orders", nil, nil, Params{"base_amount": decimal.RequireFromString("1E-8"), "price": 3100000000, "stop_price": nil, "f": false, "n": []map[string]any{{"a": 0.1}}, "list": []any{"x"}, "s": []string{"y"}}))
	eq(t, body.body, map[string]any{"base_amount": "0.00000001", "price": "3100000000", "f": false, "n": []any{map[string]any{"a": "0.1"}}, "list": []any{"x"}, "s": []string{"y"}})
	path := must[builtRequest](t)(buildRequest(cfg, "private_delete_odr_orders_identifier_identifier", Params{"identifier": "a b/c"}, nil, nil))
	eq(t, path.url, "https://api.bitpin.org/api/v1/odr/orders/identifier/a%20b%2Fc/")
	if _, err := buildRequest(cfg, "public_get_mth_orderbook_symbol", nil, nil, nil); err == nil || !strings.Contains(err.Error(), `missing path parameter "symbol"`) {
		t.Error(err)
	}
	if _, err := buildRequest(cfg, "nope", nil, nil, nil); err == nil {
		t.Error("unknown endpoint")
	}
}

func TestTokenStores(t *testing.T) {
	ctx := context.Background()
	id := KeyID("MY-API-KEY")
	if len(id) != 16 || strings.Contains(id, "MY-API-KEY") || id != KeyID("MY-API-KEY") || id == KeyID("other") {
		t.Error("KeyID")
	}
	tok := Tokens{"a", "r", 100, 200}
	mem := &MemoryTokenStore{}
	if v, _ := mem.Load(ctx, "k"); v != nil {
		t.Error("empty")
	}
	_ = mem.Save(ctx, "k", tok)
	eq(t, *must[*Tokens](t)(mem.Load(ctx, "k")), tok)
	_ = mem.Clear(ctx, "k")
	dir := filepath.Join(t.TempDir(), "cache")
	fs := FileTokenStore{Dir: dir}
	if err := fs.Save(ctx, "abc", tok); err != nil {
		t.Fatal(err)
	}
	eq(t, *must[*Tokens](t)(FileTokenStore{Dir: dir}.Load(ctx, "abc")), tok)
	if runtime.GOOS != "windows" {
		info, _ := os.Stat(filepath.Join(dir, "abc.json"))
		eq(t, info.Mode().Perm(), os.FileMode(0o600))
		dinfo, _ := os.Stat(dir)
		eq(t, dinfo.Mode().Perm(), os.FileMode(0o700))
	}
	entries, _ := os.ReadDir(dir)
	eq(t, len(entries), 1)
	_ = fs.Clear(ctx, "abc")
	if err := fs.Clear(ctx, "abc"); err != nil {
		t.Error(err)
	}
	if v, _ := fs.Load(ctx, "abc"); v != nil {
		t.Error("cleared")
	}
	_ = os.WriteFile(filepath.Join(dir, "bad.json"), []byte("{not json"), 0o600)
	if v, _ := fs.Load(ctx, "bad"); v != nil {
		t.Error("corrupt")
	}
	for _, f := range []func() error{
		func() error { return fs.Save(ctx, "../x", tok) },
		func() error { _, err := fs.Load(ctx, "../x"); return err },
		func() error { return fs.Clear(ctx, "../x") },
	} {
		if err := f(); err == nil {
			t.Error("path traversal must fail")
		}
	}
	_ = os.Mkdir(filepath.Join(dir, "taken.json"), 0o700)
	if err := fs.Save(ctx, "taken", tok); err == nil {
		t.Error("save over a directory must fail")
	}
	t.Setenv("XDG_CACHE_HOME", "/tmp/xdg")
	eq(t, must[string](t)(FileTokenStore{}.dir()), "/tmp/xdg/bitpin-sdk")
	t.Setenv("XDG_CACHE_HOME", "")
	if d, err := (FileTokenStore{}).dir(); err != nil || !strings.HasSuffix(d, "bitpin-sdk") {
		t.Error(d, err)
	}
}
