package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.json.JsonMapper;

/**
 * JSON as plain Java values: {@code Map<String, Object>} (insertion order), {@code List<Object>},
 * {@code String}, {@code Boolean}, null, and numbers as {@code Integer}, {@code Long}, {@code
 * BigInteger} or {@code BigDecimal}, so prices keep every digit.
 */
final class Json {
  private Json() {}

  private static final JsonMapper MAPPER =
      JsonMapper.builder().enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS).build();

  /** Parses JSON text; throws {@link IllegalArgumentException} when it isn't valid. */
  static Object parse(String text) {
    try {
      return MAPPER.readValue(text, Object.class);
    } catch (JacksonException e) {
      throw new IllegalArgumentException("invalid JSON", e);
    }
  }

  /** Parses JSON bytes; throws {@link IllegalArgumentException} when they aren't valid. */
  static Object parse(byte[] data) {
    try {
      return MAPPER.readValue(data, Object.class);
    } catch (JacksonException e) {
      throw new IllegalArgumentException("invalid JSON", e);
    }
  }

  static String write(Object value) {
    return MAPPER.writeValueAsString(value);
  }

  @SuppressWarnings("unchecked")
  static Map<String, Object> asMap(Object value) {
    return value instanceof Map<?, ?> m ? (Map<String, Object>) m : Map.of();
  }

  @SuppressWarnings("unchecked")
  static List<Object> asList(Object value) {
    return value instanceof List<?> l ? (List<Object>) l : List.of();
  }

  /** A value as text: null is "", numbers are plain decimals. */
  static String str(Object value) {
    return switch (value) {
      case null -> "";
      case String s -> s;
      case BigDecimal d -> d.toPlainString();
      default -> String.valueOf(value);
    };
  }

  static boolean truthy(Object value) {
    return value instanceof Boolean b && b;
  }
}
