package io.github.bitpindev.bitpin;

import java.util.OptionalDouble;

/**
 * The root of every exception the SDK throws. The subclasses follow ccxt's hierarchy: {@link
 * ExchangeException} when the server answered with an error, {@link NetworkException} when it
 * didn't answer usefully.
 *
 * <p>Catch the narrowest class you can act on, e.g. {@link InsufficientFundsException}.
 */
public class BitpinException extends RuntimeException {
  private static final long serialVersionUID = 1L;

  private int status;
  private transient Object body;
  private String endpointId;
  private double retryAfter = -1;
  private String code;
  private String feature;

  /** An error with a message. */
  public BitpinException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public BitpinException(String message, Throwable cause) {
    super(message, cause);
  }

  /** The ccxt class name, e.g. {@code InsufficientFunds}. */
  public String ccxtName() {
    return "BitpinError";
  }

  /** The HTTP status, 0 if the request didn't get a response. */
  public int status() {
    return status;
  }

  /** The parsed error body: a {@code Map}, a {@code List}, a {@code String} or null. */
  public Object body() {
    return body;
  }

  /** The spec endpoint id, e.g. {@code private_post_odr_orders}; null for local errors. */
  public String endpointId() {
    return endpointId;
  }

  /** The server's hint in seconds, for {@link RateLimitExceededException}. */
  public OptionalDouble retryAfter() {
    return retryAfter < 0 ? OptionalDouble.empty() : OptionalDouble.of(retryAfter);
  }

  /**
   * The OTP error code for {@link InvalidOtpException}: {@code invalid_otp}, {@code
   * otp1_already_verified} or {@code extra_try}; null otherwise.
   */
  public String code() {
    return code;
  }

  /** The ccxt capability name for {@link NotSupportedException}; null otherwise. */
  public String feature() {
    return feature;
  }

  BitpinException response(int status, Object body, String endpointId) {
    this.status = status;
    this.body = body;
    this.endpointId = endpointId;
    return this;
  }

  BitpinException endpoint(String endpointId) {
    this.endpointId = endpointId;
    return this;
  }

  void retryAfter(double seconds) {
    this.retryAfter = seconds;
  }

  void code(String code) {
    this.code = code;
  }

  void feature(String feature) {
    this.feature = feature;
  }
}
