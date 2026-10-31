package studio.clash.android;

import android.content.*;
import android.net.VpnService;
import android.os.Build;
import io.github.oviron.libmihomo.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicBoolean;

/** A single serialized owner for the native core and VPN descriptor. */
final class CoreRuntime {
    static final CoreRuntime INSTANCE = new CoreRuntime();
    private final ThreadPoolExecutor lifecycle = new ThreadPoolExecutor(1, 1, 0, TimeUnit.SECONDS, new ArrayBlockingQueue<>(16), new ThreadPoolExecutor.AbortPolicy());
    private final ConcurrentHashMap<String, Pending> pending = new ConcurrentHashMap<>();
    private final AtomicBoolean applying = new AtomicBoolean();
    private final java.util.concurrent.atomic.AtomicLong startEpoch = new java.util.concurrent.atomic.AtomicLong();
    long startEpoch() { return startEpoch.get(); }
    private volatile JSONObject lastOperation;
    private volatile Pending currentApply;
    private final ThreadLocal<Pending> activation = new ThreadLocal<>();
    private final java.util.concurrent.atomic.AtomicLong egressVersion = new java.util.concurrent.atomic.AtomicLong();
    private volatile String proxySignature = "";
    private volatile JSONObject connectionSample;
    private volatile long connectionAt;
    private volatile String connectionSession = "";
    private volatile long lastUpload, lastDownload;
    private final ScheduledExecutorService idleStop = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread thread = new Thread(r, "clash-probe-idle"); thread.setDaemon(true); return thread;
    });
    private final AtomicInteger probing = new AtomicInteger();
    private volatile ScheduledFuture<?> probeStop;
    private volatile String probeKey = "";
    private volatile String probeProfile = "";
    private volatile int probeRevision;
    private volatile int generation;
    private volatile Context context;
    private volatile JSONObject active;
    private volatile String phase = "stopped", lastError = "", session = "", mode = "rule";
    private volatile ClashVpnService service;
    private volatile boolean loaded;
    private final Clash core = Clash.INSTANCE;
    private static final class Pending {
        final JSONObject body; final CompletableFuture<JSONObject> result = new CompletableFuture<>();
        final LifecycleOperation operation = new LifecycleOperation(UUID.randomUUID().toString(), TimeUnit.SECONDS.toNanos(90));
        final AtomicBoolean accepted = new AtomicBoolean();
        Pending(JSONObject body) { this.body = body; }
    }
    void attach(Context context) { this.context = context.getApplicationContext(); }
    boolean available() { return context != null && Arrays.asList(Build.SUPPORTED_ABIS).contains("arm64-v8a"); }
    private void load() throws Exception {
        if (loaded) return;
        core.load(context.getApplicationInfo().nativeLibraryDir);
        try { core.assertReady(); } catch (Throwable error) { throw new ProfileStore.Failure(503, "ARM64 内核加载失败，请重新安装完整 APK"); }
        loaded = true;
        action("setLogcatLevel", "warning");
        // The bridge reports TUN creation failures through the log event channel.
        core.setEventListener((InvokeInterface) raw -> {
            if (raw != null && raw.contains("TUN start failed")) {
                lastError = "VPN 数据接口创建失败，请停止后重试";
                lifecycle.execute(() -> { try { shutdown(service); } catch (Exception ignored) { } });
            }
        });
        action("startLog", "");
    }
    private void checkActivation() throws Exception {
        Pending request = activation.get();
        if (request != null) {
            request.operation.check();
            if (currentApply != request) throw new ProfileStore.Failure(409, "生命周期操作已被替换");
        }
    }
    void cancelStart() {
        startEpoch.incrementAndGet();
        Pending request = currentApply;
        if (request != null) { request.operation.cancel(); request.result.cancel(false); }
    }
    Object action(String method, Object data) throws Exception {
        checkActivation();
        Pending ticket = activation.get();
        if (ticket != null) ticket.operation.phase("native:" + method);
        CompletableFuture<String> reply = new CompletableFuture<>();
        core.invokeAction(new JSONObject().put("id", UUID.randomUUID().toString()).put("method", method).put("data", data).toString(),
            (InvokeInterface) raw -> { if (ticket == null) reply.complete(raw); else LifecycleFaults.deliver(context, "native:" + method, () -> reply.complete(raw)); });
        JSONObject result;
        try { result = new JSONObject(reply.get(30, TimeUnit.SECONDS)); }
        catch (TimeoutException error) { throw new ProfileStore.Failure(504, "原生操作超时，结果未提交"); }
        checkActivation();
        if (result.optInt("code", -1) != 0) throw new ProfileStore.Failure(422, "内核未接受此操作，请检查配置和节点");
        return result.opt("data");
    }
    private void checkedAction(String method, JSONObject data) throws Exception {
        Object result = action(method, data.toString());
        if (result instanceof String && !((String)result).isEmpty()) throw new ProfileStore.Failure(422, "内核配置校验失败，请检查节点协议、规则与 Provider");
    }
    private JSONObject objectAction(String method) throws Exception {
        Object value = action(method, "");
        return value instanceof JSONObject ? (JSONObject)value : new JSONObject(String.valueOf(value));
    }
    JSONObject apply(JSONObject body) throws Exception {
        if (!available()) throw new ProfileStore.Failure(503, "此构建需要 ARM64 安卓设备");
        if (VpnService.prepare(context) != null) throw new ProfileStore.Failure(428, "请先确认 Android 系统 VPN 授权");
        Pending request = new Pending(ConfigEngine.copy(body)); String key = UUID.randomUUID().toString();
        if (!applying.compareAndSet(false, true)) throw new ProfileStore.Failure(409, "VPN 正在启动，请稍后重试");
        currentApply = request;
        pending.put(key, request);
        try {
            context.startForegroundService(new Intent(context, ClashVpnService.class).putExtra("request", key));
            return request.result.get(90, TimeUnit.SECONDS);
        } catch (TimeoutException error) {
            request.operation.cancel(); request.result.cancel(false);
            throw new ProfileStore.Failure(504, "VPN 启动超时，请检查网络和配置后重试");
        } catch (CancellationException error) {
            throw new ProfileStore.Failure(409, "VPN 启动已取消，正在清理资源");
        } catch (InterruptedException error) {
            request.operation.cancel(); request.result.cancel(false); Thread.currentThread().interrupt();
            throw new ProfileStore.Failure(409, "VPN 启动已取消");
        } catch (ExecutionException error) {
            if (error.getCause() instanceof Exception) throw (Exception)error.getCause();
            throw error;
        } finally {
            pending.remove(key);
            if (!request.accepted.get()) {
                request.operation.cancel();
                lifecycle.execute(() -> { if (currentApply == request) { currentApply = null; applying.set(false); } });
            }
        }
    }
    void accept(ClashVpnService owner, String key) {
        Pending request = key == null ? null : pending.get(key);
        if (request == null || !request.accepted.compareAndSet(false, true)) { owner.stopSelf(); return; }
        lifecycle.execute(() -> {
            activation.set(request);
            try { JSONObject result = activate(owner, request); checkActivation(); if (!request.result.complete(result)) throw new ProfileStore.Failure(409, "启动结果已过期"); }
            catch (Exception error) {
                if (BuildConfig.DEBUG) android.util.Log.e("ClashStudioCore", error.getClass().getSimpleName() + " " + Arrays.toString(error.getStackTrace()));
                lastError = error instanceof ProfileStore.Failure ? error.getMessage() : "VPN 启动失败，请检查网络和配置后重试";
                activation.remove();
                try { shutdown(owner); } catch (Exception ignored) { }
                request.result.completeExceptionally(new ProfileStore.Failure(error instanceof ProfileStore.Failure ? ((ProfileStore.Failure)error).status : 422, lastError));
            } finally {
                activation.remove();
                request.operation.phase(request.result.isCancelled() ? "cancelled" : request.result.isCompletedExceptionally() ? "failed" : "succeeded");
                try { lastOperation = request.operation.snapshot().put("profile_revision", request.body.optInt("profile_revision")).put("workspace_revision", request.body.optInt("workspace_revision")); } catch (Exception ignored) { }
                if (currentApply == request) { currentApply = null; applying.set(false); }
            }
        });
    }
    private JSONObject activate(ClashVpnService owner, Pending request) throws Exception {
        JSONObject body = request.body;
        request.operation.phase("preparing");
        checkActivation();
        NativeApi api = NativeApi.open(context.getNoBackupFilesDir());
        JSONObject profile = api.store.get(body.getString("profile_id"));
        JSONObject preview = api.preview(profile.getString("id"));
        if (profile.getInt("revision") != body.getInt("profile_revision") || body.getInt("workspace_revision") != preview.getInt("workspace_revision")) throw new ProfileStore.Failure(409, "配置版本已改变，请刷新后应用");
        if (preview.getJSONArray("errors").length() != 0) throw new ProfileStore.Failure(422, "请先解决配置错误");
        int port = body.getInt("mixed_port");
        JSONObject settings = api.store.settings();
        JSONObject config = CoreConfig.prepare(preview.getJSONObject("config"), settings, port);
        // Per-connection app labels come from the TUN uid resolver; only the VPN core enables it.
        config.put("find-process-mode", "always");
        ClashVpnService previous = service; service = null;
        shutdown(null);
        if (previous != null && previous != owner) previous.finishService();
        service = owner; phase = "starting"; lastError = "";
        abandonProbe();
        load();
        try (java.net.ServerSocket reservation = new java.net.ServerSocket()) {
            reservation.bind(new java.net.InetSocketAddress("127.0.0.1", port));
        } catch (IOException error) { throw new ProfileStore.Failure(409, "代理端口已被占用，请更换端口"); }
        File home = new File(context.getNoBackupFilesDir(), "mihomo");
        if (!home.isDirectory() && !home.mkdirs()) throw new IOException("core directory");
        Files.write(new File(home, "config.yaml").toPath(), ConfigEngine.dump(config).getBytes(StandardCharsets.UTF_8));
        JSONObject selections = new JSONObject(), proxies = api.store.catalog(profile.getString("id")).getJSONObject("proxies");
        for (String name : ConfigEngine.keys(proxies)) { JSONObject proxy = proxies.getJSONObject(name); if (proxy.optString("type").equals("Selector")) selections.put(name, proxy.optString("now")); }
        String global = api.store.selections(profile.getString("id")).optString("GLOBAL");
        if (proxies.has(global)) selections.put("GLOBAL", global);
        CompletableFuture<String> setup = new CompletableFuture<>();
        core.quickSetup(new JSONObject().put("home-dir", home.getAbsolutePath()).put("version", Build.VERSION.SDK_INT).toString(),
            new JSONObject().put("selected-map", selections).toString(), (InvokeInterface) setup::complete);
        String failure;
        try { failure = setup.get(30, TimeUnit.SECONDS); }
        catch (TimeoutException error) { throw new ProfileStore.Failure(504, "内核准备超时，结果未提交"); }
        LifecycleFaults.pause(context, "after-quick-setup");
        checkActivation();
        if (failure != null && !failure.isEmpty()) throw new ProfileStore.Failure(422, "Mihomo 校验未通过，请检查节点协议、规则或地理数据下载");
        checkActivation();
        JSONObject saved = api.store.selections(profile.getString("id"));
        JSONObject actual = objectAction("getProxies").getJSONObject("proxies");
        for (String name : ConfigEngine.keys(saved)) {
            JSONObject group = actual.optJSONObject(name);
            if (group != null && group.optString("type").equals("Selector") && ConfigEngine.strings(group.getJSONArray("all")).contains(saved.getString(name)))
                checkedAction("changeProxy", new JSONObject().put("group-name", name).put("proxy-name", saved.getString(name)));
        }
        LifecycleFaults.pause(context, "after-selector-restore");
        checkActivation();
        // Confirm a listener exists: native configuration application can log a bind error.
        try (java.net.Socket probe = new java.net.Socket()) { probe.connect(new java.net.InetSocketAddress("127.0.0.1", port), 2000); }
        action("closeAllConnections", ""); action("resetTraffic", "");
        checkActivation();
        request.operation.phase("establishing-vpn");
        LifecycleFaults.pause(context, "before-tunnel");
        checkActivation();
        owner.establishTunnel(core, settings.optBoolean("ipv6", true), this::checkActivation);
        checkActivation();
        if (!lastError.isEmpty()) throw new ProfileStore.Failure(422, lastError);
        if (api.store.get(profile.getString("id")).getInt("revision") != profile.getInt("revision") || api.routing.revision() != preview.getInt("workspace_revision")) throw new ProfileStore.Failure(409, "启动期间配置已改变");
        checkActivation();
        request.operation.phase("committing");
        active = new JSONObject().put("profile_id", profile.getString("id")).put("title", profile.getString("title"))
            .put("revision", profile.getInt("revision")).put("workspace_revision", preview.getInt("workspace_revision")).put("mixed_port", port)
            .put("hash", UUID.randomUUID().toString()).put("tun", false).put("vpn", true);
        mode = config.getString("mode"); session = UUID.randomUUID().toString(); phase = "running";
        checkActivation(); egressVersion.incrementAndGet(); connectionAt = 0;
        owner.showRunning(); return status();
    }
    private void shutdown(ClashVpnService owner) throws Exception {
        phase = "stopping";
        try {
            if (loaded) {
                if (active != null) try { JSONObject totals = new JSONObject(core.getTotalTraffic()); lastUpload = totals.optLong("up"); lastDownload = totals.optLong("down"); } catch (Exception ignored) { }
                closeNativeListeners();
            }
        } finally {
            abandonProbe(); active = null; phase = "stopped"; egressVersion.incrementAndGet(); connectionAt = 0;
            ClashVpnService previous = service; service = null;
            if (owner != null) owner.finishService();
            if (previous != null && previous != owner) previous.finishService();
        }
    }
    JSONObject stop() throws Exception {
        cancelStart();
        java.util.List<Runnable> obsolete = new java.util.ArrayList<>();
        lifecycle.getQueue().drainTo(obsolete);
        for (Runnable task : obsolete) if (task instanceof Future<?>) ((Future<?>)task).cancel(false);
        return lifecycle.submit(() -> { try { shutdown(service); lastError = ""; return status(); } finally { if (currentApply != null && !currentApply.operation.valid()) { currentApply = null; applying.set(false); } } }).get(35, TimeUnit.SECONDS);
    }
    private void closeNativeListeners() throws Exception {
        // Upstream stopListener only calls listener.Cleanup(), which closes TUN,
        // not the mixed listener. Reconcile zero ports before stopping it.
        try {
            action("updateConfig", new JSONObject().put("mixed-port", 0).toString());
            action("startListener", "");
        } finally {
            try { core.stopTun(); }
            finally { action("closeAllConnections", ""); }
        }
    }
    void revoked(ClashVpnService owner) {
        // finishService() schedules onDestroy after shutdown has relinquished
        // ownership. That callback must not cancel this result or a newer start.
        if (service != owner) return;
        cancelStart();
        lifecycle.execute(() -> { if (service == owner) { try { shutdown(owner); } catch (Exception ignored) { } } });
    }
    boolean matches(String id, int revision) { JSONObject value = active; return value != null && value.optString("profile_id").equals(id) && value.optInt("revision") == revision; }
    boolean uses(String id) { JSONObject value = active; return value != null && value.optString("profile_id").equals(id); }
    JSONObject status() throws Exception {
        JSONObject value = active;
        Pending ticket = currentApply;
        JSONObject operation = ticket == null ? lastOperation : ticket.operation.snapshot();
        return new JSONObject().put("operation", operation == null ? JSONObject.NULL : ConfigEngine.copy(operation)).put("lifecycle_queued", lifecycle.getQueue().size()).put("running", phase.equals("running")).put("installed", available()).put("active", value == null ? JSONObject.NULL : ConfigEngine.copy(value))
            .put("phase", phase).put("sampled_at", Instant.now().toString()).put("operation_id", currentApply == null ? JSONObject.NULL : currentApply.operation.id).put("cancel_requested", currentApply != null && !currentApply.operation.valid()).put("egress_version", egressVersion.get()).put("routing_mode", mode).put("vpn", new JSONObject().put("supported", available()).put("enabled", phase.equals("running")).put("stack", "gvisor"))
            .put("proxy", new JSONObject().put("supported", false).put("owned", false))
            .put("tun", new JSONObject().put("supported", false).put("enabled", false).put("admin", false).put("stack", "mixed").put("conflicts", new JSONArray()))
            .put("events", lastError.isEmpty() ? new JSONArray() : new JSONArray().put(new JSONObject().put("time", Instant.now().toString()).put("message", lastError)));
    }
    JSONObject proxies() throws Exception {
        if (active == null) return new JSONObject().put("proxies", new JSONObject());
        JSONObject result = objectAction("getProxies");
        JSONObject groups = result.getJSONObject("proxies"); java.util.List<String> selected = new java.util.ArrayList<>();
        for (String name : ConfigEngine.keys(groups)) if (groups.getJSONObject(name).has("now")) selected.add(name + "=" + groups.getJSONObject(name).optString("now"));
        java.util.Collections.sort(selected); String signature = selected.toString();
        synchronized (this) { if (!proxySignature.isEmpty() && !proxySignature.equals(signature)) egressVersion.incrementAndGet(); proxySignature = signature; }
        return result;
    }
    synchronized JSONObject connections() throws Exception {
        if (active == null) return new JSONObject().put("connections", new JSONArray()).put("uploadTotal", 0).put("downloadTotal", 0).put("sampled_at", Instant.now().toString()).put("session", session);
        String captured = session; long now = System.nanoTime();
        if (connectionSample != null && connectionSession.equals(captured) && now - connectionAt < TimeUnit.MILLISECONDS.toNanos(900)) return ConfigEngine.copy(connectionSample);
        JSONObject result = objectAction("getConnections");
        if (!captured.equals(session) || active == null) throw new ProfileStore.Failure(409, "连接所属会话已结束");
        result.put("sampled_at", Instant.now().toString()).put("session", captured).put("stale", false);
        connectionSample = ConfigEngine.copy(result); connectionSession = captured; connectionAt = System.nanoTime(); return result;
    }
    JSONObject traffic() throws Exception {
        JSONObject totals = loaded && active != null ? new JSONObject(core.getTotalTraffic()) : new JSONObject().put("up", lastUpload).put("down", lastDownload);
        JSONObject sample = active == null ? null : connections();
        JSONArray entries = sample == null ? null : sample.optJSONArray("connections");
        return new JSONObject().put("running", phase.equals("running")).put("session", session).put("upload", totals.optLong("up")).put("download", totals.optLong("down"))
            .put("connections", entries == null ? 0 : entries.length()).put("sampled_at", sample == null ? Instant.now().toString() : sample.get("sampled_at")).put("stale", false);
    }
    JSONObject routing(String next) throws Exception {
        if (!Arrays.asList("rule", "global", "direct").contains(next)) throw new ProfileStore.Failure(422, "分流模式无效");
        return lifecycle.submit(() -> { if (active == null) throw new ProfileStore.Failure(409, "请先启动 VPN"); checkedAction("updateConfig", new JSONObject().put("mode", next)); mode = next; egressVersion.incrementAndGet(); return status(); }).get(35, TimeUnit.SECONDS);
    }
    void select(JSONObject body) throws Exception {
        lifecycle.submit(() -> {
            if (!matches(body.getString("profile_id"), body.getInt("profile_revision"))) throw new ProfileStore.Failure(409, "运行配置已改变，请重新应用后选择节点");
            checkedAction("changeProxy", new JSONObject().put("group-name", body.getString("group")).put("proxy-name", body.getString("name"))); egressVersion.incrementAndGet(); return null;
        }).get(35, TimeUnit.SECONDS);
    }
    void close(String id) throws Exception { if (active != null) { action("closeConnection", id); connectionAt = 0; } }

    JSONObject prepareProbe(JSONObject body) throws Exception {
        if (!available()) throw new ProfileStore.Failure(503, "此构建需要 ARM64 安卓设备");
        return lifecycle.submit(() -> {
            String id = body.getString("profile_id");
            NativeApi api = NativeApi.open(context.getNoBackupFilesDir());
            JSONObject profile = api.store.get(id);
            if (active != null) {
                if (!matches(id, profile.getInt("revision"))) throw new ProfileStore.Failure(409, "请先停止 VPN 或切换到正在运行的订阅");
            } else {
                JSONObject preview = profile.getJSONObject("preview");
                if (preview.getJSONArray("errors").length() > 0) throw new ProfileStore.Failure(422, "请先解决配置错误");
                ensureProbe(api, preview.getJSONObject("config")); probeProfile = id; probeRevision = profile.getInt("revision");
            }
            return new JSONObject().put("ready", true);
        }).get(45, TimeUnit.SECONDS);
    }
    JSONObject selectionCatalog(String id, int revision) throws Exception {
        if (matches(id, revision) || (!probeKey.isEmpty() && probeProfile.equals(id) && probeRevision == revision)) return objectAction("getProxies").getJSONObject("proxies");
        return null;
    }

    /** HTTP delay probes: live against the running VPN core, else an on-demand loopback probe core. */
    JSONObject delay(JSONObject body) throws Exception {
        if (!available()) throw new ProfileStore.Failure(503, "此构建需要 ARM64 安卓设备");
        final String name = body.getString("name");
        if (name.isEmpty() || name.length() > 200) throw new ProfileStore.Failure(422, "节点名称无效");
        final String endpoint = body.optString("endpoint", "cloudflare");
        final String url = DelaySpec.url(endpoint);
        final int timeoutMs = DelaySpec.timeout(body.optInt("timeout_ms", 5000));
        if (probing.incrementAndGet() > 4) { probing.decrementAndGet(); throw new ProfileStore.Failure(429, "已有四个节点正在测速，请稍后重试"); }
        try {
            final String profileId = body.optString("profile_id", "");
            final int revision = body.optInt("profile_revision", -1);
            if (!profileId.isEmpty() && (revision <= 0 || body.optInt("workspace_revision", 1) != NativeApi.open(context.getNoBackupFilesDir()).routing.revision()))
                throw new ProfileStore.Failure(409, "节点配置已变化，请刷新节点列表后重新测速");
            DelayTask task = lifecycle.submit(() -> prepareDelay(profileId, revision, name)).get(45, TimeUnit.SECONDS);
            int measured = probeDelay(name, url, timeoutMs);
            if (task.generation != generation) throw new ProfileStore.Failure(409, "测速期间内核已重启或停止，请重新测速");
            touchProbe();
            return DelaySpec.result(name, endpoint, timeoutMs, measured, Instant.now());
        } catch (ExecutionException error) {
            if (error.getCause() instanceof Exception) throw (Exception)error.getCause();
            throw error;
        } finally { probing.decrementAndGet(); }
    }
    private static final class DelayTask {
        final int generation;
        DelayTask(int generation) { this.generation = generation; }
    }
    private DelayTask prepareDelay(String profileId, int revision, String name) throws Exception {
        if (active != null) {
            if (!profileId.isEmpty() && !matches(profileId, revision)) throw new ProfileStore.Failure(409, "VPN 正在运行其他订阅或配置已更新，请刷新节点列表或先停止 VPN");
            verifyProbeNode(name);
            return new DelayTask(generation);
        }
        if (profileId.isEmpty()) throw new ProfileStore.Failure(409, "请先启动 VPN，再进行节点测速");
        NativeApi api = NativeApi.open(context.getNoBackupFilesDir());
        JSONObject profile = api.store.get(profileId);
        if (profile.getInt("revision") != revision) throw new ProfileStore.Failure(409, "节点配置已变化，请刷新节点列表后重新测速");
        JSONObject preview = profile.getJSONObject("preview");
        if (preview.getJSONArray("errors").length() != 0) throw new ProfileStore.Failure(422, "请先解决配置错误，再进行节点测速");
        ensureProbe(api, preview.getJSONObject("config"));
        probeProfile = profileId; probeRevision = revision;
        verifyProbeNode(name);
        return new DelayTask(generation);
    }
    private void verifyProbeNode(String name) throws Exception {
        JSONObject node = objectAction("getProxies").getJSONObject("proxies").optJSONObject(name);
        if (node == null) throw new ProfileStore.Failure(404, "节点已不在运行配置中，请刷新代理页面");
        if (!DelaySpec.measurable(node)) throw new ProfileStore.Failure(422, "请选择实际代理节点测速");
    }
    /** Starts or reuses a listener-only core with the published config; the VPN core owns this process, so probing waits for it. */
    private void ensureProbe(NativeApi api, JSONObject config) throws Exception {
        JSONObject settings = api.store.settings();
        // Fingerprint the effective probe configuration, including protected DNS.
        // Use a stable placeholder; the actual ephemeral port is assigned below.
        JSONObject probe = CoreConfig.prepare(config, settings, 17890);
        DelaySpec.sanitize(probe);
        String key = DelaySpec.configurationKey(probe);
        if (!probeKey.isEmpty() && probeKey.equals(key)) { touchProbe(); return; }
        abandonProbe();
        load();
        int port;
        try (java.net.ServerSocket socket = new java.net.ServerSocket(0, 1, java.net.InetAddress.getByName("127.0.0.1"))) { port = socket.getLocalPort(); }
        probe.put("mixed-port", port);
        File home = new File(context.getNoBackupFilesDir(), "mihomo");
        if (!home.isDirectory() && !home.mkdirs()) throw new IOException("core directory");
        Files.write(new File(home, "config.yaml").toPath(), ConfigEngine.dump(probe).getBytes(StandardCharsets.UTF_8));
        CompletableFuture<String> setup = new CompletableFuture<>();
        core.quickSetup(new JSONObject().put("home-dir", home.getAbsolutePath()).put("version", Build.VERSION.SDK_INT).toString(),
            new JSONObject().put("selected-map", new JSONObject()).toString(), (InvokeInterface) setup::complete);
        String failure = setup.get(30, TimeUnit.SECONDS);
        if (failure != null && !failure.isEmpty()) {
            closeNativeListeners(); abandonProbe();
            throw new ProfileStore.Failure(422, "测速内核启动失败，请检查节点与 DNS 配置后重试");
        }
        probeKey = key;
        touchProbe();
    }
    private int probeDelay(String name, String url, int timeoutMs) throws Exception {
        CompletableFuture<String> reply = new CompletableFuture<>();
        core.invokeAction(new JSONObject().put("id", UUID.randomUUID().toString()).put("method", "testDelay")
            .put("data", new JSONObject().put("proxy-name", name).put("test-url", url).put("timeout", timeoutMs).toString()).toString(),
            (InvokeInterface) reply::complete);
        JSONObject result = new JSONObject(reply.get(timeoutMs + 25_000L, TimeUnit.MILLISECONDS));
        if (result.optInt("code", -1) != 0) throw new ProfileStore.Failure(422, "内核未接受测速请求，请稍后重试");
        Object data = result.opt("data");
        return data instanceof Number ? ((Number)data).intValue() : Integer.parseInt(String.valueOf(data));
    }
    private synchronized void touchProbe() {
        ScheduledFuture<?> previous = probeStop;
        if (previous != null) previous.cancel(false);
        probeStop = idleStop.schedule(() -> lifecycle.execute(() -> {
            if (probeKey.isEmpty() || active != null || probing.get() > 0) return;
            try { closeNativeListeners(); } catch (Exception ignored) { }
            abandonProbe();
        }), 120, TimeUnit.SECONDS);
    }
    /** Drops probe-core ownership without core calls; the next quickSetup replaces the configuration. */
    private synchronized void abandonProbe() {
        ScheduledFuture<?> previous = probeStop;
        if (previous != null) { previous.cancel(false); probeStop = null; }
        probeKey = "";
        probeProfile = ""; probeRevision = 0;
        generation++;
    }
    private final Object lookupLock = new Object();
    private final Map<String, CompletableFuture<JSONObject>> lookups = new HashMap<>();
    private String lookupKey = "";
    private long lookupAt;
    private JSONObject lookupResult;
    JSONObject lookup(String route, boolean refresh) throws Exception {
        if (!Arrays.asList("system", "proxy").contains(route)) throw new ProfileStore.Failure(422, "检测路径无效");
        JSONObject running = active;
        if (route.equals("proxy") && running == null) throw new ProfileStore.Failure(409, "请先启动 VPN");
        String hash = running == null ? "" : running.optString("hash");
        if (active != null) proxies();
        long capturedEgress = egressVersion.get();
        String identity = route + "|" + hash + "|" + session + "|" + mode + "|" + capturedEgress;
        CompletableFuture<JSONObject> future;
        boolean owner;
        synchronized (lookupLock) {
            if (lookupResult != null && lookupKey.equals(identity)) {
                long age = (System.nanoTime() - lookupAt) / 1_000_000;
                long limit = refresh ? 0 : ("unavailable".equals(lookupResult.optString("status")) ? 10000 : 60000);
                if (age >= 0 && age < limit) return ConfigEngine.copy(lookupResult).put("cached", true);
            }
            future = lookups.get(identity);
            owner = future == null;
            if (owner) { future = new CompletableFuture<>(); lookups.put(identity, future); }
        }
        if (!owner) return ConfigEngine.copy(future.get(45, TimeUnit.SECONDS));
        try {
            JSONObject result = lookupExternal(route, running, hash, capturedEgress);
            synchronized (lookupLock) { lookupKey = identity; lookupAt = System.nanoTime(); lookupResult = ConfigEngine.copy(result); }
            future.complete(result);
            return ConfigEngine.copy(result);
        } catch (Exception error) { future.completeExceptionally(error); throw error; }
        finally { synchronized (lookupLock) { lookups.remove(identity); } }
    }
    private JSONObject lookupExternal(String route, JSONObject running, String hash, long capturedEgress) throws Exception {
        java.net.Proxy proxy = route.equals("proxy") ? new java.net.Proxy(java.net.Proxy.Type.HTTP,
            new java.net.InetSocketAddress("127.0.0.1", running.getInt("mixed_port"))) : java.net.Proxy.NO_PROXY;
        long started = System.nanoTime();
        JSONObject result = new JSONObject().put("status", "unavailable").put("ip", "").put("country", "").put("region", "")
            .put("city", "").put("isp", "").put("asn", "").put("family", "").put("provider", "").put("route", route)
            .put("route_label", route.equals("proxy") ? "本程序代理 · 按当前规则分流" : "系统路由 · 不使用应用代理设置")
            .put("profile", route.equals("proxy") ? running.optString("title", "") : "").put("cached", false)
            .put("message", "检测服务暂不可达，无法据此判断整机是否断网");
        try {
            JSONObject value = fetchLookup("https://ipwho.is/?lang=zh-CN", proxy);
            if (!value.optBoolean("success")) throw new IOException("lookup rejected");
            String ip = value.optString("ip", "");
            if (!ip.matches("[0-9a-fA-F:.]{3,45}")) throw new IOException("lookup response");
            JSONObject connection = value.optJSONObject("connection");
            if (connection == null) connection = new JSONObject();
            result.put("status", "ok").put("ip", ip).put("family", ip.contains(":") ? "IPv6" : "IPv4").put("provider", "ipwho.is")
                .put("country", clip(value.optString("country"), 100)).put("region", clip(value.optString("region"), 100))
                .put("city", clip(value.optString("city"), 100))
                .put("isp", clip(connection.optString("isp", connection.optString("org", "")), 160))
                .put("asn", clip(connection.optString("asn", ""), 30))
                .put("message", "检测服务可达；位置为 IP 数据库近似归属地");
        } catch (Exception primaryError) {
            // A location-provider failure must not be reported as a general network outage.
            try {
                JSONObject value = fetchLookup("https://api.ipify.org?format=json", proxy);
                String ip = value.optString("ip", "");
                if (!ip.matches("[0-9a-fA-F:.]{3,45}")) throw new IOException("probe response");
                result.put("status", "partial").put("ip", ip).put("family", ip.contains(":") ? "IPv6" : "IPv4")
                    .put("provider", "ipify").put("message", "公网 IP 已取得；归属地服务暂不可用");
            } catch (Exception ignored) { }
        }
        result.put("elapsed_ms", (System.nanoTime() - started) / 1_000_000).put("checked_at", Instant.now().toString());
        if (active != null) proxies();
        if (capturedEgress != egressVersion.get()) throw new ProfileStore.Failure(409, "检测期间出口发生变化，请重新检测");
        result.put("egress_version", capturedEgress);
        if (route.equals("proxy")) {
            JSONObject now = active;
            if (now == null || !hash.equals(now.optString("hash"))) throw new ProfileStore.Failure(409, "检测期间运行配置发生变化，请重新检测");
        }
        return result;
    }
    private static JSONObject fetchLookup(String address, java.net.Proxy proxy) throws Exception {
        java.net.HttpURLConnection connection = (java.net.HttpURLConnection)new java.net.URL(address).openConnection(proxy);
        // Proxy-route lookups traverse the selected node; real-node RTTs of 1-3 s need generous budgets.
        connection.setConnectTimeout(8000); connection.setReadTimeout(12000); connection.setInstanceFollowRedirects(false);
        try {
            if (connection.getResponseCode() != 200) throw new IOException("lookup status");
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream input = connection.getInputStream()) {
                byte[] buffer = new byte[2048]; int count;
                while ((count = input.read(buffer)) != -1) { if (bytes.size() + count > 32768) throw new IOException("lookup size"); bytes.write(buffer, 0, count); }
            }
            return new JSONObject(bytes.toString("UTF-8"));
        } finally { connection.disconnect(); }
    }
    private static String clip(String value, int limit) {
        String text = value == null ? "" : value.trim();
        return text.length() > limit ? text.substring(0, limit) : text;
    }
    /** Loopback-safe totals for the status-bar ticker; frozen totals survive core stops. */
    long[] trafficTotals() {
        try {
            JSONObject totals = loaded && active != null ? new JSONObject(core.getTotalTraffic()) : new JSONObject().put("up", lastUpload).put("down", lastDownload);
            return new long[]{ totals.optLong("up"), totals.optLong("down") };
        } catch (Exception error) { return new long[]{ lastUpload, lastDownload }; }
    }
}
