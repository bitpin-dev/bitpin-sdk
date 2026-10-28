package io.github.bitpindev.bitpin;

/** The server is down or in maintenance (5xx). ccxt: {@code ExchangeNotAvailable}. */
public class ExchangeNotAvailableException extends NetworkException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public ExchangeNotAvailableException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public ExchangeNotAvailableException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "ExchangeNotAvailable";
  }
}
