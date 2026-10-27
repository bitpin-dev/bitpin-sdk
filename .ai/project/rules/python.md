# Rule: Python

- Python 3.10+. Every module starts with `from __future__ import annotations`. mypy strict passes; `Any` only at JSON boundaries.
- Edit `_async/client.py`; regenerate `_sync/` with `scripts/gen_sync.py`. Write code unasync can translate: `async def`/`await`, primitives from `_async/_compat.py`, no `asyncio.*` calls inside the client.
- Keep pure logic (building requests, parsing, error mapping, token and limiter state) in `_core/`, with no I/O, so both clients share it and tests need no network.
- Prices and amounts are `Decimal`. Parse with `to_decimal`, send with `fmt_decimal`. Floats are accepted as input only, through `repr`.
- Results are ccxt-shaped `TypedDict`s from `types.py`, each with the raw response in `info`.
- Public methods take ccxt arguments (`symbol, since, limit, params`). Validate locally and raise `BadRequest`/`InvalidOrder` before spending a rate-limit slot.
- Imports: modules and names at the top of the file; a local import needs a comment saying why (circular import, optional extra).
- Docstrings say what the caller must know: units, limits, side effects. Skip restating the signature.
