# Fixtures

One file per endpoint in `spec/bitpin.yaml`, named `<endpoint id>.json`:

```json
{ "status": 200, "body": <response body> }
```

Every SDK language replays these in its tests, so all of them parse the same responses the same way.

Rules:

- Shapes follow the server's serializers. Values are synthetic: no real users, addresses, IBANs, cards, tokens or tx hashes.
- When the server changes a response, update the fixture first, then make every language's tests pass.
