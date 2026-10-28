package io.github.bitpindev.bitpin;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/** Builds the URL and JSON body of a spec endpoint. */
final class Requests {
  private Requests() {}

  private static final Pattern MISSING = Pattern.compile("\\{(\\w+)}");

  /** A request ready to send. {@code body} is JSON text or null. */
  record Built(Endpoint endpoint, String url, String body) {}

  private static boolean isNumber(Object value) {
    return value instanceof BigDecimal
        || value instanceof Double
        || value instanceof Float
        || value instanceof BigInteger
        || value instanceof Long
        || value instanceof Integer
        || value instanceof Short
        || value instanceof Byte;
  }

  static String queryValue(Object value) {
    if (value instanceof Collection<?> c) {
      return c.stream().map(Requests::queryValue).collect(Collectors.joining(","));
    }
    if (value instanceof BigDecimal || value instanceof Double || value instanceof Float) {
      return Numbers.format(value);
    }
    return String.valueOf(value);
  }

  /** Numbers become plain decimal strings; null map entries are dropped. */
  static Object bodyValue(Object value) {
    if (isNumber(value)) {
      return Numbers.format(value);
    }
    if (value instanceof Map<?, ?> m) {
      Map<String, Object> out = new LinkedHashMap<>();
      m.forEach(
          (k, v) -> {
            if (v != null) {
              out.put(String.valueOf(k), bodyValue(v));
            }
          });
      return out;
    }
    if (value instanceof Collection<?> c) {
      List<Object> out = new ArrayList<>();
      c.forEach(item -> out.add(bodyValue(item)));
      return out;
    }
    return value;
  }

  private static String encode(String s) {
    return URLEncoder.encode(s, StandardCharsets.UTF_8);
  }

  static Built build(
      Config cfg,
      String endpointId,
      Map<String, ?> pathParams,
      Map<String, ?> params,
      Object body) {
    Endpoint e = Spec.ENDPOINTS.get(endpointId);
    if (e == null) {
      throw new IllegalArgumentException("unknown endpoint " + endpointId);
    }
    String path = e.path();
    if (pathParams != null) {
      for (Map.Entry<String, ?> p : new TreeMap<String, Object>(pathParams).entrySet()) {
        path =
            path.replace(
                "{" + p.getKey() + "}", encode(String.valueOf(p.getValue())).replace("+", "%20"));
      }
    }
    Matcher m = MISSING.matcher(path);
    if (m.find()) {
      throw new IllegalArgumentException(
          "missing path parameter \"" + m.group(1) + "\" for " + endpointId);
    }
    StringBuilder url = new StringBuilder(cfg.restUrl().replaceAll("/+$", "")).append(path);
    if (params != null) {
      String query =
          new TreeMap<String, Object>(params)
              .entrySet().stream()
                  .filter(p -> p.getValue() != null)
                  .map(p -> encode(p.getKey()) + "=" + encode(queryValue(p.getValue())))
                  .collect(Collectors.joining("&"));
      if (!query.isEmpty()) {
        url.append('?').append(query);
      }
    }
    return new Built(e, url.toString(), body == null ? null : Json.write(bodyValue(body)));
  }
}
