package io.github.bitpindev.bitpin;

import java.io.IOException;
import java.net.URI;
import java.time.Duration;
import java.util.Locale;
import java.util.Map;

/**
 * Sends one HTTP request. The default uses {@link java.net.http.HttpClient}; replace it with {@link
 * Config.Builder#restTransport} in tests or to use another HTTP stack.
 */
@FunctionalInterface
public interface RestTransport {
  /** One request: {@code body} is JSON text or null. */
  record Request(
      String method, URI uri, Map<String, String> headers, String body, Duration timeout) {}

  /** One response: header names are lowercase. */
  record Response(int status, Map<String, String> headers, byte[] body) {
    /** A header by its name, any case; null when absent. */
    public String header(String name) {
      return headers.get(name.toLowerCase(Locale.ROOT));
    }
  }

  /**
   * Sends the request. Throw {@link java.net.http.HttpTimeoutException} for a timeout and another
   * {@link IOException} for other transport failures.
   */
  Response send(Request request) throws IOException, InterruptedException;
}
