package studio.clash.android;

import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.WindowInsets;
import android.webkit.ConsoleMessage;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import androidx.webkit.JavaScriptReplyProxy;
import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.concurrent.*;
import org.json.JSONObject;

/** Android WebView host with origin-restricted asynchronous native APIs. */
public class MainActivity extends ComponentActivity {
    private static final String HOST = "appassets.androidplatform.net";
    private WebView webView;
    private FrameLayout container;
    private boolean darkChrome;
    private androidx.webkit.ScriptHandler themeBootstrap;
    private ValueCallback<Uri[]> fileCallback;
    private NativeApi nativeApi;
    private SubscriptionQr subscriptionQr;
    private boolean resumeUi;
    private boolean resetUiAfterRendererCrash;
    private JavaScriptReplyProxy exportReply;
    private String exportId, exportText;
    private JavaScriptReplyProxy vpnReply;
    private String vpnId;
    private JSONObject vpnBody;
    private final ExecutorService requests = new ThreadPoolExecutor(2, 2, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(16));
    private final ExecutorService controlRequests = new ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(2));
    private final ExecutorService statusRequests = new ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(8));
    private final ExecutorService lifecycleRequests = new ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(2));
    private final ExecutorService downloadRequests = new ThreadPoolExecutor(2, 2, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(4));
    private final ExecutorService probeRequests = new ThreadPoolExecutor(4, 4, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(8));
    private static boolean cancellableCoreWork(String path) {
        String route = path.split("\\?", 2)[0];
        return route.equals("/api/client/runtime/apply") || route.equals("/api/client/runtime/delay") || route.startsWith("/api/client/probe/");
    }
    private ExecutorService queue(String path, String method) {
        path = path.split("\\?", 2)[0];
        if (path.equals("/api/client/runtime/stop")) { CoreRuntime.INSTANCE.cancelStart(); return controlRequests; }
        if (path.equals("/api/client/runtime") || path.equals("/api/client/platform")) return statusRequests;
        if (path.equals("/api/client/runtime/apply")) return lifecycleRequests;
        if (path.contains("/delay") || path.contains("/probe/")) return probeRequests;
        if (path.equals("/api/subscriptions") && method.equals("POST") || path.endsWith("/refresh") || path.equals("/api/client/network/ip")) return downloadRequests;
        return requests;
    }
    private void closeQueues() { requests.shutdownNow(); controlRequests.shutdownNow(); statusRequests.shutdownNow(); lifecycleRequests.shutdownNow(); downloadRequests.shutdownNow(); probeRequests.shutdownNow(); }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        CoreRuntime.INSTANCE.attach(this);
        // The VPN status-bar notification is a core feature; ask once on Android 13+ if not granted.
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                != android.content.pm.PackageManager.PERMISSION_GRANTED && !getPreferences(MODE_PRIVATE).getBoolean("notificationPermissionRequested", false)) {
            getPreferences(MODE_PRIVATE).edit().putBoolean("notificationPermissionRequested", true).apply();
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 27);
        }
        // A non-null bundle means the system is recollecting a backgrounded task (process death or
        // activity rebuild); only then does the page resume where the user left off. A fresh task
        // (launch, task swiped away, reboot) always starts on the overview page.
        resumeUi = state != null && !state.getBoolean("resetUiAfterRendererCrash", false);
        try { nativeApi = NativeApi.open(getNoBackupFilesDir()); }
        catch (Exception error) { Log.e("ClashStudio", "Local storage could not be opened; existing files preserved"); }
        webView = new WebView(this);
        subscriptionQr = new SubscriptionQr(this);
        container = new FrameLayout(this);
        container.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        setContentView(container);
        applyChrome(getPreferences(MODE_PRIVATE).getBoolean("darkChrome", false), getPreferences(MODE_PRIVATE).getString("chromeBackground", "#F5F7FA"));
        // Keep status bar, cutouts and the IME outside the WebView, but let the page paint under
        // the navigation bar: its inset is pushed to CSS so the themed background continues there.
        container.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                android.graphics.Insets ime = insets.getInsets(WindowInsets.Type.ime());
                view.setPadding(bars.left, bars.top, bars.right, ime.bottom);
                navInset = Math.max(bars.bottom, insets.getInsets(WindowInsets.Type.displayCutout()).bottom);
                dispatchNavInset(false);
            } else {
                view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        container.requestApplyInsets();
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            android.widget.TextView error = new android.widget.TextView(this);
            error.setText("请更新 Android System WebView 后重新打开 Clash Studio。");
            setContentView(error); return;
        }
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) WebViewCompat.addWebMessageListener(webView, "ClashAndroid", Collections.singleton("https://" + HOST), (view, message, origin, mainFrame, reply) -> {
            if (view != webView || !mainFrame || !origin.toString().equals("https://" + HOST)) return;
            String id = "";
            try {
                String raw = message.getData();
                if (raw == null || raw.length() > 12 * 1024 * 1024) throw new IllegalArgumentException("请求过大");
                JSONObject request = new JSONObject(raw);
                id = request.getString("id");
                if (id.length() > 80) throw new IllegalArgumentException("请求编号无效");
                final String requestId = id, path = request.getString("path"), method = request.getString("method");
                final JSONObject body = request.optJSONObject("body");
                if (path.equals("/api/android/qr") && method.equals("POST")) {
                    subscriptionQr.start(body == null ? "" : body.optString("source"), id, reply); return;
                }
                if (path.equals("/api/android/app-settings") && method.equals("POST")) {
                    startActivity(new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName())));
                    postReply(reply, new JSONObject().put("id", id).put("status", 200).put("data", new JSONObject()).toString()); return;
                }
                if (path.equals("/api/android/apps") && method.equals("GET")) {
                    org.json.JSONArray apps = new org.json.JSONArray();
                    java.util.Set<String> seen = new java.util.HashSet<>();
                    Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
                    for (android.content.pm.ResolveInfo resolved : getPackageManager().queryIntentActivities(launcher, 0)) {
                        android.content.pm.ApplicationInfo app = resolved.activityInfo.applicationInfo;
                        if (!seen.add(app.packageName)) continue;
                        apps.put(new JSONObject().put("package", app.packageName).put("label", getPackageManager().getApplicationLabel(app)));
                    }
                    postReply(reply, new JSONObject().put("id", id).put("status", 200).put("data", apps).toString()); return;
                }
                if (path.equals("/api/android/permissions") && method.equals("GET")) {
                    JSONObject permissions = new JSONObject().put("camera", checkSelfPermission(android.Manifest.permission.CAMERA) == android.content.pm.PackageManager.PERMISSION_GRANTED)
                        .put("notifications", getSystemService(android.app.NotificationManager.class).areNotificationsEnabled())
                        .put("vpn", android.net.VpnService.prepare(this) == null);
                    postReply(reply, new JSONObject().put("id", id).put("status", 200).put("data", permissions).toString()); return;
                }
                if (path.equals("/api/android/theme") && method.equals("POST")) {
                    if (body == null || !body.optString("background").matches("#[0-9a-fA-F]{6}")) throw new IllegalArgumentException("主题颜色无效");
                    applyChrome(body.getBoolean("dark"), body.getString("background"));
                    postReply(reply, new JSONObject().put("id", id).put("status", 200).put("data", new JSONObject()).toString()); return;
                }
                if (path.equals("/api/client/runtime/stop") && method.equals("POST") && vpnReply != null) {
                    replyError(vpnReply, vpnId, 409, "VPN 启动已取消");
                    vpnReply = null; vpnId = null; vpnBody = null;
                }
                if (path.equals("/api/client/runtime/apply") && method.equals("POST")) {
                    Intent consent = android.net.VpnService.prepare(this);
                    if (consent != null) {
                        if (vpnReply != null) { replyError(reply, id, 409, "请先完成当前 VPN 授权"); return; }
                        vpnReply = reply; vpnId = id; vpnBody = body;
                        startActivityForResult(consent, 102); return;
                    }
                }
                if (path.equals("/api/android/export") && method.equals("POST")) {
                    if (exportReply != null) { replyError(reply, id, 409, "请先完成当前文件保存"); return; }
                    if (body == null || body.getString("text").getBytes(StandardCharsets.UTF_8).length > ConfigEngine.MAX_BYTES) throw new IllegalArgumentException("文件过大");
                    String filename = body.optString("filename", "ClashStudio.yaml").replaceAll("[^\\p{L}\\p{N} ._-]", "_");
                    exportReply = reply; exportId = id; exportText = body.getString("text");
                    try { startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/yaml").putExtra(Intent.EXTRA_TITLE, filename), 101); }
                    catch (android.content.ActivityNotFoundException error) { replyError(reply, id, 501, "系统文件保存器不可用"); clearExport(); }
                    return;
                }
                long startEpoch = CoreRuntime.INSTANCE.startEpoch();
                queue(path, method).execute(() -> {
                    if (cancellableCoreWork(path) && startEpoch != CoreRuntime.INSTANCE.startEpoch()) {
                        if (!isDestroyed()) runOnUiThread(() -> replyError(reply, requestId, 409, "排队中的内核操作已取消"));
                        return;
                    }
                    NativeApi.Response response = nativeApi == null ? null : nativeApi.request(path, method, body);
                    if (!isDestroyed()) runOnUiThread(() -> {
                        if (isDestroyed() || webView != view) return;
                        if (response == null) replyError(reply, requestId, 503, "本地数据读取失败，已保留原文件，请先备份检查");
                        else try { postReply(reply, response.envelope(requestId).toString()); }
                        catch (Exception error) { replyError(reply, requestId, 500, "原生响应处理失败"); }
                    });
                });
            } catch (RejectedExecutionException error) { replyError(reply, id, 429, "操作过多，请稍后重试"); }
            catch (Exception error) { replyError(reply, id, 422, "原生请求格式无效"); }
        });
        installThemeBootstrap();
        WebViewAssetLoader assets = new WebViewAssetLoader.Builder()
            .addPathHandler("/", new WebViewAssetLoader.AssetsPathHandler(this)).build();
        webView.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView view, String url) { if (url.startsWith("https://" + HOST + "/")) { dispatchSystemTheme(); dispatchNavInset(true); } }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (!"https".equals(uri.getScheme()) || !HOST.equals(uri.getHost())) return json(403, "{\"detail\":\"External WebView subresources are disabled\"}");
                String path = uri.getPath();
                if (path != null && path.startsWith("/api/")) {
                    if (!request.getMethod().equals("GET")) return json(405, "{\"detail\":\"Use the native message bridge for mutations\"}");
                    if (nativeApi == null) return json(503, "{\"detail\":\"Local storage unavailable\"}");
                    NativeApi.Response response = nativeApi.request(path + (uri.getEncodedQuery() == null ? "" : "?" + uri.getEncodedQuery()), "GET", null);
                    return json(response.status, response.data.toString());
                }
                WebResourceResponse result = assets.shouldInterceptRequest(uri);
                return result != null ? result : json(404, "{\"detail\":\"Asset not found\"}");
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("https".equals(uri.getScheme()) && HOST.equals(uri.getHost())) return false;
                if (request.isForMainFrame() && ("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()))) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); } catch (android.content.ActivityNotFoundException ignored) { }
                }
                return true;
            }
            @Override public boolean onRenderProcessGone(WebView view, android.webkit.RenderProcessGoneDetail detail) {
                if (view != webView) return true;
                // Reclaimed renderers resume the page; crashes deliberately start at the overview.
                resetUiAfterRendererCrash = detail.didCrash();
                subscriptionQr.close();
                closeQueues();
                clearExport();
                vpnReply = null; vpnId = null; vpnBody = null;
                if (fileCallback != null) { fileCallback.onReceiveValue(null); fileCallback = null; }
                disposeWebView();
                if (!isFinishing() && !isDestroyed()) recreate();
                return true;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage message) {
                if (message.messageLevel() == ConsoleMessage.MessageLevel.ERROR) Log.e("ClashStudioWeb", message.message());
                return true;
            }
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try { startActivityForResult(params.createIntent(), 100); }
                catch (android.content.ActivityNotFoundException error) { fileCallback.onReceiveValue(null); fileCallback = null; }
                return true;
            }
        });
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() { handleBack(); }
        });
        webView.loadUrl("https://" + HOST + "/index.html" + (resumeUi ? "?resume=1" : ""));
    }
    private void handleBack() {
        if (webView == null) return;
        if (Build.VERSION.SDK_INT >= 30 && webView.getRootWindowInsets() != null
                && webView.getRootWindowInsets().isVisible(WindowInsets.Type.ime())) {
            getWindow().getInsetsController().hide(WindowInsets.Type.ime());
            return;
        }
        webView.evaluateJavascript("(()=>{const d=document.querySelector('dialog[open]');if(d){d.close();return true;}return !window.dispatchEvent(new Event('clash-android-back',{cancelable:true}));})()", handled -> {
            if (!"true".equals(handled)) finish();
        });
    }
    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == 102 && vpnReply != null) {
            JavaScriptReplyProxy reply = vpnReply; String id = vpnId; JSONObject body = vpnBody;
            vpnReply = null; vpnId = null; vpnBody = null;
            if (resultCode != RESULT_OK) { replyError(reply, id, 403, "VPN 授权已取消，未接管网络"); return; }
            long startEpoch = CoreRuntime.INSTANCE.startEpoch();
            try {
                lifecycleRequests.execute(() -> {
                    if (startEpoch != CoreRuntime.INSTANCE.startEpoch()) {
                        runOnUiThread(() -> { if (!isDestroyed()) replyError(reply, id, 409, "VPN 启动已取消"); });
                        return;
                    }
                    NativeApi.Response result = nativeApi.request("/api/client/runtime/apply", "POST", body);
                    runOnUiThread(() -> { if (!isDestroyed()) try { postReply(reply, result.envelope(id).toString()); } catch (Exception ignored) { } });
                });
            } catch (RejectedExecutionException error) { replyError(reply, id, 429, "操作过多，请稍后重试"); }
            return;
        }
        if (requestCode == 100 && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileCallback = null;
        }
        if (requestCode == 101 && exportReply != null) {
            JavaScriptReplyProxy reply = exportReply; String id = exportId, text = exportText; clearExport();
            if (resultCode != RESULT_OK || data == null || data.getData() == null) {
                try { postReply(reply, new JSONObject().put("id", id).put("status", 200).put("data", new JSONObject().put("cancelled", true)).toString()); } catch (Exception ignored) { }
            } else {
                Uri destination = data.getData();
                requests.execute(() -> {
                    boolean success = false;
                    try (java.io.OutputStream output = getContentResolver().openOutputStream(destination, "wt")) {
                        if (output == null) throw new java.io.IOException("No output stream");
                        output.write(text.getBytes(StandardCharsets.UTF_8)); output.flush(); success = true;
                    } catch (Exception ignored) { }
                    final boolean saved = success;
                    if (!isDestroyed()) runOnUiThread(() -> {
                        if (isDestroyed()) return;
                        if (!saved) replyError(reply, id, 500, "文件保存失败，请重试");
                        else try { postReply(reply, new JSONObject().put("id", id).put("status", 200).put("data", new JSONObject().put("saved", true)).toString()); } catch (Exception ignored) { }
                    });
                });
            }
        }
    }
    private void clearExport() { exportReply = null; exportId = null; exportText = null; }
    private boolean systemDark() { return (getResources().getConfiguration().uiMode & android.content.res.Configuration.UI_MODE_NIGHT_MASK) == android.content.res.Configuration.UI_MODE_NIGHT_YES; }
    private void installThemeBootstrap() {
        if (webView == null) return;
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            if (themeBootstrap != null) themeBootstrap.remove();
            themeBootstrap = WebViewCompat.addDocumentStartJavaScript(webView, "window.__clashAndroidSystemDark=" + systemDark() + ";", Collections.singleton("https://" + HOST));
        }
    }
    private void dispatchSystemTheme() {
        if (webView != null) webView.evaluateJavascript("window.__clashAndroidSystemDark=" + systemDark() + ";window.dispatchEvent(new Event('clash-android-system-theme'));", null);
    }
    @Override public void onConfigurationChanged(android.content.res.Configuration configuration) { super.onConfigurationChanged(configuration); installThemeBootstrap(); dispatchSystemTheme(); dispatchNavInset(true); }
    private void applyChrome(boolean dark, String background) {
        darkChrome = dark;
        int color = android.graphics.Color.parseColor(background);
        getWindow().getDecorView().setBackgroundColor(color);
        if (container != null) container.setBackgroundColor(color);
        if (webView != null) webView.setBackgroundColor(color);
        getPreferences(MODE_PRIVATE).edit().putBoolean("darkChrome", dark).putString("chromeBackground", background).apply();
        if (Build.VERSION.SDK_INT < 30) {
            int flags = getWindow().getDecorView().getSystemUiVisibility();
            int light = android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            getWindow().getDecorView().setSystemUiVisibility(dark ? flags & ~light : flags | light);
        }
        updateBarAppearance();
    }
    private void updateBarAppearance() {
        if (Build.VERSION.SDK_INT >= 30 && getWindow().getInsetsController() != null) {
            int light = android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS | android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
            getWindow().getInsetsController().setSystemBarsAppearance(darkChrome ? 0 : light, light);
        }
    }
    private int navInset = -1, pushedNavInset = -1;
    private void dispatchNavInset(boolean force) {
        if (webView == null || navInset < 0 || (!force && navInset == pushedNavInset)) return;
        pushedNavInset = navInset;
        webView.evaluateJavascript("(()=>{window.__clashAndroidNavInset=" + navInset + ";"
            + "if(!window.__clashAndroidInsetSync){window.__clashAndroidInsetSync=()=>document.documentElement.style.setProperty('--android-nav-inset',(window.__clashAndroidNavInset/(window.devicePixelRatio||1))+'px');window.addEventListener('resize',window.__clashAndroidInsetSync);}"
            + "window.__clashAndroidInsetSync();})()", null);
    }
    @Override public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) updateBarAppearance();
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        state.putBoolean("resetUiAfterRendererCrash", resetUiAfterRendererCrash);
        super.onSaveInstanceState(state);
    }
    private void disposeWebView() {
        WebView old = webView;
        webView = null;
        themeBootstrap = null;
        if (old == null) return;
        if (old.getParent() instanceof android.view.ViewGroup) ((android.view.ViewGroup) old.getParent()).removeView(old);
        old.destroy();
    }
    @Override protected void onDestroy() {
        CoreRuntime.INSTANCE.cancelStart();
        vpnReply = null; vpnId = null; vpnBody = null;
        clearExport();
        if (subscriptionQr != null) subscriptionQr.close();
        closeQueues();
        if (fileCallback != null) { fileCallback.onReceiveValue(null); fileCallback = null; }
        disposeWebView();
        super.onDestroy();
    }
    private static void postReply(JavaScriptReplyProxy reply, String message) {
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) reply.postMessage(message);
    }
    private static void replyError(JavaScriptReplyProxy reply, String id, int status, String detail) {
        try { postReply(reply, new JSONObject().put("id", id).put("status", status).put("data", new JSONObject().put("detail", detail).put("error", ErrorContract.error(status, ErrorContract.code(status), detail).put("operation_id", id))).toString()); }
        catch (Exception ignored) { }
    }
    static WebResourceResponse json(int status, String body) {
        return new WebResourceResponse("application/json", "UTF-8", status, status < 400 ? "OK" : "Unavailable",
            Collections.singletonMap("Cache-Control", "no-store"), new ByteArrayInputStream(body.getBytes(StandardCharsets.UTF_8)));
    }
}
