package io.github.bitpindev.bitpin;

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Builds exceptions from error responses, using the rules in the spec. */
final class Errors {
  private Errors() {}

  private static final Map<String, Function<String, BitpinException>> BY_NAME =
      Map.ofEntries(
          Map.entry("ExchangeError", ExchangeException::new),
          Map.entry("AuthenticationError", AuthenticationException::new),
          Map.entry("PermissionDenied", PermissionDeniedException::new),
          Map.entry("InsufficientFunds", InsufficientFundsException::new),
          Map.entry("InvalidOrder", InvalidOrderException::new),
          Map.entry("OrderNotFound", OrderNotFoundException::new),
          Map.entry("BadRequest", BadRequestException::new),
          Map.entry("BadSymbol", BadSymbolException::new),
          Map.entry("InvalidOTP", InvalidOtpException::new),
          Map.entry("NotSupported", NotSupportedException::new),
          Map.entry("NetworkError", NetworkException::new),
          Map.entry("RateLimitExceeded", RateLimitExceededException::new),
          Map.entry("RequestTimeout", RequestTimeoutException::new),
          Map.entry("ExchangeNotAvailable", ExchangeNotAvailableException::new));

  private static final Pattern RETRY_AFTER =
      Pattern.compile("(?i)available in (\\d+(?:\\.\\d+)?) second");
  private static final List<String> OTP_CODES =
      List.of("invalid_otp", "otp1_already_verified", "extra_try");

  /** Whether the spec's error rules can name {@code name}. */
  static boolean known(String name) {
    return BY_NAME.containsKey(name);
  }

  static String bodyText(Object body) {
    if (body == null) {
      return "";
    }
    if (body instanceof String s) {
      return s;
    }
    return Json.write(body);
  }

  static String detail(Object body) {
    if (body instanceof Map<?, ?> m) {
      for (String key : List.of("detail", "code", "message")) {
        if (m.get(key) instanceof String s) {
          return s;
        }
      }
    }
    String text = bodyText(body);
    return text.length() > 200 ? text.substring(0, 200) : text;
  }

  static BitpinException map(String endpointId, int status, Object body, String retryAfterHeader) {
    String text = bodyText(body).toLowerCase(Locale.ROOT);
    String name = "ExchangeError";
    for (ErrorRule rule : Spec.ERROR_RULES) {
      if (rule.status() != status) {
        continue;
      }
      if (!rule.paths().isEmpty() && rule.paths().stream().noneMatch(endpointId::startsWith)) {
        continue;
      }
      if (!rule.detail().isEmpty()
          && rule.detail().stream().noneMatch(d -> text.contains(d.toLowerCase(Locale.ROOT)))) {
        continue;
      }
      name = rule.error();
      break;
    }
    String message = status + " " + endpointId;
    String detail = detail(body);
    if (!detail.isEmpty()) {
      message += ": " + detail;
    }
    BitpinException e = BY_NAME.get(name).apply(message).response(status, body, endpointId);
    if (e instanceof RateLimitExceededException) {
      Double seconds = parseSeconds(retryAfterHeader);
      if (seconds == null) {
        Matcher m = RETRY_AFTER.matcher(bodyText(body));
        if (m.find()) {
          seconds = Double.parseDouble(m.group(1));
        }
      }
      if (seconds != null) {
        e.retryAfter(seconds);
      }
    } else if (e instanceof InvalidOtpException) {
      OTP_CODES.stream().filter(text::contains).findFirst().ifPresent(e::code);
    }
    return e;
  }

  private static Double parseSeconds(String header) {
    if (header == null || header.isBlank()) {
      return null;
    }
    try {
      double value = Double.parseDouble(header.trim());
      return Double.isFinite(value) && value >= 0 ? value : null;
    } catch (NumberFormatException e) {
      return null;
    }
  }

  /** The error for a ccxt capability Bitpin doesn't offer, in English and Persian. */
  static NotSupportedException notSupported(String feature) {
    List<String> msg = Spec.NOT_SUPPORTED.get(feature);
    NotSupportedException e = new NotSupportedException(msg.get(0) + "\n" + msg.get(1));
    e.feature(feature);
    return e;
  }
}
