package bitpin

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math"
	"strings"
)

// Tokens is a cached access/refresh pair with their expiry times (Unix seconds).
type Tokens struct {
	Access     string  `json:"access"`
	Refresh    string  `json:"refresh"`
	AccessExp  float64 `json:"accessExp"`
	RefreshExp float64 `json:"refreshExp"`
}

// GoString hides the token values.
func (t Tokens) GoString() string {
	return fmt.Sprintf("Tokens{AccessExp: %v, RefreshExp: %v}", t.AccessExp, t.RefreshExp)
}

// String hides the token values.
func (t Tokens) String() string { return t.GoString() }

// jwtExp reads a JWT's exp claim without verifying it; ok is false when unreadable.
func jwtExp(token string) (float64, bool) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return 0, false
	}
	payload, err := base64.RawURLEncoding.DecodeString(strings.TrimRight(parts[1], "="))
	if err != nil {
		return 0, false
	}
	var claims map[string]any
	if json.Unmarshal(payload, &claims) != nil {
		return 0, false
	}
	exp, ok := claims["exp"].(float64)
	if !ok || math.IsNaN(exp) || math.IsInf(exp, 0) {
		return 0, false
	}
	return exp, true
}

type tokenAction int

const (
	actionOK tokenAction = iota
	actionRefresh
	actionAuthenticate
)

// tokenState decides between using, refreshing and re-authenticating. Not safe for
// concurrent use on its own; the client holds its auth mutex.
type tokenState struct {
	tokens *Tokens
	clock  func() float64
}

func (s *tokenState) action() tokenAction {
	if s.tokens == nil {
		return actionAuthenticate
	}
	now := s.clock()
	if now >= s.tokens.RefreshExp {
		return actionAuthenticate
	}
	if now >= s.tokens.AccessExp-float64(specConstants["token_refresh_margin_seconds"]) {
		return actionRefresh
	}
	return actionOK
}

func (s *tokenState) exp(token, ttl string) float64 {
	if exp, ok := jwtExp(token); ok {
		return exp
	}
	return s.clock() + float64(specConstants[ttl])
}

func (s *tokenState) setTokens(access, refresh string) Tokens {
	s.tokens = &Tokens{
		Access: access, Refresh: refresh,
		AccessExp:  s.exp(access, "access_token_ttl_seconds"),
		RefreshExp: s.exp(refresh, "refresh_token_ttl_seconds"),
	}
	return *s.tokens
}

func (s *tokenState) setAccess(access string) Tokens {
	s.tokens.Access = access
	s.tokens.AccessExp = s.exp(access, "access_token_ttl_seconds")
	return *s.tokens
}

// expireAccess makes the next call refresh, but only if token is still the current one.
func (s *tokenState) expireAccess(token string) {
	if s.tokens != nil && s.tokens.Access == token {
		s.tokens.AccessExp = 0
	}
}
