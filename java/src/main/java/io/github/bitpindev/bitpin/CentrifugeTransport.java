package io.github.bitpindev.bitpin;

import io.github.centrifugal.centrifuge.Client;
import io.github.centrifugal.centrifuge.ConnectionTokenEvent;
import io.github.centrifugal.centrifuge.ConnectionTokenGetter;
import io.github.centrifugal.centrifuge.DuplicateSubscriptionException;
import io.github.centrifugal.centrifuge.EventListener;
import io.github.centrifugal.centrifuge.Options;
import io.github.centrifugal.centrifuge.PublicationEvent;
import io.github.centrifugal.centrifuge.Subscription;
import io.github.centrifugal.centrifuge.SubscriptionEventListener;
import io.github.centrifugal.centrifuge.TokenCallback;
import java.util.function.Consumer;

/**
 * The default {@link WsTransport}: Centrifugo's official Java client. It reconnects on its own and
 * asks for a new token when the old one expires.
 */
final class CentrifugeTransport implements WsTransport {
  private final Client client;

  CentrifugeTransport(String url, TokenSource tokens) {
    Options opts = new Options();
    opts.setName("bitpin-sdk-java");
    opts.setVersion(Version.VERSION);
    if (tokens != null) {
      opts.setTokenGetter(
          new ConnectionTokenGetter() {
            @Override
            public void getConnectionToken(ConnectionTokenEvent event, TokenCallback cb) {
              // centrifuge-java runs callbacks on its single client thread: fetching the token
              // (an HTTP call) there would stall pings and replies, so it runs on its own thread.
              Thread.ofVirtual()
                  .name("bitpin-ws-token")
                  .start(
                      () -> {
                        String token;
                        try {
                          token = tokens.token();
                        } catch (RuntimeException e) {
                          cb.Done(e, null);
                          return;
                        }
                        cb.Done(null, token);
                      });
            }
          });
    }
    client = new Client(url, opts, new EventListener() {});
  }

  @Override
  public void connect() {
    client.connect();
  }

  @Override
  public void subscribe(String channel, Consumer<byte[]> onData) {
    Subscription sub;
    try {
      sub =
          client.newSubscription(
              channel,
              new SubscriptionEventListener() {
                @Override
                public void onPublication(Subscription s, PublicationEvent event) {
                  onData.accept(event.getData());
                }
              });
    } catch (DuplicateSubscriptionException e) {
      return; // already subscribed
    }
    sub.subscribe();
  }

  @Override
  public void close() {
    try {
      client.close(5000);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
    }
  }
}
