package io.github.bitpindev.bitpin;

import java.util.List;
import java.util.Map;

/** The result of a bulk cancel. */
public record CancelResult(
    List<String> canceled, List<String> notCanceled, Map<String, Object> info) {}
