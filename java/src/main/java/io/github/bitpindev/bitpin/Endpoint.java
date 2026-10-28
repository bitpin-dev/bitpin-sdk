package io.github.bitpindev.bitpin;

import java.util.List;

/** One endpoint of the spec. */
record Endpoint(
    String id, String method, String path, String auth, List<String> buckets, boolean idempotent) {}
