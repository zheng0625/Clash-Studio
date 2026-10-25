package studio.clash.android;

import android.Manifest;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.net.Uri;
import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.PickVisualMediaRequest;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.webkit.JavaScriptReplyProxy;
import com.journeyapps.barcodescanner.*;
import com.google.zxing.*;
import com.google.zxing.common.HybridBinarizer;
import org.json.JSONObject;
import java.io.*;
import java.net.URI;
import java.util.*;
import java.util.concurrent.*;

/** Camera access is requested on demand; photos use a one-image system URI grant. */
final class SubscriptionQr {
    private final ComponentActivity activity;
    private final ActivityResultLauncher<ScanOptions> scanner;
    private final ActivityResultLauncher<String> cameraPermission;
    private final ActivityResultLauncher<PickVisualMediaRequest> photos;
    private final ExecutorService decoder = Executors.newSingleThreadExecutor();
    private JavaScriptReplyProxy reply;
    private String id;
    private boolean closed;
    SubscriptionQr(ComponentActivity activity) {
        this.activity = activity;
        scanner = activity.registerForActivityResult(new ScanContract(), result -> {
            if (result.getContents() == null) complete(200, cancelled());
            else accept(result.getContents());
        });
        cameraPermission = activity.registerForActivityResult(new ActivityResultContracts.RequestPermission(), granted -> {
            if (reply == null || closed) return;
            if (granted) launchCamera();
            else fail(403, "相机权限未开启。请在权限设置中允许相机，或选择从照片识别。");
        });
        photos = activity.registerForActivityResult(new ActivityResultContracts.PickVisualMedia(), uri -> {
            if (reply == null || closed) return;
            if (uri == null) { complete(200, cancelled()); return; }
            decoder.execute(() -> {
                try { String text = decode(activity, uri); activity.runOnUiThread(() -> { if (!closed) accept(text); }); }
                catch (Exception error) { activity.runOnUiThread(() -> fail(422, "未能识别订阅二维码，请选择清晰、完整的二维码图片。")); }
            });
        });
    }
    void start(String source, String requestId, JavaScriptReplyProxy requestReply) {
        if (closed) return;
        if (reply != null) { send(requestReply, requestId, 409, detail("请先完成当前二维码识别")); return; }
        reply = requestReply; id = requestId;
        try {
            if (source.equals("photo")) photos.launch(new PickVisualMediaRequest.Builder().setMediaType(ActivityResultContracts.PickVisualMedia.ImageOnly.INSTANCE).build());
            else if (source.equals("camera")) {
                if (!activity.getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)) { fail(501, "此设备没有可用相机，请从照片识别"); return; }
                if (activity.checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) launchCamera();
                else cameraPermission.launch(Manifest.permission.CAMERA);
            } else fail(422, "请选择相机扫码或从照片识别");
        } catch (Exception error) { fail(501, "系统相机或照片选择器不可用，请手动粘贴订阅链接"); }
    }
    private void launchCamera() {
        try { scanner.launch(new ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE).setPrompt("扫描订阅二维码").setBeepEnabled(false).setOrientationLocked(false).setBarcodeImageEnabled(false)); }
        catch (Exception error) { fail(501, "相机无法打开，请从照片识别或检查相机权限"); }
    }
    private void accept(String text) {
        try { complete(200, new JSONObject().put("url", subscriptionUrl(text)).put("cancelled", false)); }
        catch (Exception error) { fail(422, "二维码不是有效的 HTTPS 订阅链接，请向服务商获取 Clash/Mihomo 订阅二维码。"); }
    }
    static String subscriptionUrl(String text) throws Exception {
        if (text == null || text.length() > 16384) throw new IllegalArgumentException();
        String value = text.trim(); URI uri = new URI(value);
        if (Arrays.asList("clash", "mihomo", "clashmeta").contains(uri.getScheme())) {
            if (!Arrays.asList("install-config", "install-sub").contains(uri.getHost())) throw new IllegalArgumentException();
            String query = uri.getRawQuery(); value = null;
            if (query != null) for (String item : query.split("&")) {
                String[] pair = item.split("=", 2);
                if (pair.length == 2 && pair[0].equals("url")) { value = java.net.URLDecoder.decode(pair[1], "UTF-8"); break; }
            }
            if (value == null) throw new IllegalArgumentException();
            uri = new URI(value);
        }
        if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null || uri.getFragment() != null)
            throw new IllegalArgumentException();
        return uri.toASCIIString();
    }
    private static String decode(ComponentActivity activity, Uri uri) throws Exception {
        BitmapFactory.Options options = new BitmapFactory.Options(); options.inJustDecodeBounds = true;
        try (InputStream input = activity.getContentResolver().openInputStream(uri)) { BitmapFactory.decodeStream(input, null, options); }
        if (options.outWidth <= 0 || options.outHeight <= 0) throw new IOException("invalid image");
        options.inSampleSize = 1;
        while (Math.max(options.outWidth, options.outHeight) / options.inSampleSize > 2048) options.inSampleSize *= 2;
        options.inJustDecodeBounds = false;
        Bitmap bitmap;
        try (InputStream input = activity.getContentResolver().openInputStream(uri)) { bitmap = BitmapFactory.decodeStream(input, null, options); }
        if (bitmap == null) throw new IOException("invalid image");
        try {
            int width = bitmap.getWidth(), height = bitmap.getHeight(); int[] pixels = new int[width * height];
            bitmap.getPixels(pixels, 0, width, 0, 0, width, height);
            RGBLuminanceSource source = new RGBLuminanceSource(width, height, pixels);
            Map<DecodeHintType,Object> hints = new EnumMap<>(DecodeHintType.class);
            hints.put(DecodeHintType.POSSIBLE_FORMATS, Collections.singletonList(BarcodeFormat.QR_CODE)); hints.put(DecodeHintType.TRY_HARDER, true);
            MultiFormatReader reader = new MultiFormatReader();
            try { return reader.decode(new BinaryBitmap(new HybridBinarizer(source)), hints).getText(); }
            catch (NotFoundException error) { return reader.decode(new BinaryBitmap(new HybridBinarizer(source.invert())), hints).getText(); }
        } finally { bitmap.recycle(); }
    }
    private static JSONObject detail(String text) { try { return new JSONObject().put("detail", text); } catch (Exception e) { throw new IllegalStateException(e); } }
    private static JSONObject cancelled() { try { return new JSONObject().put("cancelled", true); } catch (Exception e) { throw new IllegalStateException(e); } }
    private void fail(int status, String text) { complete(status, detail(text)); }
    private void complete(int status, JSONObject data) { JavaScriptReplyProxy r = reply; String request = id; reply = null; id = null; if (!closed && r != null) send(r, request, status, data); }
    private static void send(JavaScriptReplyProxy r, String id, int status, JSONObject data) { try { if (androidx.webkit.WebViewFeature.isFeatureSupported(androidx.webkit.WebViewFeature.WEB_MESSAGE_LISTENER)) r.postMessage(new JSONObject().put("id", id).put("status", status).put("data", data).toString()); } catch (Exception ignored) { } }
    void close() { closed = true; reply = null; id = null; decoder.shutdownNow(); }
}
