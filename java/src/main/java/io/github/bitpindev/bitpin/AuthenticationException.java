package io.github.bitpindev.bitpin;

/** Missing or rejected API keys or tokens. ccxt: {@code AuthenticationError}. */
public class AuthenticationException extends ExchangeException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public AuthenticationException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public AuthenticationException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "AuthenticationError";
  }
}
