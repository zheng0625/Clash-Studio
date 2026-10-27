package studio.clash.android;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.LongSupplier;

/** Pure lifecycle ticket: deadlines and cancellation are checked at every native boundary. */
final class LifecycleOperation {
    final String id;
    private final long deadline;
    private final LongSupplier clock;
    private final long started;
    private long phaseAt;
    private String phase = "accepted";
    private final java.util.Map<String, Long> timings = new java.util.LinkedHashMap<>();
    private final AtomicBoolean cancelled = new AtomicBoolean();
    LifecycleOperation(String id, long timeoutNanos) { this(id, timeoutNanos, System::nanoTime); }
    LifecycleOperation(String id, long timeoutNanos, LongSupplier clock) { this.id = id; this.clock = clock; this.started = clock.getAsLong(); this.phaseAt = started; this.deadline = started + timeoutNanos; }
    synchronized void phase(String next) {
        long now = clock.getAsLong();
        timings.put(phase, timings.getOrDefault(phase, 0L) + Math.max(0, now - phaseAt));
        phaseAt = now; phase = next;
    }
    synchronized org.json.JSONObject snapshot() throws org.json.JSONException {
        org.json.JSONObject durations = new org.json.JSONObject();
        for (java.util.Map.Entry<String, Long> item : timings.entrySet()) durations.put(item.getKey(), item.getValue() / 1_000_000.0);
        return new org.json.JSONObject().put("operation_id", id).put("phase", phase).put("phase_ms", durations)
            .put("elapsed_ms", (clock.getAsLong()-started)/1_000_000.0).put("cancel_requested", !valid());
    }
    void cancel() { cancelled.set(true); }
    boolean valid() { return !cancelled.get() && clock.getAsLong() < deadline; }
    void check() throws ProfileStore.Failure { if (!valid()) throw new ProfileStore.Failure(409, "生命周期操作已取消或超时", "OPERATION_CANCELLED"); }
}
