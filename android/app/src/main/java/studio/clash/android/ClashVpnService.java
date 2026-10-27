package studio.clash.android;

import android.app.*;
import android.content.*;
import android.net.*;
import android.os.*;
import io.github.oviron.libmihomo.*;
import java.io.IOException;
import java.util.Locale;

/** Foreground VPN owner; mihomo takes and closes the detached TUN fd exactly once. */
public class ClashVpnService extends VpnService {
    private static final String CHANNEL = "clash_vpn";
    private static final int NOTIFICATION = 27;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private long tickUp, tickDown, tickAt;
    private final Runnable ticker = new Runnable() { @Override public void run() {
        // One hertz status-bar update: live rates plus session totals, sampled from the core counters.
        long[] totals = CoreRuntime.INSTANCE.trafficTotals();
        long now = SystemClock.elapsedRealtime();
        String text = tickAt > 0 && now > tickAt
            ? "↑ " + rate(totals[0] - tickUp, now - tickAt) + " · ↓ " + rate(totals[1] - tickDown, now - tickAt)
                + " · " + "累计 ↑ " + size(totals[0]) + " ↓ " + size(totals[1])
            : "VPN 已连接 · 正在统计流量";
        tickUp = totals[0]; tickDown = totals[1]; tickAt = now;
        getSystemService(NotificationManager.class).notify(NOTIFICATION, notification(text));
        handler.postDelayed(this, 1000);
    }};
    private static String rate(long bytes, long millis) { return size(Math.max(0, bytes * 1000 / Math.max(1, millis))) + "/s"; }
    private static String size(long bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return String.format(Locale.US, "%.1f KB", bytes / 1024.0);
        if (bytes < 1024L * 1024 * 1024) return String.format(Locale.US, "%.1f MB", bytes / 1048576.0);
        return String.format(Locale.US, "%.2f GB", bytes / 1073741824.0);
    }
    @Override public void onCreate() {
        super.onCreate(); CoreRuntime.INSTANCE.attach(this);
        getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel(CHANNEL, "VPN 连接", NotificationManager.IMPORTANCE_LOW));
    }
    @Override public int onStartCommand(Intent intent, int flags, int id) {
        if (intent != null && "stop".equals(intent.getAction())) { CoreRuntime.INSTANCE.revoked(this); return START_NOT_STICKY; }
        startForeground(NOTIFICATION, notification("正在启动 VPN…"));
        CoreRuntime.INSTANCE.accept(this, intent == null ? null : intent.getStringExtra("request"));
        return START_NOT_STICKY;
    }
    private Notification notification(String text) {
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop = PendingIntent.getService(this, 1, new Intent(this, ClashVpnService.class).setAction("stop"), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this, CHANNEL).setSmallIcon(studio.clash.android.R.drawable.ic_launcher).setContentTitle("Clash Studio VPN").setContentText(text)
            .setStyle(new Notification.BigTextStyle().bigText(text))
            .setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true).setCategory(Notification.CATEGORY_SERVICE)
            .addAction(new Notification.Action.Builder(null, "停止", stop).build()).build();
    }
    void showRunning() { tickUp = 0; tickDown = 0; tickAt = 0; handler.removeCallbacks(ticker); handler.post(ticker); }
    interface CancellationCheck { void check() throws Exception; }
    void establishTunnel(Clash core, boolean ipv6, CancellationCheck cancellation) throws Exception {
        cancellation.check();
        Builder builder = new Builder().setSession("Clash Studio").setMtu(1500).setBlocking(false)
            .addAddress("198.19.0.1", 30).addRoute("0.0.0.0", 0).addDnsServer("198.19.0.2");
        if (Build.VERSION.SDK_INT >= 29) builder.setMetered(false);
        if (ipv6) builder.addAddress("fdfe:dcba:9876::1", 126).addRoute("::", 0);
        // Keep local network devices and wireless debugging reachable on Android 13+.
        if (Build.VERSION.SDK_INT >= 33) for (String route : new String[]{"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "fe80::/10"}) {
            if (!ipv6 && route.contains(":")) continue; // Adding an IPv6 exclusion would enable IPv6 bypass.
            String[] parts = route.split("/");
            builder.excludeRoute(new IpPrefix(java.net.InetAddress.getByName(parts[0]), Integer.parseInt(parts[1])));
        }
        cancellation.check();
        ParcelFileDescriptor descriptor = builder.establish();
        if (descriptor == null) throw new IOException("VPN permission revoked");
        try { cancellation.check(); } catch (Exception error) { descriptor.close(); throw error; }
        core.startTUN(descriptor.detachFd(), new TunInterface() {
            @Override public void protect(int fd) { ClashVpnService.this.protect(fd); }
            // The bridge cannot read /proc on Android 10+, so uid arrives as -1; the public
            // socket-owner lookup plus PackageManager gives per-connection app labels.
            private final java.util.Map<Integer,String> labels = new java.util.concurrent.ConcurrentHashMap<>();
            @Override public String resolverProcess(int protocol, String source, String target, int uid) {
                if (uid <= 0) uid = ownerUid(protocol, source, target);
                String label = resolveLabel(uid);
                if (label.isEmpty()) return "";
                return label;
            }
            private String resolveLabel(int uid) {
                if (uid <= 0) return "";
                String cached = labels.get(uid);
                if (cached != null) return cached;
                String resolved = "";
                try {
                    String[] packages = getPackageManager().getPackagesForUid(uid);
                    if (packages != null && packages.length > 0) {
                        // The kernel matches PROCESS-NAME against this value. Localized labels
                        // are presentation only; a package name remains stable across locales.
                        resolved = packages[0];
                    }
                } catch (Exception ignored) { }
                labels.put(uid, resolved);
                return resolved;
            }
            private int ownerUid(int protocol, String source, String target) {
                if (Build.VERSION.SDK_INT < 29) return 0;
                try {
                    android.net.ConnectivityManager manager = getSystemService(android.net.ConnectivityManager.class);
                    java.net.InetSocketAddress local = parseAddress(source), remote = parseAddress(target);
                    if (manager == null || local == null || remote == null) return 0;
                    // getConnectionOwnerUid protocol values: TCP = 6, UDP = 17 (public constants).
                    int[] order = protocol == 17 ? new int[]{17, 6} : new int[]{6, 17};
                    for (int candidate : order) {
                        int owner = manager.getConnectionOwnerUid(candidate, local, remote);
                        if (owner > 0) return owner;
                    }
                } catch (Exception ignored) { }
                return 0;
            }
            private java.net.InetSocketAddress parseAddress(String value) {
                if (value == null) return null;
                int port = value.lastIndexOf(':');
                if (port <= 0 || port == value.length() - 1) return null;
                try {
                    String host = value.indexOf(':') != port ? value.substring(value.indexOf('[') == 0 ? 1 : 0, value.lastIndexOf(']') > 0 ? value.lastIndexOf(']') : port) : value.substring(0, port);
                    return new java.net.InetSocketAddress(java.net.InetAddress.getByName(host), Integer.parseInt(value.substring(port + 1)));
                } catch (Exception error) { return null; }
            }
        }, "ClashStudio", "gvisor", ipv6 ? "198.19.0.1/30,fdfe:dcba:9876::1/126" : "198.19.0.1/30", "198.19.0.2", 1500);
    }
    void finishService() { handler.removeCallbacks(ticker); stopForeground(STOP_FOREGROUND_REMOVE); stopSelf(); }
    @Override public void onRevoke() { CoreRuntime.INSTANCE.revoked(this); super.onRevoke(); }
    @Override public void onDestroy() { handler.removeCallbacks(ticker); CoreRuntime.INSTANCE.revoked(this); super.onDestroy(); }
}
