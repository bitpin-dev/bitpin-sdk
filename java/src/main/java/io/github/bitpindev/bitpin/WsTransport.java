package io.github.bitpindev.bitpin;

import java.util.function.Consumer;

/**
 * The Centrifugo connection. The default is {@code centrifuge-java}, Centrifugo's official client;
 * tests replace it with {@link Config.Builder#wsTransport}.
 */
public interface WsTransport {
  /** Supplies a fresh connection token; it may block (it calls the REST API). */
  @FunctionalInterface
  interface TokenSource {
    /** A connection token. */
    String token();
  }

  /** Builds a transport; {@code tokens} is null for clients without API keys. */
  @FunctionalInterface
  interface Factory {
    /** A transport for {@code url}. */
    WsTransport create(String url, TokenSource tokens);
  }

  /** Starts connecting; the transport reconnects on its own. */
  void connect();

  /** Subscribes to {@code channel}; {@code onData} gets each publication's JSON bytes. */
  void subscribe(String channel, Consumer<byte[]> onData);

  /** Disconnects for good. */
  void close();
}
