package bitpin

import (
	"testing"
)

const tOrder = 1793083530123

func TestParsers(t *testing.T) {
	m := parseMarket(asMap(asList(fixtureBody(t, "public_get_mkt_markets"))[0]))
	eq(t, []any{m.ID, m.Symbol, m.Active, m.Type, m.Precision.Amount.String(), m.Precision.Price.String()}, []any{"BTC_IRT", "BTC/IRT", true, "spot", "0.00000001", "1"})
	sus := parseMarket(asMap(asList(fixtureBody(t, "public_get_mkt_markets"))[2]))
	eq(t, []any{sus.Active, sus.Precision.Price.String()}, []any{false, "0.01"})
	c := parseCurrency(asMap(asList(fixtureBody(t, "public_get_mkt_currencies"))[1]))
	eq(t, []any{c.Code, c.Name, c.Precision.String()}, []any{"BTC", "Bitcoin", "0.00000001"})
	eq(t, parseCurrency(Info{"currency": "X"}).Name, "X")

	tk := parseTicker(asMap(asList(fixtureBody(t, "public_get_mkt_tickers"))[0]))
	eq(t, []any{tk.Symbol, tk.Last.String(), tk.Percentage.String(), *tk.Timestamp, tk.Datetime, tk.BaseVolume == nil}, []any{"BTC/IRT", "3145737420", "-1.58", 1761550530189, "2025-10-27T07:35:30.189Z", true})

	ob := parseOrderBook(Info{"asks": []any{[]any{"3", "1"}, []any{"2", "1"}, []any{"bad"}}, "bids": []any{[]any{"1", "1"}, []any{"1.5", "2"}}}, "BTC/IRT", nil)
	eq(t, []string{ob.Asks[0].Price.String(), ob.Bids[0].Price.String(), ob.Datetime}, []string{"2", "1.5", ""})

	tr := parseTrade(asMap(asList(fixtureBody(t, "public_get_mth_matches_symbol"))[0]), "BTC/IRT")
	eq(t, []any{tr.ID, tr.Side, tr.Amount.String(), *tr.Timestamp}, []any{"73802972_73807087", "buy", "0.002", 1761550530149})
	mt := parseMyTrade(asMap(asList(fixtureBody(t, "private_get_odr_fills"))[0]))
	eq(t, []any{mt.ID, mt.Order, mt.Symbol, mt.Fee.Currency, mt.Fee.Cost.String(), *mt.Timestamp}, []any{"65375307", "535179300", "BTC/IRT", "IRT", "11060", 1793083800500})
	k := parseOHLCV(asMap(asList(fixtureBody(t, "public_get_mkt_candles"))[0]))
	eq(t, []any{k.Timestamp, k.Open.String(), k.High.String(), k.Low.String(), k.Close.String(), k.Volume.String()}, []any{1761550200000, "3100000000", "3120000000", "3090000000", "3110000000", "1.25"})

	o := parseOrder(asMap(fixtureBody(t, "private_post_odr_orders")))
	eq(t, []any{o.ID, o.ClientOrderID, o.Symbol, o.Type, o.Status, *o.Timestamp, o.Remaining.String(), o.Average == nil, o.LastTradeTimestamp == nil}, []any{"535179385", "mm-bid-1", "BTC/IRT", "limit", "open", tOrder, "0.001", true, true})
	filled := parseOrder(asMap(asList(fixtureBody(t, "private_get_odr_orders"))[1]))
	eq(t, []any{filled.Status, filled.Remaining.String(), filled.Average.String()}, []any{"closed", "0", "3160000000"})
	h := parseHistoryOrder(asMap(asList(asMap(fixtureBody(t, "private_get_odr_order_history"))["results"])[0]))
	eq(t, []any{h.Status, *h.Timestamp, *h.LastTradeTimestamp, h.Price == nil}, []any{"closed", 1761460000000, 1761460000500, true})
	eq(t, len(parseBulkOrders(fixtureBody(t, "private_post_odr_orders_bulk"))), 2)
	eq(t, len(parseBulkOrders(asMap(fixtureBody(t, "private_post_odr_orders_bulk"))["orders"])), 2)
	if parseOrder(Info{"id": "1", "symbol": "A_B", "state": "active"}).Remaining != nil {
		t.Error("sparse order")
	}

	base := asMap(fixtureBody(t, "private_post_odr_orders"))
	for _, c := range []struct {
		state, b, db, q, dq, want string
	}{
		{"initial", "1", "0", "10", "0", "open"}, {"closed", "1", "1", "10", "10", "closed"}, {"closed", "1", "0.5", "10", "5", "canceled"},
		{"closed", "", "0.3", "10", "10", "closed"}, {"closed", "", "0.3", "10", "9", "canceled"}, {"closed", "", "0", "", "0", "closed"}, {"weird", "1", "0", "10", "0", "weird"},
	} {
		raw := Info{}
		for k, v := range base {
			raw[k] = v
		}
		raw["state"], raw["base_amount"], raw["dealed_base_amount"], raw["quote_amount"], raw["dealed_quote_amount"] = c.state, c.b, c.db, c.q, c.dq
		if got := parseOrder(raw).Status; got != c.want {
			t.Errorf("%+v: got %s", c, got)
		}
	}

	bal := parseBalance(asList(fixtureBody(t, "private_get_wlt_wallets")))
	eq(t, []string{bal.Currencies["BTC"].Total.String(), bal.Free["IRT"].String()}, []string{"0.0135", "150000000"})
	sum := parseBalance([]any{map[string]any{"asset": "BTC", "balance": "1"}, map[string]any{"asset": "BTC", "balance": "2", "frozen": "1"}})
	eq(t, sum.Total["BTC"].String(), "4")
	fee := parseTradingFee(asMap(asList(fixtureBody(t, "private_get_mkt_commissions"))[0]))
	eq(t, []string{fee.Maker.String(), fee.Taker.String()}, []string{"0.003", "0.0035"})
	eq(t, parseTradingFee(Info{"symbol": "A_B"}).Maker == nil, true)

	dep := parseDeposit(asMap(asList(fixtureBody(t, "private_get_wlt_deposits"))[0]))
	eq(t, []any{dep.ID, dep.Status, dep.Network, *dep.Internal}, []any{"9001", "ok", "TRX", false})
	eq(t, parseDeposit(Info{"id": "1", "state": "waiting", "network": "TRX"}).Status, "pending")
	w := parseWithdrawal(asMap(asList(fixtureBody(t, "private_get_wlt_withdraws"))[0]))
	eq(t, []any{w.ID, w.Status, w.Network, w.Fee.Currency}, []any{"7001", "ok", "TRX", "USDT"})
	eq(t, parseWithdrawal(asMap(asList(fixtureBody(t, "private_get_wlt_withdraws"))[1])).Address, "")
	a := parseDepositAddress(asMap(fixtureBody(t, "private_post_wlt_address")), "TRX")
	eq(t, []string{a.Currency, a.Network, a.Tag}, []string{"USDT", "TRX", ""})
	nets := asList(fixtureBody(t, "private_get_wlt_networks"))
	v2, v1 := parseCurrencyNetwork(asMap(nets[0])), parseCurrencyNetwork(asMap(nets[1]))
	eq(t, []any{v2.Network, v2.Withdraw, v2.AddressPattern, v1.AddressPattern}, []any{"TRX", false, "", "^0x[a-fA-F0-9]{40}$"})
	eq(t, parseNetwork(Info{"code": "X"}).Name, "X")
	bank := parseBankAccount(asMap(asList(fixtureBody(t, "private_get_wlt_account_numbers"))[0]))
	eq(t, []string{bank.ID, bank.Currency, bank.Status}, []string{"123", "IRT", "verified"})
	eq(t, parseBankAccount(Info{"id": 1.0, "currency": "IRT"}).Currency, "IRT")

	eq(t, isoToMs("garbage") == nil, true)
	eq(t, *isoToMs("2026-10-27T10:20:00.5+03:30"), 1793083800500)
	eq(t, *isoToMs("2025-10-19T11:38:27.929164Z"), 1760873907929)
	eq(t, str(2.5), "2.5")
	eq(t, str(true), "true")
	eq(t, tick(nil).String(), "1")
}
