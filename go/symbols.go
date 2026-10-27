package bitpin

import (
	"regexp"
	"strings"
)

var symbolPart = regexp.MustCompile(`^[A-Z0-9]+$`)

func splitSymbol(value, sep string) (string, string, bool) {
	parts := strings.Split(value, sep)
	if len(parts) != 2 || !symbolPart.MatchString(parts[0]) || !symbolPart.MatchString(parts[1]) {
		return "", "", false
	}
	return parts[0], parts[1], true
}

// MarketID converts "btc/irt", "BTC/IRT" or "BTC_IRT" to Bitpin's id "BTC_IRT".
func MarketID(symbol string) (string, error) {
	value := strings.ToUpper(strings.TrimSpace(symbol))
	for _, sep := range []string{"/", "_"} {
		if strings.Contains(value, sep) {
			if base, quote, ok := splitSymbol(value, sep); ok {
				return base + "_" + quote, nil
			}
		}
	}
	return "", newError(ErrBadSymbol, "invalid symbol %q; use 'BASE/QUOTE', e.g. 'BTC/IRT'", symbol)
}

// Symbol converts Bitpin's id "BTC_IRT" to the ccxt symbol "BTC/IRT".
func Symbol(marketID string) (string, error) {
	base, quote, ok := splitSymbol(marketID, "_")
	if !ok {
		return "", newError(ErrBadSymbol, "invalid market id %q", marketID)
	}
	return base + "/" + quote, nil
}

func symbolOrRaw(marketID any) string {
	id, _ := marketID.(string)
	if s, err := Symbol(id); err == nil {
		return s
	}
	return id
}
