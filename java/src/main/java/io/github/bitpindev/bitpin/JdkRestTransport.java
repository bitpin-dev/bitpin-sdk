package io.github.bitpindev.bitpin;

import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/** The default {@link RestTransport}, on the JDK's HTTP client. */
final class JdkRestTransport implements RestTransport {
  private final HttpClient client;

  JdkRestTransport(HttpClient client) {
    this.client = client;
  }

  @Override
  public Response send(Request request) throws IOException, InterruptedException {
    HttpRequest.BodyPublisher body =
        request.body() == null
            ? HttpRequest.BodyPublishers.noBody()
            : HttpRequest.BodyPublishers.ofString(request.body());
    HttpRequest.Builder builder =
        HttpRequest.newBuilder(request.uri())
            .timeout(request.timeout())
            .method(request.method(), body);
    request.headers().forEach(builder::header);
    HttpResponse<byte[]> response =
        client.send(builder.build(), HttpResponse.BodyHandlers.ofByteArray());
    Map<String, String> headers = new HashMap<>();
    response
        .headers()
        .map()
        .forEach((k, v) -> headers.put(k.toLowerCase(Locale.ROOT), v.isEmpty() ? "" : v.get(0)));
    return new Response(response.statusCode(), headers, response.body());
  }
}
