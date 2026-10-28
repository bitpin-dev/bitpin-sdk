package io.github.bitpindev.bitpin;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/** The shared fixtures in ../fixtures, one synthetic response per endpoint. */
final class Fixtures {
  private Fixtures() {}

  static final Path DIR = Path.of("..", "fixtures");

  static String read(String name) {
    try {
      return Files.readString(DIR.resolve(name), StandardCharsets.UTF_8);
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }

  static int status(String endpointId) {
    return ((Number) Json.asMap(Json.parse(read(endpointId + ".json"))).get("status")).intValue();
  }

  static Object body(String endpointId) {
    return Json.asMap(Json.parse(read(endpointId + ".json"))).get("body");
  }
}
