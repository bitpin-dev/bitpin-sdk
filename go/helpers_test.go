package bitpin

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

const testNow = 4_000_000_000 // seconds; before the fixture tokens expire

func fixture(t testing.TB, endpointID string) (int, any) {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "fixtures", endpointID+".json"))
	if err != nil {
		t.Fatal(err)
	}
	var f struct {
		Status int `json:"status"`
		Body   any `json:"body"`
	}
	if err := json.Unmarshal(data, &f); err != nil {
		t.Fatal(err)
	}
	return f.Status, normalizeNumbers(f.Body)
}

func fixtureBody(t testing.TB, endpointID string) any { _, b := fixture(t, endpointID); return b }

func makeJWT(exp float64) string {
	b := func(s string) string { return base64.RawURLEncoding.EncodeToString([]byte(s)) }
	return b("{}") + "." + b(fmt.Sprintf(`{"exp":%v}`, exp)) + ".c2ln"
}

type call struct {
	Method string
	Path   string
	Query  map[string]string
	Header http.Header
	Body   any
}

type reply struct {
	status int
	body   any
	text   string
	header map[string]string
	err    error
}

type route struct {
	method, path string
	prefix       bool
	replies      []reply
	mu           sync.Mutex
	calls        []call
}

func (r *route) count() int    { r.mu.Lock(); defer r.mu.Unlock(); return len(r.calls) }
func (r *route) last() call    { r.mu.Lock(); defer r.mu.Unlock(); return r.calls[len(r.calls)-1] }
func (r *route) at(i int) call { r.mu.Lock(); defer r.mu.Unlock(); return r.calls[i] }

type mockHTTP struct {
	mu     sync.Mutex
	routes []*route
	calls  []call
}

func (m *mockHTTP) on(method, path string, replies ...reply) *route {
	r := &route{method: method, path: strings.TrimSuffix(path, "*"), prefix: strings.HasSuffix(path, "*"), replies: replies}
	m.mu.Lock()
	m.routes = append([]*route{r}, m.routes...)
	m.mu.Unlock()
	return r
}

// endpoint mocks one spec endpoint with its shared fixture (or the given reply).
func (m *mockHTTP) endpoint(t testing.TB, endpointID string, override ...reply) *route {
	e := specEndpoints[endpointID]
	status, body := fixture(t, endpointID)
	rep := reply{status: status, body: body}
	if len(override) > 0 {
		rep = override[0]
	}
	path := e.path
	if i := strings.Index(path, "{"); i >= 0 {
		path = path[:i] + "*"
	}
	return m.on(e.method, path, rep)
}

func (m *mockHTTP) RoundTrip(req *http.Request) (*http.Response, error) {
	if err := req.Context().Err(); err != nil {
		return nil, err // like a real transport
	}
	c := call{Method: req.Method, Path: req.URL.Path, Query: map[string]string{}, Header: req.Header.Clone()}
	for k := range req.URL.Query() {
		c.Query[k] = req.URL.Query().Get(k)
	}
	if req.Body != nil {
		data, _ := io.ReadAll(req.Body)
		if len(data) > 0 {
			_ = json.Unmarshal(data, &c.Body)
		}
	}
	m.mu.Lock()
	m.calls = append(m.calls, c)
	var match *route
	for _, r := range m.routes {
		if r.method == req.Method && (r.path == req.URL.Path || (r.prefix && strings.HasPrefix(req.URL.Path, r.path))) {
			match = r
			break
		}
	}
	m.mu.Unlock()
	if match == nil {
		return nil, fmt.Errorf("not mocked: %s %s", req.Method, req.URL.Path)
	}
	match.mu.Lock()
	match.calls = append(match.calls, c)
	rep := match.replies[0]
	if len(match.replies) > 1 {
		match.replies = match.replies[1:]
	}
	match.mu.Unlock()
	if rep.err != nil {
		return nil, rep.err
	}
	var payload []byte
	switch {
	case rep.text != "":
		payload = []byte(rep.text)
	case rep.body != nil:
		payload, _ = json.Marshal(rep.body)
	}
	resp := &http.Response{StatusCode: rep.status, Header: http.Header{}, Body: io.NopCloser(bytes.NewReader(payload)), Request: req}
	for k, v := range rep.header {
		resp.Header.Set(k, v)
	}
	return resp, nil
}

type fakeTime struct {
	mu     sync.Mutex
	now    time.Time
	sleeps []float64
}

func newFakeTime() *fakeTime { return &fakeTime{now: time.Unix(testNow, 0)} }

func (f *fakeTime) Clock() time.Time { f.mu.Lock(); defer f.mu.Unlock(); return f.now }

func (f *fakeTime) Sleep(d time.Duration) <-chan time.Time {
	f.mu.Lock()
	f.sleeps = append(f.sleeps, d.Seconds())
	f.now = f.now.Add(d)
	f.mu.Unlock()
	ch := make(chan time.Time, 1)
	ch <- f.now
	return ch
}

func (f *fakeTime) advance(seconds float64) {
	f.mu.Lock()
	f.now = f.now.Add(time.Duration(seconds * float64(time.Second)))
	f.mu.Unlock()
}

func (f *fakeTime) slept() []float64 {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]float64(nil), f.sleeps...)
}

type env struct {
	client *Client
	http   *mockHTTP
	time   *fakeTime
	auth   *route
}

func newEnv(t testing.TB, mutate ...func(*Config)) env {
	t.Helper()
	m := &mockHTTP{}
	ft := newFakeTime()
	cfg := Config{APIKey: "test-key", SecretKey: "test-secret", HTTPClient: &http.Client{Transport: m}, Clock: ft.Clock, Sleep: ft.Sleep}
	for _, f := range mutate {
		f(&cfg)
	}
	auth := m.endpoint(t, "credentials_post_usr_authenticate")
	c, err := New(cfg)
	if err != nil {
		t.Fatal(err)
	}
	return env{client: c, http: m, time: ft, auth: auth}
}

func must[T any](t testing.TB) func(T, error) T {
	return func(v T, err error) T {
		t.Helper()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		return v
	}
}

func eq(t testing.TB, got, want any) {
	t.Helper()
	if fmt.Sprint(got) != fmt.Sprint(want) {
		t.Fatalf("got %v, want %v", got, want)
	}
}
