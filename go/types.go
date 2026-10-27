package bitpin

// Result types use ccxt's field names. Nullable numbers are *Decimal; Info holds the raw response.

type Info = map[string]any

// Params are extra request parameters, as in ccxt.
type Params = map[string]any

type MinMax struct{ Min, Max *Decimal }

type Market struct {
	ID, Symbol, Base, Quote, BaseID, QuoteID     string
	Active                                       bool
	Type                                         string // "spot"
	Spot, Margin, Swap, Future, Option, Contract bool
	Precision                                    struct{ Amount, Price, Cost Decimal }
	Limits                                       struct{ Amount, Price, Cost MinMax }
	Info                                         Info
}

type Currency struct {
	ID, Code, Name string
	Active         bool
	Precision      Decimal
	Info           Info
}

type Ticker struct {
	Symbol                                         string
	Timestamp                                      *int64
	Datetime                                       string
	High, Low, Bid, Ask, Last, Close, Open, Change *Decimal
	Percentage, Average, BaseVolume, QuoteVolume   *Decimal
	Info                                           Info
}

// PriceLevel is one [price, amount] row of an order book.
type PriceLevel struct{ Price, Amount Decimal }

type OrderBook struct {
	Symbol    string
	Bids      []PriceLevel
	Asks      []PriceLevel
	Timestamp *int64
	Datetime  string
}

type Fee struct {
	Cost     *Decimal
	Currency string
}

type Trade struct {
	ID, Order, Symbol, Side string
	Timestamp               *int64
	Datetime                string
	Price, Amount, Cost     *Decimal
	Fee                     *Fee
	Info                    Info
}

type Order struct {
	ID, ClientOrderID, Symbol, Type, Side, Status   string
	Timestamp, LastTradeTimestamp                   *int64
	Datetime                                        string
	Price, StopPrice, TriggerPrice, TakeProfitPrice *Decimal
	Average, Amount, Cost, Filled, Remaining        *Decimal
	Fee                                             Fee
	Info                                            Info
}

type BalanceEntry struct{ Free, Used, Total Decimal }

// Balances is ccxt's balance structure: per currency, plus Free/Used/Total maps.
type Balances struct {
	Currencies        map[string]BalanceEntry
	Free, Used, Total map[string]Decimal
	Info              []Info
}

type TradingFee struct {
	Symbol       string
	Maker, Taker *Decimal // ratios: 0.003 = 0.3 %
	// Percentage and TierBased are ccxt's flags: fees are ratios and depend on your tier.
	Percentage, TierBased bool
	Info                  Info
}

type Transaction struct {
	ID, TxID, Network, Address, AddressTo, Tag, Currency, Status, Comment string
	Type                                                                  string // "deposit" or "withdrawal"
	Timestamp, Updated                                                    *int64
	Datetime                                                              string
	Amount                                                                *Decimal
	Fee                                                                   *Fee
	Internal                                                              *bool
	Info                                                                  Info
}

type DepositAddress struct {
	Currency, Network, Address, Tag string
	Info                            Info
}

type Network struct {
	ID, Network, Name, AddressPattern string
	Deposit, Withdraw                 bool
	Info                              Info
}

type BankAccount struct {
	ID, Currency, IBAN, Card, Status string
	Info                             Info
}

type CancelResult struct {
	Canceled, NotCanceled []string
	Info                  Info
}

// OHLCV is one candle: Timestamp in ms, then open, high, low, close and volume.
type OHLCV struct {
	Timestamp                      int64
	Open, High, Low, Close, Volume *Decimal
}

// OrderRequest is one order of CreateOrders.
type OrderRequest struct {
	Symbol, Type, Side string
	Amount, Price      any // Decimal, string or number; nil when not needed
	Params             Params
}
