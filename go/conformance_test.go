package bitpin

// Every SDK must parse the shared fixtures into the same result as the Python reference
// (fixtures/expected.json, written by scripts/gen_expected.py).

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

type conformanceCase struct {
	Parser  string `json:"parser"`
	Fixture string `json:"fixture"`
	Path    []any  `json:"path"`
	Args    []any  `json:"args"`
	Output  any    `json:"output"`
}

var conformanceParsers = map[string]func(row any, args []any) any{
	"parse_market":           func(r any, _ []any) any { return parseMarket(asMap(r)) },
	"parse_currency":         func(r any, _ []any) any { return parseCurrency(asMap(r)) },
	"parse_ticker":           func(r any, _ []any) any { return parseTicker(asMap(r)) },
	"parse_order_book":       func(r any, a []any) any { return parseOrderBook(asMap(r), a[0].(string), nil) },
	"parse_trade":            func(r any, a []any) any { return parseTrade(asMap(r), a[0].(string)) },
	"parse_my_trade":         func(r any, _ []any) any { return parseMyTrade(asMap(r)) },
	"parse_ohlcv":            func(r any, _ []any) any { return parseOHLCV(asMap(r)) },
	"parse_order":            func(r any, _ []any) any { return parseOrder(asMap(r)) },
	"parse_history_order":    func(r any, _ []any) any { return parseHistoryOrder(asMap(r)) },
	"parse_bulk_orders":      func(r any, _ []any) any { return parseBulkOrders(r) },
	"parse_balance":          func(r any, _ []any) any { return parseBalance(asList(r)) },
	"parse_trading_fee":      func(r any, _ []any) any { return parseTradingFee(asMap(r)) },
	"parse_deposit":          func(r any, _ []any) any { return parseDeposit(asMap(r)) },
	"parse_withdrawal":       func(r any, _ []any) any { return parseWithdrawal(asMap(r)) },
	"parse_deposit_address":  func(r any, a []any) any { return parseDepositAddress(asMap(r), a[0].(string)) },
	"parse_currency_network": func(r any, _ []any) any { return parseCurrencyNetwork(asMap(r)) },
	"parse_network":          func(r any, _ []any) any { return parseNetwork(asMap(r)) },
	"parse_bank_account":     func(r any, _ []any) any { return parseBankAccount(asMap(r)) },
}

// shape converts Go's typed results to the reference's JSON shape.
func shape(v any) any {
	switch t := v.(type) {
	case OrderBook:
		levels := func(ls []PriceLevel) []any {
			out := []any{}
			for _, l := range ls {
				out = append(out, []any{l.Price.String(), l.Amount.String()})
			}
			return out
		}
		return map[string]any{"symbol": t.Symbol, "bids": levels(t.Bids), "asks": levels(t.Asks), "timestamp": t.Timestamp, "datetime": t.Datetime}
	case OHLCV:
		s := func(d *Decimal) any {
			if d == nil {
				return nil
			}
			return d.String()
		}
		return []any{t.Timestamp, s(t.Open), s(t.High), s(t.Low), s(t.Close), s(t.Volume)}
	case Balances:
		out := map[string]any{"free": t.Free, "used": t.Used, "total": t.Total}
		for code, e := range t.Currencies {
			out[code] = e
		}
		return out
	}
	return v
}

func toJSONTree(v any) any {
	data, _ := json.Marshal(shape(v))
	var out any
	_ = json.Unmarshal(data, &out)
	return out
}

func normKey(k string) string { return strings.ToLower(strings.ReplaceAll(k, "_", "")) }

func isEmptyValue(v any) bool {
	switch t := v.(type) {
	case nil:
		return true
	case string:
		return t == ""
	case []any:
		return len(t) == 0
	}
	return false
}

func compareTree(want, got any, path string, problems *[]string) {
	if isEmptyValue(want) {
		if !isEmptyValue(got) {
			*problems = append(*problems, fmt.Sprintf("%s: expected empty, got %v", path, got))
		}
		return
	}
	switch w := want.(type) {
	case []any:
		g, ok := got.([]any)
		if !ok || len(g) != len(w) {
			*problems = append(*problems, fmt.Sprintf("%s: expected %d items, got %v", path, len(w), got))
			return
		}
		for i := range w {
			compareTree(w[i], g[i], fmt.Sprintf("%s[%d]", path, i), problems)
		}
	case map[string]any:
		actual := map[string]any{}
		if g, ok := got.(map[string]any); ok {
			for k, v := range g {
				if normKey(k) != "info" {
					actual[normKey(k)] = v
				}
			}
		}
		keys := make([]string, 0, len(w))
		for k := range w {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			compareTree(w[k], actual[normKey(k)], path+"."+k, problems)
		}
	default:
		if fmt.Sprint(want) != fmt.Sprint(got) {
			*problems = append(*problems, fmt.Sprintf("%s: expected %v, got %v", path, want, got))
		}
	}
}

func TestConformanceWithPythonReference(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "fixtures", "expected.json"))
	if err != nil {
		t.Fatal(err)
	}
	var cases map[string]conformanceCase
	if err := json.Unmarshal(data, &cases); err != nil {
		t.Fatal(err)
	}
	seen := map[string]bool{}
	for name, c := range cases {
		t.Run(name, func(t *testing.T) {
			parser, ok := conformanceParsers[c.Parser]
			if !ok {
				t.Fatalf("no Go parser for %s", c.Parser)
			}
			seen[c.Parser] = true
			row := fixtureBody(t, c.Fixture)
			for _, step := range c.Path {
				switch s := step.(type) {
				case float64:
					row = asList(row)[int(s)]
				case string:
					row = asMap(row)[s]
				}
			}
			var problems []string
			compareTree(c.Output, toJSONTree(parser(row, c.Args)), "$", &problems)
			if len(problems) > 0 {
				t.Errorf("%s", strings.Join(problems, "\n"))
			}
		})
	}
	if len(seen) != len(conformanceParsers) {
		t.Errorf("expected.json covers %d of %d parsers", len(seen), len(conformanceParsers))
	}
}
