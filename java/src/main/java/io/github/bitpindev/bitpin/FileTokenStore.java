package io.github.bitpindev.bitpin;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.FileAttribute;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * Keeps tokens in {@code <dir>/<key id>.json}, readable only by you (mode 0600). The default
 * directory is {@code $XDG_CACHE_HOME/bitpin-sdk} or the OS cache directory. The file format is
 * shared with the Python, TypeScript and Go SDKs.
 */
public final class FileTokenStore implements TokenStore {
  private static final Pattern KEY_ID = Pattern.compile("^[A-Za-z0-9_-]+$");
  private static final boolean POSIX =
      FileSystems.getDefault().supportedFileAttributeViews().contains("posix");

  private final Path dir;

  /** A store in the default cache directory. */
  public FileTokenStore() {
    this(defaultDir());
  }

  /** A store in {@code dir}. */
  public FileTokenStore(Path dir) {
    this.dir = dir;
  }

  /** The directory the tokens are kept in. */
  public Path dir() {
    return dir;
  }

  static Path defaultDir() {
    String xdg = System.getenv("XDG_CACHE_HOME");
    if (xdg != null && !xdg.isEmpty()) {
      return Path.of(xdg, "bitpin-sdk");
    }
    String home = System.getProperty("user.home");
    String os = System.getProperty("os.name", "").toLowerCase(Locale.ROOT);
    if (os.contains("mac")) {
      return Path.of(home, "Library", "Caches", "bitpin-sdk");
    }
    if (os.contains("win")) {
      String local = System.getenv("LOCALAPPDATA");
      return Path.of(local != null && !local.isEmpty() ? local : home, "bitpin-sdk");
    }
    return Path.of(home, ".cache", "bitpin-sdk");
  }

  private Path path(String keyId) {
    if (keyId == null || !KEY_ID.matcher(keyId).matches()) {
      throw new IllegalArgumentException("invalid key id \"" + keyId + "\"");
    }
    return dir.resolve(keyId + ".json");
  }

  @Override
  public Optional<Tokens> load(String keyId) {
    Path file = path(keyId);
    try {
      Map<String, Object> m =
          Json.asMap(Json.parse(Files.readString(file, StandardCharsets.UTF_8)));
      String access = Json.str(m.get("access"));
      String refresh = Json.str(m.get("refresh"));
      if (access.isEmpty() || refresh.isEmpty()) {
        return Optional.empty();
      }
      return Optional.of(
          new Tokens(
              access,
              refresh,
              number(m, "accessExp", "access_exp"),
              number(m, "refreshExp", "refresh_exp")));
    } catch (IOException | IllegalArgumentException e) {
      return Optional.empty(); // missing or unreadable: authenticate again
    }
  }

  // Go and TypeScript write accessExp, Python writes access_exp.
  private static double number(Map<String, Object> m, String key, String alias) {
    Object value = m.containsKey(key) ? m.get(key) : m.get(alias);
    return value instanceof Number n ? n.doubleValue() : 0;
  }

  @Override
  public void save(String keyId, Tokens tokens) {
    Path file = path(keyId);
    Map<String, Object> data = new LinkedHashMap<>();
    data.put("access", tokens.access());
    data.put("refresh", tokens.refresh());
    data.put("accessExp", tokens.accessExp());
    data.put("refreshExp", tokens.refreshExp());
    Path tmp = null;
    try {
      if (POSIX) {
        Files.createDirectories(
            dir,
            PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")));
        Files.setPosixFilePermissions(dir, PosixFilePermissions.fromString("rwx------"));
      } else {
        Files.createDirectories(dir);
      }
      FileAttribute<?>[] attrs =
          POSIX
              ? new FileAttribute<?>[] {
                PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------"))
              }
              : new FileAttribute<?>[0];
      // A unique temp file per save: several processes may save at the same time.
      tmp = Files.createTempFile(dir, "." + keyId + ".", ".tmp", attrs);
      Files.writeString(tmp, Json.write(data), StandardCharsets.UTF_8);
      try {
        Files.move(tmp, file, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
      } catch (AtomicMoveNotSupportedException e) {
        Files.move(tmp, file, StandardCopyOption.REPLACE_EXISTING);
      }
      tmp = null;
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    } finally {
      if (tmp != null) {
        try {
          Files.deleteIfExists(tmp);
        } catch (IOException ignored) {
          // best effort
        }
      }
    }
  }

  @Override
  public void clear(String keyId) {
    try {
      Files.deleteIfExists(path(keyId));
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }
}
