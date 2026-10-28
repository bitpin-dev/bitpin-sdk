package io.github.bitpindev.bitpin;

/**
 * Bitpin doesn't offer this yet; {@link #feature()} names the capability. ccxt: {@code
 * NotSupported}.
 */
public class NotSupportedException extends ExchangeException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public NotSupportedException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public NotSupportedException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "NotSupported";
  }
}
