// A minimal two-sided quoting loop. A starting point, not a strategy.
// Each round: read the book, quote a bid and an ask around the mid at -spread-bps, replace the
// previous quotes. Whatever ends the loop, the last quotes are cancelled. Dry-run unless -live.
//
//	go run ./examples/marketmaker -symbol USDT/IRT -size 10 [-live]
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"time"

	bitpin "github.com/bitpin-dev/bitpin-sdk/go"
	"github.com/shopspring/decimal"
)

func quotes(mid, spreadBps, tick decimal.Decimal) (decimal.Decimal, decimal.Decimal) {
	half := mid.Mul(spreadBps).Div(decimal.NewFromInt(20000))
	bid := mid.Sub(half).Div(tick).Floor().Mul(tick)
	ask := mid.Add(half).Div(tick).Ceil().Mul(tick)
	return bid, ask
}

func main() {
	symbol := flag.String("symbol", "USDT/IRT", "market")
	size := flag.String("size", "", "amount per quote, in the base currency")
	spread := flag.String("spread-bps", "20", "spread in basis points")
	interval := flag.Duration("interval", 5*time.Second, "time between rounds")
	iterations := flag.Int("iterations", 10, "rounds")
	live := flag.Bool("live", false, "really place orders (default: dry-run)")
	flag.Parse()
	if *size == "" {
		log.Fatal("-size is required")
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	client, err := bitpin.New(bitpin.ConfigFromEnv())
	if err != nil {
		log.Fatal(err)
	}
	if _, err := client.LoadMarkets(ctx, false); err != nil {
		log.Fatal(err)
	}
	market, err := client.Market(*symbol)
	if err != nil {
		log.Fatal(err)
	}
	spreadBps := decimal.RequireFromString(*spread)
	buf := make([]byte, 4)
	_, _ = rand.Read(buf)
	run := "mm-" + hex.EncodeToString(buf) // unique per run, so ids never collide across restarts
	var resting []string
	defer func() {
		if *live && len(resting) > 0 { // never leave quotes resting unattended
			if _, err := client.CancelOrders(context.Background(), nil, resting); err != nil {
				log.Print(err)
			}
		}
	}()
	for i := 0; i < *iterations && ctx.Err() == nil; i++ {
		book, err := client.FetchOrderBook(ctx, *symbol, 1)
		if err != nil {
			log.Print(err)
			return
		}
		if len(book.Bids) == 0 || len(book.Asks) == 0 {
			fmt.Println("empty book, not quoting")
		} else {
			mid := book.Bids[0].Price.Add(book.Asks[0].Price).Div(decimal.NewFromInt(2))
			bid, ask := quotes(mid, spreadBps, market.Precision.Price)
			ids := []string{fmt.Sprintf("%s-%d-bid", run, i), fmt.Sprintf("%s-%d-ask", run, i)}
			orders := []bitpin.OrderRequest{
				{Symbol: *symbol, Type: "limit", Side: "buy", Amount: *size, Price: bid, Params: bitpin.Params{"clientOrderId": ids[0]}},
				{Symbol: *symbol, Type: "limit", Side: "sell", Amount: *size, Price: ask, Params: bitpin.Params{"clientOrderId": ids[1]}},
			}
			if !*live {
				fmt.Printf("DRY-RUN cancel %v, place bid %s / ask %s (pass -live to send)\n", resting, bid, ask)
				resting = ids
			} else {
				if len(resting) > 0 {
					if _, err := client.CancelOrders(ctx, nil, resting); err != nil {
						log.Print(err)
						return
					}
					resting = nil
				}
				if _, err := client.CreateOrders(ctx, orders); err != nil {
					log.Print(err)
					return
				}
				resting = ids
			}
		}
		select {
		case <-ctx.Done():
		case <-time.After(*interval):
		}
	}
}
