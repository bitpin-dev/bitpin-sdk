package io.github.bitpindev.bitpin;

/** Unknown or malformed market symbol. ccxt: {@code BadSymbol}. */
public class BadSymbolException extends BadRequestException {
  private static final long serialVersionUID = 1L;

  /** An error with a message. */
  public BadSymbolException(String message) {
    super(message);
  }

  /** An error with a message and its cause. */
  public BadSymbolException(String message, Throwable cause) {
    super(message, cause);
  }

  @Override
  public String ccxtName() {
    return "BadSymbol";
  }
}
