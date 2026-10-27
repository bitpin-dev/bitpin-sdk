# Rule: spec and fixtures

`spec/bitpin.yaml` is the contract every language implements. A change starts there and flows outward.

- Change the spec first, then regenerate (`gen_python.py`), then code, then tests, then docs. Use the `add-endpoint` skill for anything endpoint-shaped.
- Paths start with `/api/` and end with `/`. Only `/api/` endpoints are in scope; the server rejects a missing trailing slash.
- Endpoint ids are `<auth>_<method>_<path without /api/vN/>` (ccxt implicit style). Renaming one is a breaking change.
- `idempotent: true` only for requests that are safe to send twice. Every POST and DELETE is `false`, except the deposit address, which returns the existing address.
- `buckets` lists every server throttle a request consumes (bulk create consumes two). Values are the server's defaults; users override them in config, so the spec never carries VIP or per-user limits.
- Error rules are ordered; the first match wins. Put specific rules (path or detail) above generic ones.
- A missing capability is `has: false` plus an `en` and `fa` message that tells the user what to do instead.
- Each endpoint has exactly one fixture, `fixtures/<endpoint id>.json`, in the shape the server returns today, with synthetic values (all-zero IBANs, `TTestAddress…` addresses).
- When the server's response shape changes, update the fixture, then make every language pass.
