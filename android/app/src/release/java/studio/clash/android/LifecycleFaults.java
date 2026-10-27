package studio.clash.android;

import android.content.Context;

/** Release builds have no fault-file reader or delayed callback thread. */
final class LifecycleFaults {
    static void pause(Context context, String stage) { }
    static void deliver(Context context, String stage, Runnable completion) { completion.run(); }
}
