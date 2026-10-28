package io.github.bitpindev.bitpin;

/**
 * Too many requests; {@link #retryAfter()} is the server's hint. ccxt: {@code RateLimitExceeded}.
 */
public class RateLimitExceededException extends NetworkException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public RateLimitExceededException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public RateLimitExceededException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "RateLimitExceeded";
  }
}
