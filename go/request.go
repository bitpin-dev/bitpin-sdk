package bitpin

import (
	"fmt"
	"net/url"
	"regexp"
	"sort"
	"strings"

	"github.com/shopspring/decimal"
)

type endpoint struct {
	id, method, path, auth string
	buckets                []string
	idempotent             bool
}

type errorRule struct {
	status        int
	kind          string
	paths, detail []string
}

type builtRequest struct {
	endpoint
	url     string
	query   url.Values
	body    any
	hasBody bool
}

var missingParam = regexp.MustCompile(`\{(\w+)\}`)

func queryValue(value any) string {
	switch v := value.(type) {
	case bool:
		if v {
			return "true"
		}
		return "false"
	case []string:
		return strings.Join(v, ",")
	case []any:
		parts := make([]string, len(v))
		for i, item := range v {
			parts[i] = queryValue(item)
		}
		return strings.Join(parts, ",")
	case decimal.Decimal, *decimal.Decimal, float64, float32:
		s, _ := formatDecimal(v)
		return s
	default:
		return fmt.Sprint(v)
	}
}

func bodyValue(value any) any {
	switch v := value.(type) {
	case nil, bool, string:
		return v
	case decimal.Decimal, *decimal.Decimal, float64, float32, int, int64:
		s, _ := formatDecimal(v)
		return s
	case map[string]any:
		out := make(map[string]any, len(v))
		for k, item := range v {
			if item != nil {
				out[k] = bodyValue(item)
			}
		}
		return out
	case []any:
		out := make([]any, len(v))
		for i, item := range v {
			out[i] = bodyValue(item)
		}
		return out
	case []map[string]any:
		out := make([]any, len(v))
		for i, item := range v {
			out[i] = bodyValue(item)
		}
		return out
	case []string:
		return v
	default:
		return v
	}
}

func buildRequest(cfg resolvedConfig, endpointID string, pathParams, params map[string]any, body any) (builtRequest, error) {
	e, ok := specEndpoints[endpointID]
	if !ok {
		return builtRequest{}, fmt.Errorf("unknown endpoint %s", endpointID)
	}
	path := e.path
	keys := make([]string, 0, len(pathParams))
	for k := range pathParams {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		path = strings.ReplaceAll(path, "{"+k+"}", url.PathEscape(fmt.Sprint(pathParams[k])))
	}
	if m := missingParam.FindStringSubmatch(path); m != nil {
		return builtRequest{}, fmt.Errorf("missing path parameter %q for %s", m[1], endpointID)
	}
	query := url.Values{}
	for k, v := range params {
		if v != nil {
			query.Set(k, queryValue(v))
		}
	}
	req := builtRequest{endpoint: e, url: strings.TrimRight(cfg.RestURL, "/") + path, query: query}
	if body != nil {
		req.body = bodyValue(body)
		req.hasBody = true
	}
	return req, nil
}
