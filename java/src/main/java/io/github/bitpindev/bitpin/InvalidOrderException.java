package io.github.bitpindev.bitpin;

/** The order was rejected: bad price, amount, type or state. ccxt: {@code InvalidOrder}. */
public class InvalidOrderException extends ExchangeException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public InvalidOrderException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public InvalidOrderException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "InvalidOrder";
  }
}
