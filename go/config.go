package bitpin

import (
	"fmt"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Domain is the domain the API is served on: DomainOrg (default), DomainIR or DomainMarket.
// REST and WebSocket switch together.
type Domain string

const (
	DomainOrg    Domain = "org"
	DomainIR     Domain = "ir"
	DomainMarket Domain = "market"
)

type domainURLs struct{ rest, ws string }

var periodSeconds = map[string]float64{"sec": 1, "min": 60, "hour": 3600, "day": 86400}

// RateLimit is at most Limit requests per Period ("sec", "min", "hour" or "day").
type RateLimit struct {
	Limit  int
	Period string
}

// PeriodSeconds is the length of the window in seconds.
func (r RateLimit) PeriodSeconds() float64 { return periodSeconds[r.Period] }

var rateLimitPattern = regexp.MustCompile(`^(\d+)/(sec|min|hour|day)$`)

// ParseRateLimit reads "10800/min".
func ParseRateLimit(s string) (RateLimit, error) {
	m := rateLimitPattern.FindStringSubmatch(s)
	if m == nil {
		return RateLimit{}, fmt.Errorf("invalid rate limit %q; use '<count>/<sec|min|hour|day>', e.g. '60/min'", s)
	}
	limit, _ := strconv.Atoi(m[1])
	if limit < 1 {
		return RateLimit{}, fmt.Errorf("invalid rate limit %q; the count must be at least 1", s)
	}
	return RateLimit{Limit: limit, Period: m[2]}, nil
}

// Config holds the client settings. The zero value works for public endpoints.
type Config struct {
	APIKey    string
	SecretKey string
	// Domain picks the API domain; empty means DomainOrg.
	Domain Domain
	// RestURL and WSURL override the domain's URLs (e.g. a proxy).
	RestURL string
	WSURL   string
	// Timeout per request; zero means 10 s.
	Timeout time.Duration
	// MaxRetries for idempotent requests only; nil means 3. Use bitpin.Int(0) to disable.
	MaxRetries *int
	// DisableRateLimit turns the client-side limiter off; the server still enforces its limits.
	DisableRateLimit bool
	// RateLimits overrides server defaults per bucket, e.g. {"orderbook": "10800/min"}.
	RateLimits map[string]string
	UserAgent  string
	// TokenStore caches tokens; nil means in memory. See FileTokenStore.
	TokenStore TokenStore
	// HTTPClient sends requests; nil means a client with Timeout.
	HTTPClient *http.Client
	// Clock and Sleep exist for tests.
	Clock func() time.Time
	Sleep func(d time.Duration) <-chan time.Time
	// WSTransport replaces the Centrifugo connection (tests).
	WSTransport TransportFactory
}

// Int returns a pointer to n, for Config.MaxRetries.
func Int(n int) *int { return &n }

// ConfigFromEnv reads BITPIN_API_KEY, BITPIN_SECRET_KEY and BITPIN_DOMAIN.
func ConfigFromEnv() Config {
	return Config{
		APIKey:    os.Getenv("BITPIN_API_KEY"),
		SecretKey: os.Getenv("BITPIN_SECRET_KEY"),
		Domain:    Domain(os.Getenv("BITPIN_DOMAIN")),
	}
}

type resolvedConfig struct {
	Config
	rateLimits map[string]RateLimit
	maxRetries int
}

func (c Config) resolve() (resolvedConfig, error) {
	r := resolvedConfig{Config: c, rateLimits: map[string]RateLimit{}}
	if r.Domain == "" {
		r.Domain = defaultDomain
	}
	urls, ok := specDomains[r.Domain]
	if !ok {
		names := make([]string, 0, len(specDomains))
		for name := range specDomains {
			names = append(names, string(name))
		}
		sort.Strings(names)
		return r, fmt.Errorf("unknown domain %q; use one of: %s", r.Domain, strings.Join(names, ", "))
	}
	if r.RestURL == "" {
		r.RestURL = urls.rest
	}
	if r.WSURL == "" {
		r.WSURL = urls.ws
	}
	if r.Timeout == 0 {
		r.Timeout = 10 * time.Second
	}
	r.maxRetries = 3
	if c.MaxRetries != nil {
		if *c.MaxRetries < 0 {
			return r, fmt.Errorf("MaxRetries must be >= 0")
		}
		r.maxRetries = *c.MaxRetries
	}
	for name, rule := range specRateLimits {
		r.rateLimits[name] = rule
	}
	for name, value := range c.RateLimits {
		if _, known := specRateLimits[name]; !known {
			return r, fmt.Errorf("unknown rate-limit bucket %q", name)
		}
		rule, err := ParseRateLimit(value)
		if err != nil {
			return r, err
		}
		r.rateLimits[name] = rule
	}
	if r.Clock == nil {
		r.Clock = time.Now
	}
	if r.Sleep == nil {
		r.Sleep = time.After
	}
	return r, nil
}

func (c resolvedConfig) hasCredentials() bool { return c.APIKey != "" && c.SecretKey != "" }

// String hides the credentials.
func (c Config) String() string {
	mask := func(s string) string {
		if s == "" {
			return `""`
		}
		return `"***"`
	}
	return fmt.Sprintf("Config{APIKey: %s, SecretKey: %s, Domain: %q, RestURL: %q}", mask(c.APIKey), mask(c.SecretKey), c.Domain, c.RestURL)
}

// GoString hides the credentials in %#v too.
func (c Config) GoString() string { return c.String() }
