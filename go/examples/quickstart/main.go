// Read-only tour: markets, a ticker, the order book, and your balance if keys are set.
//
//	go run ./examples/quickstart -symbol BTC/IRT
package main

import (
	"context"
	"flag"
	"fmt"
	"log"

	bitpin "github.com/bitpin-dev/bitpin-sdk/go"
)

func main() {
	symbol := flag.String("symbol", "BTC/IRT", "market")
	flag.Parse()
	ctx := context.Background()
	cfg := bitpin.ConfigFromEnv() // BITPIN_API_KEY, BITPIN_SECRET_KEY, BITPIN_DOMAIN
	client, err := bitpin.New(cfg)
	if err != nil {
		log.Fatal(err)
	}
	markets, err := client.LoadMarkets(ctx, false)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("%d markets\n", len(markets))
	ticker, err := client.FetchTicker(ctx, *symbol)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("%s last %s (24h %s%%)\n", ticker.Symbol, ticker.Last, ticker.Percentage)
	book, err := client.FetchOrderBook(ctx, *symbol, 5)
	if err != nil {
		log.Fatal(err)
	}
	if len(book.Bids) > 0 && len(book.Asks) > 0 {
		fmt.Printf("best bid %s / ask %s\n", book.Bids[0].Price, book.Asks[0].Price)
	}
	if cfg.APIKey == "" {
		fmt.Println("Set BITPIN_API_KEY and BITPIN_SECRET_KEY to see your balance.")
		return
	}
	balance, err := client.FetchBalance(ctx, nil)
	if err != nil {
		log.Fatal(err)
	}
	for code, total := range balance.Total {
		if !total.IsZero() {
			fmt.Printf("%s %s\n", code, total)
		}
	}
}
