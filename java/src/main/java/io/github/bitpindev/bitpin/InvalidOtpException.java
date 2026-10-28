package io.github.bitpindev.bitpin;

/** A wrong or reused withdrawal OTP; {@link #code()} says which. ccxt: {@code InvalidOTP}. */
public class InvalidOtpException extends BadRequestException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public InvalidOtpException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public InvalidOtpException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "InvalidOTP";
  }
}
