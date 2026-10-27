package studio.clash.android;

import android.content.Context;
import org.json.JSONObject;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/** ADB-only faults, restricted to the isolated acceptance application ID. */
final class LifecycleFaults {
    private static long delay(Context context, String stage) {
        if (!BuildConfig.APPLICATION_ID.endsWith(".acceptance")) return 0;
        try {
            File file = new File(context.getNoBackupFilesDir(), "lifecycle-fault.json");
            if (!file.isFile() || file.length() > 2048) return 0;
            JSONObject value = new JSONObject(new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8));
            return stage.equals(value.optString("stage")) ? Math.max(0, Math.min(120000, value.optLong("delay_ms"))) : 0;
        } catch (Exception ignored) { return 0; }
    }
    private static void hold(Context context, String stage, long delay) throws Exception {
        JSONObject marker = new JSONObject().put("stage", stage).put("delay_ms", delay).put("entered_at", System.currentTimeMillis());
        AtomicDocument.write(new File(context.getNoBackupFilesDir(), "lifecycle-fault-entered.json").toPath(), marker.toString());
        Thread.sleep(delay);
    }
    static void pause(Context context, String stage) throws Exception {
        long delay = delay(context, stage);
        if (delay > 0) hold(context, stage, delay);
    }
    static void deliver(Context context, String stage, Runnable completion) {
        long delay = delay(context, stage);
        if (delay == 0) { completion.run(); return; }
        Thread thread = new Thread(() -> {
            try { hold(context, stage, delay); completion.run(); }
            catch (Exception error) { Thread.currentThread().interrupt(); }
        }, "acceptance-delayed-callback");
        thread.setDaemon(true); thread.start();
    }
}
