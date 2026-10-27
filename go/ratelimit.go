package bitpin

import (
	"sort"
	"sync"
)

// limiter is a client-side sliding window per bucket. reserve books a send time
// atomically, so concurrent callers queue up behind each other instead of bursting.
type limiter struct {
	mu    sync.Mutex
	rules map[string]RateLimit
	calls map[string][]float64
	clock func() float64
}

func newLimiter(rules map[string]RateLimit, clock func() float64) *limiter {
	l := &limiter{rules: rules, calls: map[string][]float64{}, clock: clock}
	return l
}

func (l *limiter) prune(now float64) {
	for name, list := range l.calls {
		window := l.rules[name].PeriodSeconds()
		cut := sort.SearchFloat64s(list, now-window)
		for cut < len(list) && list[cut] <= now-window {
			cut++
		}
		l.calls[name] = list[cut:]
	}
}

func (l *limiter) earliest(buckets []string, now float64) float64 {
	at := now
	for round := 0; round <= len(buckets); round++ {
		moved := false
		for _, bucket := range buckets {
			rule, ok := l.rules[bucket]
			if !ok {
				continue
			}
			list := l.calls[bucket]
			after := len(list) - sort.Search(len(list), func(i int) bool { return list[i] > at-rule.PeriodSeconds() })
			if after >= rule.Limit {
				if next := list[len(list)-rule.Limit] + rule.PeriodSeconds(); next > at {
					at = next
				}
				moved = true
			}
		}
		if !moved {
			break
		}
	}
	return at
}

// reserve books the next free send time for buckets and returns the seconds to wait.
func (l *limiter) reserve(buckets []string) float64 {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := l.clock()
	l.prune(now)
	at := l.earliest(buckets, now)
	for _, bucket := range buckets {
		if _, ok := l.rules[bucket]; ok {
			list := l.calls[bucket]
			i := sort.SearchFloat64s(list, at)
			for i < len(list) && list[i] <= at {
				i++
			}
			list = append(list, 0)
			copy(list[i+1:], list[i:])
			list[i] = at
			l.calls[bucket] = list
		}
	}
	return at - now
}
