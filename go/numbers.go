package bitpin

import (
	"encoding/json"
	"fmt"
	"strconv"

	"github.com/shopspring/decimal"
)

// Decimal is the exact decimal type used for every price and amount.
type Decimal = decimal.Decimal

// toDecimal reads a server or user value. Floats go through their shortest representation,
// so 0.1 stays 0.1. Returns nil for nil and "".
func toDecimal(value any) (*Decimal, error) {
	var d decimal.Decimal
	var err error
	switch v := value.(type) {
	case nil:
		return nil, nil
	case decimal.Decimal:
		d = v
	case *decimal.Decimal:
		if v == nil {
			return nil, nil
		}
		d = *v
	case string:
		if v == "" {
			return nil, nil
		}
		d, err = decimal.NewFromString(v)
	case json.Number:
		d, err = decimal.NewFromString(string(v))
	case float64:
		d, err = decimal.NewFromString(strconv.FormatFloat(v, 'f', -1, 64))
	case float32:
		d, err = decimal.NewFromString(strconv.FormatFloat(float64(v), 'f', -1, 32))
	case int:
		d = decimal.NewFromInt(int64(v))
	case int64:
		d = decimal.NewFromInt(v)
	default:
		return nil, fmt.Errorf("not a number: %v", value)
	}
	if err != nil {
		return nil, fmt.Errorf("not a number: %v", value)
	}
	return &d, nil
}

// formatDecimal is the plain string the API expects: no exponent, no trailing zeros.
func formatDecimal(value any) (string, error) {
	d, err := toDecimal(value)
	if err != nil {
		return "", err
	}
	if d == nil {
		return "", fmt.Errorf("not a number: %v", value)
	}
	return d.String(), nil
}

// dec is a lenient parse for server fields: nil when absent or not a number.
func dec(value any) *Decimal {
	d, err := toDecimal(value)
	if err != nil {
		return nil
	}
	return d
}
