package bitpin

import (
	"context"
	"crypto/pbkdf2"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sync"
)

// TokenStore caches tokens between clients and restarts. Authenticate allows 3 requests per
// minute per IP, so several bots on one host should share a FileTokenStore.
type TokenStore interface {
	Load(ctx context.Context, keyID string) (*Tokens, error)
	Save(ctx context.Context, keyID string, tokens Tokens) error
	Clear(ctx context.Context, keyID string) error
}

// KeyID is a stable, non-secret id for an API key: a slow PBKDF2 derivation, 16 hex characters.
func KeyID(apiKey string) string {
	key, err := pbkdf2.Key(sha256.New, apiKey, []byte("bitpin-sdk/token-store"), 100_000, 32)
	if err != nil { // only for invalid parameters, which these aren't
		panic(err)
	}
	return hex.EncodeToString(key)[:16]
}

// MemoryTokenStore keeps tokens for the life of the process (the default).
type MemoryTokenStore struct {
	mu     sync.Mutex
	tokens map[string]Tokens
}

func (m *MemoryTokenStore) Load(_ context.Context, keyID string) (*Tokens, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if t, ok := m.tokens[keyID]; ok {
		return &t, nil
	}
	return nil, nil
}

func (m *MemoryTokenStore) Save(_ context.Context, keyID string, tokens Tokens) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.tokens == nil {
		m.tokens = map[string]Tokens{}
	}
	m.tokens[keyID] = tokens
	return nil
}

func (m *MemoryTokenStore) Clear(_ context.Context, keyID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.tokens, keyID)
	return nil
}

var keyIDPattern = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

// FileTokenStore keeps tokens in <Dir>/<key id>.json with mode 0600 (default Dir:
// $XDG_CACHE_HOME/bitpin-sdk or the OS cache dir).
type FileTokenStore struct{ Dir string }

func (f FileTokenStore) dir() (string, error) {
	if f.Dir != "" {
		return f.Dir, nil
	}
	if xdg := os.Getenv("XDG_CACHE_HOME"); xdg != "" {
		return filepath.Join(xdg, "bitpin-sdk"), nil
	}
	base, err := os.UserCacheDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(base, "bitpin-sdk"), nil
}

func (f FileTokenStore) path(keyID string) (string, error) {
	if !keyIDPattern.MatchString(keyID) {
		return "", fmt.Errorf("invalid key id %q", keyID)
	}
	dir, err := f.dir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, keyID+".json"), nil
}

func (f FileTokenStore) Load(_ context.Context, keyID string) (*Tokens, error) {
	path, err := f.path(keyID)
	if err != nil {
		return nil, err
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, nil // missing or unreadable: authenticate again
	}
	var t Tokens
	if json.Unmarshal(data, &t) != nil || t.Access == "" || t.Refresh == "" {
		return nil, nil
	}
	return &t, nil
}

func (f FileTokenStore) Save(_ context.Context, keyID string, tokens Tokens) error {
	path, err := f.path(keyID)
	if err != nil {
		return err
	}
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	_ = os.Chmod(dir, 0o700)
	// A unique temp file per save: several processes may save at the same time.
	tmp, err := os.CreateTemp(dir, "."+keyID+".*.tmp")
	if err != nil {
		return err
	}
	data, _ := json.Marshal(tokens)
	_, werr := tmp.Write(data)
	cerr := tmp.Close()
	if err := errors.Join(werr, cerr); err != nil {
		_ = os.Remove(tmp.Name())
		return err
	}
	if err := os.Rename(tmp.Name(), path); err != nil {
		_ = os.Remove(tmp.Name())
		return err
	}
	return nil
}

func (f FileTokenStore) Clear(_ context.Context, keyID string) error {
	path, err := f.path(keyID)
	if err != nil {
		return err
	}
	if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return nil
}
