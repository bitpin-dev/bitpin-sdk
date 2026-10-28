package io.github.bitpindev.bitpin;

/** Not enough balance for the order or withdrawal. ccxt: {@code InsufficientFunds}. */
public class InsufficientFundsException extends ExchangeException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public InsufficientFundsException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public InsufficientFundsException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "InsufficientFunds";
  }
}
