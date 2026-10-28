package io.github.bitpindev.bitpin;

/** The request was invalid; often caught locally before sending. ccxt: {@code BadRequest}. */
public class BadRequestException extends ExchangeException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public BadRequestException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public BadRequestException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "BadRequest";
  }
}
