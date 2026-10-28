package io.github.bitpindev.bitpin;

/** No such order. ccxt: {@code OrderNotFound}. */
public class OrderNotFoundException extends ExchangeException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public OrderNotFoundException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public OrderNotFoundException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "OrderNotFound";
  }
}
