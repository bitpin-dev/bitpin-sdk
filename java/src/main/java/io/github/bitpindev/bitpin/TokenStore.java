package io.github.bitpindev.bitpin;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.HexFormat;
import java.util.Optional;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;

/**
 * Caches tokens between clients and restarts. Authenticate allows 3 requests per minute per IP, so
 * several bots on one host should share a {@link FileTokenStore}. Implementations must be
 * thread-safe.
 */
public interface TokenStore {
  /** The tokens saved for {@code keyId}, if any. */
  Optional<Tokens> load(String keyId);

  /** Saves the tokens of {@code keyId}. */
  void save(String keyId, Tokens tokens);

  /** Forgets the tokens of {@code keyId}. */
  void clear(String keyId);

  /**
   * A stable, non-secret id for an API key: a slow PBKDF2 derivation, 16 hex characters. Every
   * language of the SDK derives the same id, so their bots can share one token file.
   */
  static String keyId(String apiKey) {
    try {
      PBEKeySpec spec =
          new PBEKeySpec(
              apiKey.toCharArray(),
              "bitpin-sdk/token-store".getBytes(StandardCharsets.UTF_8),
              100_000,
              256);
      byte[] key =
          SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded();
      spec.clearPassword();
      return HexFormat.of().formatHex(key).substring(0, 16);
    } catch (GeneralSecurityException e) {
      throw new IllegalStateException("PBKDF2WithHmacSHA256 is not available", e);
    }
  }
}
