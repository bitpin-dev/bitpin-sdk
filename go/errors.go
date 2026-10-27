package bitpin

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// kind is one class of the ccxt error hierarchy. Each kind knows its parent, so
// errors.Is(err, ErrExchange) matches every exchange error.
type kind struct {
	name   string
	parent *kind
}

func (k *kind) Error() string { return k.name }

var (
	// ErrBitpin is the root of every error the SDK returns.
	ErrBitpin = &kind{name: "BitpinError"}
	// ErrExchange: the server answered with an error.
	ErrExchange             = &kind{"ExchangeError", ErrBitpin}
	ErrAuthentication       = &kind{"AuthenticationError", ErrExchange}
	ErrPermissionDenied     = &kind{"PermissionDenied", ErrExchange}
	ErrInsufficientFunds    = &kind{"InsufficientFunds", ErrExchange}
	ErrInvalidOrder         = &kind{"InvalidOrder", ErrExchange}
	ErrOrderNotFound        = &kind{"OrderNotFound", ErrExchange}
	ErrBadRequest           = &kind{"BadRequest", ErrExchange}
	ErrBadSymbol            = &kind{"BadSymbol", ErrBadRequest}
	ErrInvalidOTP           = &kind{"InvalidOTP", ErrBadRequest}
	ErrNotSupported         = &kind{"NotSupported", ErrExchange}
	ErrNetwork              = &kind{"NetworkError", ErrBitpin}
	ErrRateLimitExceeded    = &kind{"RateLimitExceeded", ErrNetwork}
	ErrRequestTimeout       = &kind{"RequestTimeout", ErrNetwork}
	ErrExchangeNotAvailable = &kind{"ExchangeNotAvailable", ErrNetwork}
)

var kindsByName = map[string]*kind{}

func init() {
	for _, k := range []*kind{ErrExchange, ErrAuthentication, ErrPermissionDenied, ErrInsufficientFunds,
		ErrInvalidOrder, ErrOrderNotFound, ErrBadRequest, ErrBadSymbol, ErrInvalidOTP, ErrNotSupported,
		ErrNetwork, ErrRateLimitExceeded, ErrRequestTimeout, ErrExchangeNotAvailable} {
		kindsByName[k.name] = k
	}
}

// Error is every error the SDK returns. Match it with errors.Is against the Err* kinds,
// and read the details with errors.As.
type Error struct {
	Kind       error // one of the Err* kinds
	Message    string
	Status     int    // HTTP status, 0 if the request didn't get a response
	Body       any    // the parsed error body
	EndpointID string // the spec endpoint id
	// RetryAfter is the server's hint in seconds for RateLimitExceeded; negative when absent.
	RetryAfter float64
	// Code is the OTP error code for InvalidOTP: invalid_otp, otp1_already_verified or extra_try.
	Code string
	// Feature is the ccxt capability name for NotSupported.
	Feature string
	cause   error
}

func (e *Error) Error() string { return e.Message }

// Unwrap returns the underlying transport error, if any.
func (e *Error) Unwrap() error { return e.cause }

// Is reports whether the error belongs to target's class or one of its subclasses.
func (e *Error) Is(target error) bool {
	for k, _ := e.Kind.(*kind); k != nil; k = k.parent {
		if target == error(k) {
			return true
		}
	}
	return false
}

func newError(k *kind, format string, args ...any) *Error {
	return &Error{Kind: k, Message: fmt.Sprintf(format, args...), RetryAfter: -1}
}

var retryAfterPattern = regexp.MustCompile(`(?i)available in (\d+(?:\.\d+)?) second`)
var otpCodes = []string{"invalid_otp", "otp1_already_verified", "extra_try"}

func bodyText(body any) string {
	switch b := body.(type) {
	case nil:
		return ""
	case string:
		return b
	default:
		data, _ := json.Marshal(b)
		return string(data)
	}
}

func errorDetail(body any) string {
	if m, ok := body.(map[string]any); ok {
		for _, key := range []string{"detail", "code", "message"} {
			if s, ok := m[key].(string); ok {
				return s
			}
		}
	}
	text := bodyText(body)
	if len(text) > 200 {
		text = text[:200]
	}
	return text
}

// mapError builds the error for an error response, using the rules in the spec.
func mapError(endpointID string, status int, body any, retryAfterHeader string) *Error {
	text := strings.ToLower(bodyText(body))
	name := "ExchangeError"
	for _, rule := range specErrorRules {
		if rule.status != status {
			continue
		}
		if len(rule.paths) > 0 && !anyPrefix(endpointID, rule.paths) {
			continue
		}
		if len(rule.detail) > 0 && !anyContains(text, rule.detail) {
			continue
		}
		name = rule.kind
		break
	}
	message := fmt.Sprintf("%d %s", status, endpointID)
	if detail := errorDetail(body); detail != "" {
		message += ": " + detail
	}
	err := &Error{Kind: kindsByName[name], Message: message, Status: status, Body: body, EndpointID: endpointID, RetryAfter: -1}
	switch name {
	case "RateLimitExceeded":
		if seconds, perr := strconv.ParseFloat(strings.TrimSpace(retryAfterHeader), 64); perr == nil {
			err.RetryAfter = seconds
		} else if m := retryAfterPattern.FindStringSubmatch(bodyText(body)); m != nil {
			err.RetryAfter, _ = strconv.ParseFloat(m[1], 64)
		}
	case "InvalidOTP":
		for _, code := range otpCodes {
			if strings.Contains(text, code) {
				err.Code = code
				break
			}
		}
	}
	return err
}

// notSupported is the error for a ccxt capability Bitpin doesn't offer, in English and Persian.
func notSupported(feature string) *Error {
	msg := specNotSupported[feature]
	err := newError(ErrNotSupported, "%s\n%s", msg[0], msg[1])
	err.Feature = feature
	return err
}

func anyPrefix(s string, prefixes []string) bool {
	for _, p := range prefixes {
		if strings.HasPrefix(s, p) {
			return true
		}
	}
	return false
}

func anyContains(s string, parts []string) bool {
	for _, p := range parts {
		if strings.Contains(s, strings.ToLower(p)) {
			return true
		}
	}
	return false
}
