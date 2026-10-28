package io.github.bitpindev.bitpin;

/** The request or wait timed out. ccxt: {@code RequestTimeout}. */
public class RequestTimeoutException extends NetworkException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public RequestTimeoutException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public RequestTimeoutException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "RequestTimeout";
  }
}
