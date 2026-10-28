package io.github.bitpindev.bitpin;

/** The server answered with an error. ccxt: {@code ExchangeError}. */
public class ExchangeException extends BitpinException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public ExchangeException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public ExchangeException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "ExchangeError";
  }
}
