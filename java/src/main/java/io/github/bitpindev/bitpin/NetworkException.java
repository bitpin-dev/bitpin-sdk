package io.github.bitpindev.bitpin;

/** The request failed or the server didn't answer usefully. ccxt: {@code NetworkError}. */
public class NetworkException extends BitpinException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public NetworkException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public NetworkException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "NetworkError";
  }
}
