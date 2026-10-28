package io.github.bitpindev.bitpin;

import java.util.List;

/** Maps an error response to an exception class; the first matching rule wins. */
record ErrorRule(int status, String error, List<String> paths, List<String> detail) {}
