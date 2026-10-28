package io.github.bitpindev.bitpin;

import java.io.IOException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.UnaryOperator;

/** Mock HTTP, fake time and a client wired to both. */
final class TestSupport {
  private TestSupport() {}

  /** Seconds; before the fixture tokens expire. */
  static final long TEST_NOW = 4_000_000_000L;

  /** A fixture order's created_at in ms. */
  static final long T_ORDER = 1793083530123L;

  static String makeJwt(double exp) {
    Base64.Encoder b = Base64.getUrlEncoder().withoutPadding();
    String payload =
        "{\"exp\":"
            + (exp == Math.rint(exp) ? String.valueOf((long) exp) : String.valueOf(exp))
            + "}";
    return b.encodeToString("{}".getBytes(StandardCharsets.UTF_8))
        + "."
        + b.encodeToString(payload.getBytes(StandardCharsets.UTF_8))
        + ".c2ln";
  }

  static <K, V> Map<K, V> map(Object... pairs) {
    Map<K, V> out = new LinkedHashMap<>();
    for (int i = 0; i < pairs.length; i += 2) {
      @SuppressWarnings("unchecked")
      K k = (K) pairs[i];
      @SuppressWarnings("unchecked")
      V v = (V) pairs[i + 1];
      out.put(k, v);
    }
    return out;
  }

  /** One request the client sent. */
  record Call(
      String method,
      String path,
      Map<String, String> query,
      Map<String, String> headers,
      Object body) {
    String header(String name) {
      return headers.get(name.toLowerCase(Locale.ROOT));
    }
  }

  /** One canned response, or a transport failure. */
  record Reply(
      int status, Object body, String text, Map<String, String> headers, IOException error) {
    static Reply of(int status, Object body) {
      return new Reply(status, body, null, Map.of(), null);
    }

    static Reply text(int status, String text) {
      return new Reply(status, null, text, Map.of(), null);
    }

    static Reply fail(IOException error) {
      return new Reply(0, null, null, Map.of(), error);
    }

    Reply withHeader(String name, String value) {
      Map<String, String> h = new HashMap<>(headers);
      h.put(name.toLowerCase(Locale.ROOT), value);
      return new Reply(status, body, text, h, error);
    }
  }

  /** The replies of one method and path; the last reply repeats. */
  static final class Route {
    final String method;
    final String path;
    final boolean prefix;
    private final Deque<Reply> replies;
    private final List<Call> calls = new ArrayList<>();

    Route(String method, String path, Reply... replies) {
      this.method = method;
      this.prefix = path.endsWith("*");
      this.path = prefix ? path.substring(0, path.length() - 1) : path;
      this.replies = new ArrayDeque<>(List.of(replies));
    }

    synchronized Reply next(Call call) {
      calls.add(call);
      return replies.size() > 1 ? replies.pollFirst() : replies.peekFirst();
    }

    synchronized int count() {
      return calls.size();
    }

    synchronized Call last() {
      return calls.get(calls.size() - 1);
    }

    synchronized Call at(int i) {
      return calls.get(i);
    }
  }

  /** A {@link RestTransport} that answers from routes; the newest matching route wins. */
  static final class MockHttp implements RestTransport {
    private final List<Route> routes = new ArrayList<>();
    final List<Call> calls = new ArrayList<>();

    synchronized Route on(String method, String path, Reply... replies) {
      Route r = new Route(method, path, replies);
      routes.add(0, r);
      return r;
    }

    /** Mocks one spec endpoint with its shared fixture, or with the given reply. */
    Route endpoint(String endpointId, Reply... override) {
      Endpoint e = Spec.ENDPOINTS.get(endpointId);
      Reply reply =
          override.length > 0
              ? override[0]
              : Reply.of(Fixtures.status(endpointId), Fixtures.body(endpointId));
      String path = e.path();
      int brace = path.indexOf('{');
      if (brace >= 0) {
        path = path.substring(0, brace) + "*";
      }
      return on(e.method(), path, reply);
    }

    @Override
    public Response send(Request request) throws IOException {
      Map<String, String> query = new LinkedHashMap<>();
      String raw = request.uri().getRawQuery();
      if (raw != null) {
        for (String pair : raw.split("&")) {
          int eq = pair.indexOf('=');
          query.put(
              URLDecoder.decode(pair.substring(0, eq), StandardCharsets.UTF_8),
              URLDecoder.decode(pair.substring(eq + 1), StandardCharsets.UTF_8));
        }
      }
      Map<String, String> headers = new HashMap<>();
      request.headers().forEach((k, v) -> headers.put(k.toLowerCase(Locale.ROOT), v));
      String path = request.uri().getRawPath();
      Call call =
          new Call(
              request.method(),
              path,
              query,
              headers,
              request.body() == null ? null : Json.parse(request.body()));
      Route match = null;
      synchronized (this) {
        calls.add(call);
        for (Route r : routes) {
          if (r.method.equals(request.method())
              && (r.path.equals(path) || (r.prefix && path.startsWith(r.path)))) {
            match = r;
            break;
          }
        }
      }
      if (match == null) {
        throw new IOException("not mocked: " + request.method() + " " + path);
      }
      Reply reply = match.next(call);
      if (reply.error() != null) {
        throw reply.error();
      }
      byte[] payload =
          reply.text() != null
              ? reply.text().getBytes(StandardCharsets.UTF_8)
              : reply.body() != null
                  ? Json.write(reply.body()).getBytes(StandardCharsets.UTF_8)
                  : new byte[0];
      return new Response(reply.status(), reply.headers(), payload);
    }
  }

  /** A clock that only moves when the client sleeps or the test advances it. */
  static final class FakeTime extends Clock implements Config.Sleeper {
    private Instant now = Instant.ofEpochSecond(TEST_NOW);
    private final List<Double> sleeps = new ArrayList<>();

    @Override
    public synchronized Instant instant() {
      return now;
    }

    @Override
    public ZoneId getZone() {
      return ZoneOffset.UTC;
    }

    @Override
    public Clock withZone(ZoneId zone) {
      return this;
    }

    @Override
    public synchronized void sleep(Duration duration) {
      sleeps.add(duration.toNanos() / 1e9);
      now = now.plus(duration);
    }

    synchronized void advance(double seconds) {
      now = now.plusNanos((long) (seconds * 1e9));
    }

    synchronized List<Double> slept() {
      return List.copyOf(sleeps);
    }
  }

  record Env(Bitpin client, MockHttp http, FakeTime time, Route auth) {}

  /** A client with test keys on mock HTTP and fake time; authenticate is mocked. */
  @SafeVarargs
  static Env env(UnaryOperator<Config.Builder>... mutate) {
    MockHttp http = new MockHttp();
    FakeTime time = new FakeTime();
    Config.Builder b =
        Config.builder()
            .apiKey("test-key")
            .secretKey("test-secret")
            .restTransport(http)
            .clock(time)
            .sleeper(time);
    for (UnaryOperator<Config.Builder> m : mutate) {
      b = m.apply(b);
    }
    Route auth = http.endpoint("credentials_post_usr_authenticate");
    return new Env(new Bitpin(b.build()), http, time, auth);
  }

  static String fixtureAccess() {
    return Json.str(Json.asMap(Fixtures.body("credentials_post_usr_authenticate")).get("access"));
  }
}
