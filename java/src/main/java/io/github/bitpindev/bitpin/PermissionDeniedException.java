package io.github.bitpindev.bitpin;

/** Your account may not do this (e.g. no API trading access). ccxt: {@code PermissionDenied}. */
public class PermissionDeniedException extends ExchangeException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public PermissionDeniedException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public PermissionDeniedException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "PermissionDenied";
  }
}
