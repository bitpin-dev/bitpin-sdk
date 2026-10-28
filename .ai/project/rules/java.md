# Rule: Java

- Maven `io.github.bitpin-dev:bitpin-sdk`, package `io.github.bitpindev.bitpin` (the hyphen can't be in a package). The jar targets Java 21 (`maven.compiler.release`); develop on the JDK in `.java-version`; build only with `./mvnw` (pinned Maven). Keep dependencies and plugins on their newest releases; if a newest version breaks the build, work around it and leave a comment naming the version (see google-java-format in `pom.xml`).
- Every method blocks and the client is thread-safe: shared state sits behind `ReentrantLock` (not `synchronized`, which pins virtual threads on Java 21), auth is single-flight, limiter reservations are atomic. Restore the interrupt flag whenever you catch `InterruptedException`.
- Errors are unchecked `BitpinException` subclasses mirroring ccxt (`InsufficientFundsException` → ccxt `InsufficientFunds`, see `ccxtName()`). Credentials requests never chain the transport exception (it holds the request body).
- Numbers are `BigDecimal` in and out; JSON floats parse to `BigDecimal` (Jackson 3, `USE_BIG_DECIMAL_FOR_FLOATS`), and requests carry plain decimal strings. Nullable results are `null`, not `Optional`.
- The WebSocket is Centrifugo's official `centrifuge-java`. Its callbacks run on its single client thread: never block there (the ws-info token fetch runs on a virtual thread).
- Behaviour matches Python, TypeScript and Go; change all four together. Tests replay `fixtures/` through `TestSupport.MockHttp` and `FakeTime`, assert the exact request sent, and `ConformanceTest` compares the parsers with `fixtures/expected.json`.
- Releases are `java-vX.Y.Z` tags from release-please; CI uploads to the Maven Central Portal and a maintainer publishes.
