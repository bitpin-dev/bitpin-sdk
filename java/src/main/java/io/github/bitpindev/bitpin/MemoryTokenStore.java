package io.github.bitpindev.bitpin;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/** Keeps tokens for the life of the process (the default). */
public final class MemoryTokenStore implements TokenStore {
  private final Map<String, Tokens> tokens = new ConcurrentHashMap<>();

  /** An empty store. */
  public MemoryTokenStore() {}

  @Override
  public Optional<Tokens> load(String keyId) {
    return Optional.ofNullable(tokens.get(keyId));
  }

  @Override
  public void save(String keyId, Tokens value) {
    tokens.put(keyId, value);
  }

  @Override
  public void clear(String keyId) {
    tokens.remove(keyId);
  }
}
