package io.github.bitpindev.bitpin;

import java.net.http.HttpClient;
import java.time.Clock;
import java.time.Duration;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;

/**
 * The client settings, built with {@link #builder()}. Without keys only public endpoints work.
 *
 * <pre>{@code
 * Config config = Config.builder()
 *     .apiKey("...").secretKey("...")
 *     .domain(Domain.IR)                       // ORG (default), IR or MARKET
 *     .timeout(Duration.ofSeconds(10))
 *     .maxRetries(3)                           // idempotent requests only
 *     .rateLimit("orderbook", "10800/min")
 *     .tokenStore(new FileTokenStore())        // share tokens across processes
 *     .build();
 * }</pre>
 */
public final class Config {
  /** Sleeps; replaced in tests. */
  @FunctionalInterface
  public interface Sleeper {
    /** Waits for {@code duration}. */
    void sleep(Duration duration) throws InterruptedException;
  }

  private final String apiKey;
  private final String secretKey;
  private final Domain domain;
  private final String restUrl;
  private final String wsUrl;
  private final Duration timeout;
  private final int maxRetries;
  private final boolean rateLimitEnabled;
  private final Map<String, RateLimit> rateLimits;
  private final String userAgent;
  private final TokenStore tokenStore;
  private final RestTransport restTransport;
  private final Clock clock;
  private final Sleeper sleeper;
  private final WsTransport.Factory wsTransport;

  private Config(Builder b) {
    apiKey = b.apiKey == null ? "" : b.apiKey;
    secretKey = b.secretKey == null ? "" : b.secretKey;
    domain = b.domain == null ? Domain.parse(null) : b.domain;
    restUrl = b.restUrl == null || b.restUrl.isEmpty() ? domain.restUrl() : b.restUrl;
    wsUrl = b.wsUrl == null || b.wsUrl.isEmpty() ? domain.wsUrl() : b.wsUrl;
    timeout = b.timeout;
    maxRetries = b.maxRetries;
    rateLimitEnabled = b.rateLimitEnabled;
    Map<String, RateLimit> limits = new TreeMap<>(Spec.RATE_LIMITS);
    limits.putAll(b.rateLimits);
    rateLimits = Collections.unmodifiableMap(limits);
    userAgent =
        b.userAgent == null || b.userAgent.isEmpty()
            ? "bitpin-sdk-java/" + Version.VERSION
            : b.userAgent;
    tokenStore = b.tokenStore == null ? new MemoryTokenStore() : b.tokenStore;
    restTransport =
        b.restTransport != null
            ? b.restTransport
            : new JdkRestTransport(
                b.httpClient != null
                    ? b.httpClient
                    : HttpClient.newBuilder().connectTimeout(timeout).build());
    clock = b.clock == null ? Clock.systemUTC() : b.clock;
    sleeper = b.sleeper == null ? Thread::sleep : b.sleeper;
    wsTransport = b.wsTransport == null ? CentrifugeTransport::new : b.wsTransport;
  }

  /** A builder with the defaults. */
  public static Builder builder() {
    return new Builder();
  }

  /** Reads {@code BITPIN_API_KEY}, {@code BITPIN_SECRET_KEY} and {@code BITPIN_DOMAIN}. */
  public static Builder fromEnv() {
    return builder()
        .apiKey(System.getenv("BITPIN_API_KEY"))
        .secretKey(System.getenv("BITPIN_SECRET_KEY"))
        .domain(Domain.parse(System.getenv("BITPIN_DOMAIN")));
  }

  String apiKey() {
    return apiKey;
  }

  String secretKey() {
    return secretKey;
  }

  boolean hasCredentials() {
    return !apiKey.isEmpty() && !secretKey.isEmpty();
  }

  /** The API domain. */
  public Domain domain() {
    return domain;
  }

  /** The REST base URL in use. */
  public String restUrl() {
    return restUrl;
  }

  /** The WebSocket URL in use. */
  public String wsUrl() {
    return wsUrl;
  }

  /** The timeout per request. */
  public Duration timeout() {
    return timeout;
  }

  /** Retries of idempotent requests. */
  public int maxRetries() {
    return maxRetries;
  }

  /** Whether the client-side rate limiter is on. */
  public boolean rateLimitEnabled() {
    return rateLimitEnabled;
  }

  /** The effective limit of every bucket. */
  public Map<String, RateLimit> rateLimits() {
    return rateLimits;
  }

  /** The User-Agent header. */
  public String userAgent() {
    return userAgent;
  }

  TokenStore tokenStore() {
    return tokenStore;
  }

  RestTransport restTransport() {
    return restTransport;
  }

  Clock clock() {
    return clock;
  }

  Sleeper sleeper() {
    return sleeper;
  }

  WsTransport.Factory wsTransport() {
    return wsTransport;
  }

  /** Hides the credentials. */
  @Override
  public String toString() {
    return "Config{apiKey="
        + (apiKey.isEmpty() ? "\"\"" : "***")
        + ", secretKey="
        + (secretKey.isEmpty() ? "\"\"" : "***")
        + ", domain="
        + domain
        + ", restUrl="
        + restUrl
        + "}";
  }

  /** Builds a {@link Config}; every setting is optional. */
  public static final class Builder {
    private String apiKey;
    private String secretKey;
    private Domain domain;
    private String restUrl;
    private String wsUrl;
    private Duration timeout = Duration.ofSeconds(10);
    private int maxRetries = 3;
    private boolean rateLimitEnabled = true;
    private final Map<String, RateLimit> rateLimits = new LinkedHashMap<>();
    private String userAgent;
    private TokenStore tokenStore;
    private HttpClient httpClient;
    private RestTransport restTransport;
    private Clock clock;
    private Sleeper sleeper;
    private WsTransport.Factory wsTransport;

    private Builder() {}

    /** Your API key (needed for private endpoints). */
    public Builder apiKey(String apiKey) {
      this.apiKey = apiKey;
      return this;
    }

    /** Your secret key (needed for private endpoints). */
    public Builder secretKey(String secretKey) {
      this.secretKey = secretKey;
      return this;
    }

    /** The API domain; {@link Domain#ORG} by default. */
    public Builder domain(Domain domain) {
      this.domain = domain;
      return this;
    }

    /** Overrides the domain's REST URL (e.g. a proxy). */
    public Builder restUrl(String restUrl) {
      this.restUrl = restUrl;
      return this;
    }

    /** Overrides the domain's WebSocket URL. */
    public Builder wsUrl(String wsUrl) {
      this.wsUrl = wsUrl;
      return this;
    }

    /** The timeout per request; 10 seconds by default. */
    public Builder timeout(Duration timeout) {
      Objects.requireNonNull(timeout, "timeout");
      if (timeout.isNegative() || timeout.isZero()) {
        throw new IllegalArgumentException("timeout must be positive");
      }
      this.timeout = timeout;
      return this;
    }

    /** Retries of idempotent requests only; 3 by default, 0 disables them. */
    public Builder maxRetries(int maxRetries) {
      if (maxRetries < 0) {
        throw new IllegalArgumentException("maxRetries must be >= 0");
      }
      this.maxRetries = maxRetries;
      return this;
    }

    /** Turns the client-side limiter off; the server still enforces its limits. */
    public Builder disableRateLimit() {
      this.rateLimitEnabled = false;
      return this;
    }

    /** Overrides one bucket's server default, e.g. {@code ("orderbook", "10800/min")}. */
    public Builder rateLimit(String bucket, String limit) {
      if (!Spec.RATE_LIMITS.containsKey(bucket)) {
        throw new IllegalArgumentException("unknown rate-limit bucket \"" + bucket + "\"");
      }
      rateLimits.put(bucket, RateLimit.parse(limit));
      return this;
    }

    /** The User-Agent header; {@code bitpin-sdk-java/<version>} by default. */
    public Builder userAgent(String userAgent) {
      this.userAgent = userAgent;
      return this;
    }

    /** Caches tokens; in memory by default. See {@link FileTokenStore}. */
    public Builder tokenStore(TokenStore tokenStore) {
      this.tokenStore = tokenStore;
      return this;
    }

    /** The JDK HTTP client to send requests with (proxy, TLS, executor). */
    public Builder httpClient(HttpClient httpClient) {
      this.httpClient = httpClient;
      return this;
    }

    /** Replaces the HTTP layer entirely (tests, other HTTP stacks). */
    public Builder restTransport(RestTransport restTransport) {
      this.restTransport = restTransport;
      return this;
    }

    /** The clock for tokens, limits and time ranges (tests). */
    public Builder clock(Clock clock) {
      this.clock = clock;
      return this;
    }

    /** How the client waits for the limiter and retries (tests). */
    public Builder sleeper(Sleeper sleeper) {
      this.sleeper = sleeper;
      return this;
    }

    /** Replaces the Centrifugo connection (tests). */
    public Builder wsTransport(WsTransport.Factory wsTransport) {
      this.wsTransport = wsTransport;
      return this;
    }

    /** The settings. */
    public Config build() {
      return new Config(this);
    }
  }
}
