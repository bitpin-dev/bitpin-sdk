package bitpin

import (
	"encoding/json"
	"fmt"
	"sort"
	"time"

	"github.com/shopspring/decimal"
)

var hundred = decimal.NewFromInt(100)

func str(v any) string {
	switch s := v.(type) {
	case nil:
		return ""
	case string:
		return s
	case float64:
		return decimal.NewFromFloat(s).String()
	case json.Number:
		return s.String()
	default:
		return fmt.Sprint(s)
	}
}

func truthy(v any) bool { b, _ := v.(bool); return b }

func asMap(v any) map[string]any { m, _ := v.(map[string]any); return m }

func asList(v any) []any { l, _ := v.([]any); return l }

// isoToMs reads "2026-10-27T10:15:30.123456+03:30" or "...Z" as Unix milliseconds.
func isoToMs(v any) *int64 {
	s, ok := v.(string)
	if !ok || s == "" {
		return nil
	}
	t, err := time.Parse(time.RFC3339Nano, s)
	if err != nil {
		return nil
	}
	ms := t.UnixMilli()
	return &ms
}

func secondsToMs(v any) *int64 {
	d := dec(v)
	if d == nil {
		return nil
	}
	ms := d.Mul(decimal.NewFromInt(1000)).Floor().IntPart()
	return &ms
}

func msToISO(ms *int64) string {
	if ms == nil {
		return ""
	}
	return time.UnixMilli(*ms).UTC().Format("2006-01-02T15:04:05.000Z")
}

func ratioToPercent(v any) *Decimal {
	if d := dec(v); d != nil {
		p := d.Mul(hundred)
		return &p
	}
	return nil
}

func tick(places any) Decimal {
	n := dec(places)
	if n == nil {
		return decimal.NewFromInt(1)
	}
	return decimal.New(1, -int32(n.IntPart()))
}

func positive(d *Decimal) *Decimal {
	if d != nil && d.IsPositive() {
		return d
	}
	return nil
}

func parseMarket(raw Info) Market {
	base, quote := str(raw["base"]), str(raw["quote"])
	m := Market{
		ID: str(raw["symbol"]), Symbol: base + "/" + quote, Base: base, Quote: quote, BaseID: base, QuoteID: quote,
		Active: truthy(raw["tradable"]) && !truthy(raw["suspended"]), Type: "spot", Spot: true, Info: raw,
	}
	m.Precision.Amount = tick(raw["base_amount_precision"])
	m.Precision.Price = tick(raw["price_precision"])
	m.Precision.Cost = tick(raw["quote_amount_precision"])
	return m
}

func parseCurrency(raw Info) Currency {
	code := str(raw["currency"])
	name := str(raw["name"])
	if name == "" {
		name = code
	}
	return Currency{ID: code, Code: code, Name: name, Active: truthy(raw["tradable"]), Precision: tick(raw["precision"]), Info: raw}
}

func parseTicker(raw Info) Ticker {
	ts := secondsToMs(raw["timestamp"])
	last := dec(raw["price"])
	return Ticker{
		Symbol: symbolOrRaw(raw["symbol"]), Timestamp: ts, Datetime: msToISO(ts),
		High: dec(raw["high"]), Low: dec(raw["low"]), Last: last, Close: last,
		Percentage: ratioToPercent(raw["daily_change_price"]), Average: dec(raw["mean"]),
		BaseVolume: dec(raw["base_volume"]), QuoteVolume: dec(raw["quote_volume"]), Info: raw,
	}
}

func levels(rows any, descending bool) []PriceLevel {
	out := []PriceLevel{}
	for _, row := range asList(rows) {
		pair := asList(row)
		if len(pair) < 2 {
			continue
		}
		p, a := dec(pair[0]), dec(pair[1])
		if p != nil && a != nil {
			out = append(out, PriceLevel{Price: *p, Amount: *a})
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		if descending {
			return out[i].Price.GreaterThan(out[j].Price)
		}
		return out[i].Price.LessThan(out[j].Price)
	})
	return out
}

func parseOrderBook(raw Info, symbol string, ts *int64) OrderBook {
	return OrderBook{Symbol: symbol, Bids: levels(raw["bids"], true), Asks: levels(raw["asks"], false), Timestamp: ts, Datetime: msToISO(ts)}
}

func parseTrade(raw Info, symbol string) Trade {
	ts := secondsToMs(raw["time"])
	return Trade{ID: str(raw["id"]), Symbol: symbol, Side: str(raw["side"]), Timestamp: ts, Datetime: msToISO(ts),
		Price: dec(raw["price"]), Amount: dec(raw["base_amount"]), Cost: dec(raw["quote_amount"]), Info: raw}
}

func parseMyTrade(raw Info) Trade {
	ts := isoToMs(raw["created_at"])
	return Trade{ID: str(raw["id"]), Order: str(raw["order_id"]), Symbol: symbolOrRaw(raw["symbol"]), Side: str(raw["side"]),
		Timestamp: ts, Datetime: msToISO(ts), Price: dec(raw["price"]), Amount: dec(raw["base_amount"]), Cost: dec(raw["quote_amount"]),
		Fee: &Fee{Cost: dec(raw["commission"]), Currency: str(raw["commission_currency"])}, Info: raw}
}

func parseOHLCV(raw Info) OHLCV {
	var ts int64
	if ms := secondsToMs(raw["ts"]); ms != nil {
		ts = *ms
	}
	return OHLCV{Timestamp: ts, Open: dec(raw["open"]), High: dec(raw["high"]), Low: dec(raw["low"]), Close: dec(raw["close"]), Volume: dec(raw["volume"])}
}

func orderStatus(raw Info) string {
	state := str(raw["state"])
	switch state {
	case "initial", "active":
		return "open"
	case "closed":
	default:
		return state
	}
	zero := decimal.Zero
	or0 := func(d *Decimal) Decimal {
		if d == nil {
			return zero
		}
		return *d
	}
	if base := dec(raw["base_amount"]); base != nil && base.IsPositive() {
		if or0(dec(raw["dealed_base_amount"])).GreaterThanOrEqual(*base) {
			return "closed"
		}
		return "canceled"
	}
	if quote := dec(raw["quote_amount"]); quote != nil && quote.IsPositive() {
		if or0(dec(raw["dealed_quote_amount"])).GreaterThanOrEqual(*quote) {
			return "closed"
		}
		return "canceled"
	}
	return "closed"
}

func buildOrder(raw Info, ts, closed *int64, status string) Order {
	amount, filled := dec(raw["base_amount"]), dec(raw["dealed_base_amount"])
	var remaining *Decimal
	if amount != nil {
		r := *amount
		if filled != nil {
			r = r.Sub(*filled)
		}
		if r.IsNegative() {
			r = decimal.Zero
		}
		remaining = &r
	}
	var lastTrade *int64
	if filled != nil && !filled.IsZero() {
		lastTrade = closed
	}
	stop := dec(raw["stop_price"])
	return Order{
		ID: str(raw["id"]), ClientOrderID: str(raw["identifier"]), Symbol: symbolOrRaw(raw["symbol"]),
		Type: str(raw["type"]), Side: str(raw["side"]), Status: status, Timestamp: ts, Datetime: msToISO(ts),
		LastTradeTimestamp: lastTrade, Price: positive(dec(raw["price"])), StopPrice: stop, TriggerPrice: stop,
		TakeProfitPrice: dec(raw["oco_target_price"]), Average: positive(dec(raw["average_price"])),
		Amount: amount, Cost: dec(raw["dealed_quote_amount"]), Filled: filled, Remaining: remaining,
		Fee: Fee{Cost: dec(raw["commission"])}, Info: raw,
	}
}

func parseOrder(raw Info) Order {
	return buildOrder(raw, isoToMs(raw["created_at"]), isoToMs(raw["closed_at"]), orderStatus(raw))
}

// parseHistoryOrder: order-history rows are always closed and use Unix-millisecond times.
func parseHistoryOrder(raw Info) Order {
	ms := func(v any) *int64 {
		if d := dec(v); d != nil {
			n := d.IntPart()
			return &n
		}
		return nil
	}
	closed := Info{}
	for k, v := range raw {
		closed[k] = v
	}
	closed["state"] = "closed"
	return buildOrder(raw, ms(raw["created_at"]), ms(raw["closed_at"]), orderStatus(closed))
}

// parseBulkOrders accepts {"orders": [...]} and a bare list.
func parseBulkOrders(raw any) []Order {
	rows := asList(raw)
	if rows == nil {
		rows = asList(asMap(raw)["orders"])
	}
	out := make([]Order, 0, len(rows))
	for _, r := range rows {
		out = append(out, parseOrder(asMap(r)))
	}
	return out
}

func parseBalance(rows []any) Balances {
	b := Balances{Currencies: map[string]BalanceEntry{}, Free: map[string]Decimal{}, Used: map[string]Decimal{}, Total: map[string]Decimal{}}
	for _, item := range rows {
		row := asMap(item)
		code := str(row["asset"])
		free, used := b.Free[code], b.Used[code]
		if d := dec(row["balance"]); d != nil {
			free = free.Add(*d)
		}
		if d := dec(row["frozen"]); d != nil {
			used = used.Add(*d)
		}
		b.Free[code], b.Used[code], b.Total[code] = free, used, free.Add(used)
		b.Currencies[code] = BalanceEntry{Free: free, Used: used, Total: free.Add(used)}
		b.Info = append(b.Info, row)
	}
	return b
}

// parseTradingFee converts Bitpin's percents (0.3 = 0.3 %) to ccxt ratios (0.003).
func parseTradingFee(raw Info) TradingFee {
	div := func(d *Decimal) *Decimal {
		if d == nil {
			return nil
		}
		r := d.Div(hundred)
		return &r
	}
	return TradingFee{Symbol: symbolOrRaw(raw["symbol"]), Maker: div(dec(raw["maker"])), Taker: div(dec(raw["taker"])), Info: raw}
}

var txStatus = map[string]string{"succeed": "ok", "failed": "failed", "canceled": "canceled"}

func status(state any) string {
	if s, ok := txStatus[str(state)]; ok {
		return s
	}
	return "pending"
}

func boolPtr(v any) *bool {
	if b, ok := v.(bool); ok {
		return &b
	}
	return nil
}

func networkCode(v any) string {
	if m := asMap(v); m != nil {
		return str(m["code"])
	}
	return str(v)
}

func parseDeposit(raw Info) Transaction {
	ts := isoToMs(raw["created_at"])
	return Transaction{ID: str(raw["id"]), TxID: str(raw["tx_hash"]), Timestamp: ts, Datetime: msToISO(ts),
		Network: networkCode(raw["network"]), Type: "deposit", Amount: dec(raw["amount"]), Currency: str(raw["currency"]),
		Status: status(raw["state"]), Internal: boolPtr(raw["internal"]), Comment: str(raw["description"]), Info: raw}
}

func parseWithdrawal(raw Info) Transaction {
	ts := isoToMs(raw["created_at"])
	crypto := asMap(raw["crypto_details"])
	currency := str(raw["currency"])
	return Transaction{ID: str(raw["id"]), TxID: str(crypto["tx_hash"]), Timestamp: ts, Datetime: msToISO(ts),
		Network: str(crypto["network"]), Address: str(crypto["address"]), Tag: str(crypto["memo"]), Type: "withdrawal",
		Amount: dec(raw["amount"]), Currency: currency, Status: status(raw["state"]), Updated: isoToMs(raw["closed_at"]),
		Fee: &Fee{Cost: dec(raw["commission"]), Currency: currency}, Internal: boolPtr(raw["internal"]),
		Comment: str(raw["description"]), Info: raw}
}

func parseDepositAddress(raw Info, network string) DepositAddress {
	return DepositAddress{Currency: str(raw["currency"]), Network: network, Address: str(raw["address"]), Tag: str(raw["memo"]), Info: raw}
}

func parseNetwork(raw Info) Network {
	code := str(raw["code"])
	name := str(raw["title"])
	if name == "" {
		name = code
	}
	return Network{ID: code, Network: code, Name: name, Deposit: truthy(raw["can_deposit"]), Withdraw: truthy(raw["can_withdraw"]),
		AddressPattern: str(raw["address_pattern"]), Info: raw}
}

// parseCurrencyNetwork accepts the v1 and v2 shapes of a currency-networks row.
func parseCurrencyNetwork(raw Info) Network {
	n := parseNetwork(asMap(raw["network"]))
	n.Deposit = n.Deposit && !truthy(raw["deposit_under_maintenance"])
	n.Withdraw = n.Withdraw && !truthy(raw["withdraw_under_maintenance"])
	n.Info = raw
	return n
}

func parseBankAccount(raw Info) BankAccount {
	currency := str(raw["currency"])
	if m := asMap(raw["currency"]); m != nil {
		currency = str(m["currency"])
	}
	return BankAccount{ID: str(raw["id"]), Currency: currency, IBAN: str(raw["iban"]), Card: str(raw["card"]), Status: str(raw["state"]), Info: raw}
}
