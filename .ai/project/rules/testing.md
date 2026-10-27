# Rule: testing

- Write the test first and watch it fail for the right reason, then implement.
- Client tests are `async def` and use the `client` fixture, which runs each test against `AsyncBitpin` and `Bitpin`. Wrap calls in `await call(...)`.
- Mock HTTP with respx through `tests.conftest.route(mock, endpoint_id, ...)`, which serves the shared fixture. Assert on what was sent: method, path, query and JSON body, exactly.
- Time is `FakeTime`: assert sleeps and token refreshes, never wall-clock waits.
- Every write method has a test proving it is sent once on `NetworkError`.
- Every validation error has a test proving nothing was sent.
- Coverage gate: 95 % branch on `python/src`. New branches come with tests.
- Tests never reach the network. `@pytest.mark.live` tests are read-only and opt-in.
