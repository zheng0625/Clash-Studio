package studio.clash.android;

import android.os.Build;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.util.*;

/** Android-owned APIs; unsupported runtime features return explicit errors. */
final class NativeApi {
    private static NativeApi shared;
    static synchronized NativeApi open(File directory) throws Exception {
        if (shared == null) shared = new NativeApi(directory);
        return shared;
    }
    final ProfileStore store;
    final AndroidRouting routing;
    static final String DEMO = "proxies:\n  - name: 示例节点 · 不提供代理\n    type: socks5\n    server: example.invalid\n    port: 9\nproxy-groups:\n  - name: 节点选择\n    type: select\n    proxies: [示例节点 · 不提供代理, DIRECT]\nrules:\n  - MATCH,节点选择\n";
    static class Response {
        final int status; final Object data;
        Response(int status, Object data) { this.status = status; this.data = data; }
        JSONObject envelope(String id) throws Exception { return new JSONObject().put("id", id).put("status", status).put("data", data); }
    }
    NativeApi(File directory) throws Exception { store = new ProfileStore(directory); routing = new AndroidRouting(directory); }
    JSONObject preview(String id) throws Exception {
        JSONObject profile = store.get(id), preview = profile.getJSONObject("preview");
        synchronized (routing) {
            preview.put("config", routing.overlay(id, preview.getJSONObject("config")));
            preview.put("yaml", ConfigEngine.dump(preview.getJSONObject("config")));
            return preview.put("profile_revision", profile.getInt("revision")).put("workspace_revision", routing.revision())
                .put("module_rules", new JSONArray()).put("published_conflict", false);
        }
    }
    Response request(String path, String method, JSONObject body) {
        try { return new Response(200, route(path, method.equals("DEL") ? "DELETE" : method, body == null ? new JSONObject() : body)); }
        catch (ProfileStore.Failure error) { return error(error.status, error.getMessage()); }
        catch (IllegalArgumentException | org.json.JSONException error) { return error(422, "配置或参数无效：" + error.getMessage()); }
        catch (org.yaml.snakeyaml.error.YAMLException error) { return error(422, "YAML 格式无效，请检查缩进、字段与重复键"); }
        catch (Exception error) {
            Throwable cause = error instanceof java.util.concurrent.ExecutionException ? error.getCause() : error;
            if (cause instanceof ProfileStore.Failure) return error(((ProfileStore.Failure)cause).status, cause.getMessage());
            return error(500, "操作未完成，请检查网络或本地存储后重试");
        }
    }
    private static Response error(int status, String detail) {
        try { return new Response(status, new JSONObject().put("detail", detail)); }
        catch (Exception impossible) { throw new IllegalStateException(impossible); }
    }
    private Object route(String path, String method, JSONObject body) throws Exception {
        URI uri = new URI(path);
        if (uri.isAbsolute() || uri.getRawAuthority() != null || uri.getFragment() != null || !uri.getPath().startsWith("/api/")) throw new ProfileStore.Failure(403, "仅允许本地 API 路径");
        String route = uri.getPath();
        Map<String,String> query = new HashMap<>();
        if (uri.getRawQuery() != null) for (String item : uri.getRawQuery().split("&")) {
            String[] pair = item.split("=", 2);
            query.put(URLDecoder.decode(pair[0], "UTF-8"), pair.length > 1 ? URLDecoder.decode(pair[1], "UTF-8") : "");
        }
        if (route.equals("/api/subscriptions")) {
            if (method.equals("GET")) return store.list();
            if (method.equals("POST")) {
                String type = body.getString("source_type"), url = body.optString("source_url", "");
                Download download = type.equals("url") ? fetch(url) : new Download(type.equals("demo") ? DEMO : body.getString("yaml"), null);
                return store.create(body.optString("title", type.equals("demo") ? "示例订阅 · 不提供实际代理" : ""), type, url, download.yaml, download.usage);
            }
        }
        if (route.equals("/api/android/routing")) {
            String id = method.equals("GET") ? query.getOrDefault("profile_id", "") : body.getString("profile_id");
            JSONObject config = store.get(id).getJSONObject("preview").getJSONObject("config");
            if (method.equals("GET")) return routing.get(id, config);
            if (method.equals("PUT")) return routing.save(id, body.getInt("revision"), body.getJSONArray("rules"), config);
            throw new ProfileStore.Failure(405, "不支持的分流操作");
        }
        String[] segments = route.substring(1).split("/");
        if (segments.length >= 3 && segments[1].equals("subscriptions")) {
            String id = segments[2];
            if (segments.length == 3) {
                if (method.equals("GET")) return store.get(id);
                if (method.equals("DELETE")) { if (CoreRuntime.INSTANCE.uses(id)) throw new ProfileStore.Failure(409, "请先停止正在使用此订阅的 VPN"); store.delete(id, Integer.parseInt(query.getOrDefault("revision", "-1"))); return new JSONObject(); }
                if (method.equals("PATCH")) return store.metadata(id, body.getInt("revision"), body);
            }
            if (segments.length == 4) {
                String action = segments[3];
                if (action.equals("preview") && method.equals("POST")) return store.draft(id, body.getInt("revision"), body.getJSONObject("edits"));
                if (action.equals("edits") && method.equals("PUT")) return store.saveEdits(id, body.getInt("revision"), body.getJSONObject("edits"));
                if (action.equals("refresh") && method.equals("POST")) {
                    JSONObject old = store.get(id);
                    Download download = old.getString("source_type").equals("url") ? fetch(old.getString("source_url")) : new Download(old.getString("source_type").equals("demo") ? DEMO : body.getString("yaml"), null);
                    return store.refresh(id, body.getInt("revision"), download.yaml, download.usage);
                }
                if (action.equals("history") && method.equals("GET")) return store.histories(id);
            }
            if (segments.length >= 5 && segments[3].equals("history")) {
                int historyId = Integer.parseInt(segments[4]);
                if (segments.length == 5 && method.equals("GET")) {
                    JSONObject snapshot = store.historical(id, historyId), record = snapshot.getJSONObject("record");
                    return new JSONObject().put("id", historyId).put("label", snapshot.getString("label")).put("yaml", ConfigEngine.preview(record.getJSONObject("source"), record.getJSONObject("edits")).getString("yaml"));
                }
                if (segments.length == 6 && segments[5].equals("restore") && method.equals("POST")) return store.restore(id, body.getInt("revision"), historyId);
            }
        }
        if (route.startsWith("/api/client/preview/") && method.equals("GET")) {
            return preview(route.substring("/api/client/preview/".length()));
        }
        if (route.equals("/api/client/proxy-catalog") && method.equals("GET")) {
            String id = query.getOrDefault("profile_id", ""); JSONObject catalog = store.catalog(id);
            JSONObject nativeProxies = CoreRuntime.INSTANCE.selectionCatalog(id, catalog.getInt("profile_revision"));
            if (nativeProxies != null) {
                boolean live = CoreRuntime.INSTANCE.matches(id, catalog.getInt("profile_revision"));
                if (!live) {
                    JSONObject saved = store.selections(id);
                    for (String name : ConfigEngine.keys(saved)) {
                        JSONObject group = nativeProxies.optJSONObject(name);
                        if (group != null && group.optJSONArray("all") != null && ConfigEngine.strings(group.getJSONArray("all")).contains(saved.getString(name))) group.put("now", saved.getString(name));
                    }
                }
                catalog.put("proxies", nativeProxies).put("live", live);
            }
            return catalog.put("workspace_revision", routing.revision());
        }
        if (route.equals("/api/client/proxy-selection") && method.equals("PUT")) {
            if (body.getInt("workspace_revision") != routing.revision()) throw new ProfileStore.Failure(409, "分流规则已改变，请刷新节点列表");
            // ProfileStore owns subscription revisions; overlay revisions are checked above.
            body = ConfigEngine.copy(body).put("workspace_revision", 1);
            boolean live = CoreRuntime.INSTANCE.matches(body.getString("profile_id"), body.getInt("profile_revision"));
            JSONObject proxies = CoreRuntime.INSTANCE.selectionCatalog(body.getString("profile_id"), body.getInt("profile_revision"));
            store.validateSelection(body, proxies);
            String previous = live ? proxies.getJSONObject(body.getString("group")).optString("now") : "";
            if (live) CoreRuntime.INSTANCE.select(body);
            try { store.select(body, proxies); }
            catch (Exception error) {
                if (live && !previous.isEmpty()) try { CoreRuntime.INSTANCE.select(ConfigEngine.copy(body).put("name", previous)); } catch (Exception ignored) { }
                throw error;
            }
            return new JSONObject();
        }
        if (route.equals("/api/client/runtime/apply") && method.equals("POST")) return CoreRuntime.INSTANCE.apply(body);
        if (route.equals("/api/client/probe/prepare") && method.equals("POST")) return CoreRuntime.INSTANCE.prepareProbe(body);
        if (route.equals("/api/client/runtime/stop") && method.equals("POST")) return CoreRuntime.INSTANCE.stop();
        if (route.equals("/api/client/runtime/routing-mode") && method.equals("PUT")) return CoreRuntime.INSTANCE.routing(body.getString("mode"));
        if (route.equals("/api/client/runtime/proxies") && method.equals("GET")) return CoreRuntime.INSTANCE.proxies();
        if (route.equals("/api/client/runtime/delay") && method.equals("POST")) return CoreRuntime.INSTANCE.delay(body);
        if (route.equals("/api/client/runtime/connections") && method.equals("GET")) return CoreRuntime.INSTANCE.connections();
        if (route.startsWith("/api/client/runtime/connections/") && method.equals("DELETE")) { CoreRuntime.INSTANCE.close(route.substring("/api/client/runtime/connections/".length())); return new JSONObject(); }
        if (route.equals("/api/client/settings")) {
            if (method.equals("PUT")) store.saveSettings(body);
            else if (!method.equals("GET")) throw new ProfileStore.Failure(405, "不支持的操作");
            return settings();
        }
        if (route.equals("/api/client/tray/context") && method.equals("PUT")) return new JSONObject();
        if (method.equals("GET")) switch (route) {
            case "/api/client/platform": return new JSONObject().put("os", "android").put("arch", Build.SUPPORTED_ABIS[0]).put("capabilities", new JSONObject("{\"validation\":false,\"development\":true,\"native_insets\":true,\"subscriptions\":true,\"modules\":false,\"ai\":false,\"lan_share\":false,\"autostart\":false}").put("core", CoreRuntime.INSTANCE.available()).put("vpn", CoreRuntime.INSTANCE.available()));
            case "/api/client/workspace": return new JSONObject().put("revision", routing.revision()).put("modules", new JSONArray()).put("plans", new JSONObject());
            case "/api/client/tray": return new JSONObject("{\"context_configured\":false,\"proxy_mode\":\"system\",\"tun_stack\":\"mixed\",\"profile_id\":\"\"}");
            case "/api/client/runtime": return CoreRuntime.INSTANCE.status();
            case "/api/client/network/traffic": return CoreRuntime.INSTANCE.traffic();
            case "/api/client/network/ip": return CoreRuntime.INSTANCE.lookup(query.getOrDefault("route", "system"), "true".equals(query.getOrDefault("refresh", "false")));
            case "/api/presets/ai": return new JSONObject("{\"version\":\"android\",\"group_name\":\"AI\",\"service_count\":0,\"rule_count\":0,\"services\":[]}");
            case "/api/network": return new JSONObject("{\"enabled\":false,\"running\":false,\"port\":8767,\"selected_host\":\"\",\"addresses\":[],\"base_url\":\"\",\"error\":\"\"}");
            case "/api/client/geodata": return settings().getJSONObject("geodata");
            default: break;
        }
        throw new ProfileStore.Failure(501, "此功能尚未接入安卓端；当前支持订阅管理、配置编辑与节点选择");
    }
    private JSONObject settings() throws Exception {
        return new JSONObject().put("settings", store.settings()).put("lan_addresses", new JSONArray()).put("core_version", "Mihomo v1.19.32 · Android ARM64")
            .put("geodata", new JSONObject("{\"busy\":false,\"phase\":\"idle\",\"completed\":0,\"total\":0,\"file\":\"\",\"message\":\"\",\"files\":[]}"));
    }
    private static class Download {
        final String yaml; final Object usage;
        Download(String yaml, Object usage) { this.yaml = yaml; this.usage = usage; }
    }
    private static Download fetch(String address) throws Exception {
        URI uri = new URI(address);
        long deadline = System.nanoTime() + 30_000_000_000L;
        for (int redirects = 0; redirects < 6; redirects++) {
            int remaining = (int)((deadline - System.nanoTime()) / 1_000_000);
            if (remaining <= 0) throw new ProfileStore.Failure(504, "订阅下载超时");
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null) throw new ProfileStore.Failure(422, "订阅地址必须是 HTTPS URL，且不能包含内嵌账号密码");
            HttpURLConnection connection = (HttpURLConnection)uri.toURL().openConnection();
            connection.setConnectTimeout(Math.min(10000, remaining)); connection.setReadTimeout(Math.min(10000, remaining)); connection.setInstanceFollowRedirects(false);
            // Subscription panels select their output by client User-Agent; match the Clash Verge Rev
            // identifier (same as the desktop backend) so panels return the Clash YAML payload.
            connection.setRequestProperty("User-Agent", "clash-verge/v2.5.8");
            connection.setRequestProperty("Accept", "text/yaml, text/plain, */*");
            try {
                int status = connection.getResponseCode();
                if (Arrays.asList(301, 302, 303, 307, 308).contains(status)) {
                    String location = connection.getHeaderField("Location");
                    if (location == null) throw new ProfileStore.Failure(502, "订阅重定向缺少目标地址");
                    uri = uri.resolve(location); continue;
                }
                if (status != 200) throw new ProfileStore.Failure(502, "订阅服务返回 HTTP " + status);
                if (connection.getContentLengthLong() > ConfigEngine.MAX_BYTES) throw new ProfileStore.Failure(413, "配置文件不能超过 8 MB");
                ByteArrayOutputStream output = new ByteArrayOutputStream();
                try (InputStream input = connection.getInputStream()) {
                    byte[] buffer = new byte[16384]; int count;
                    while ((count = input.read(buffer)) != -1) {
                        if (System.nanoTime() > deadline) throw new ProfileStore.Failure(504, "订阅下载超时");
                        if (output.size() + count > ConfigEngine.MAX_BYTES) throw new ProfileStore.Failure(413, "配置文件不能超过 8 MB");
                        output.write(buffer, 0, count);
                    }
                }
                CharsetDecoder utf8 = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT);
                String yaml = utf8.decode(ByteBuffer.wrap(output.toByteArray())).toString();
                ConfigEngine.rejectClientNotice(yaml);
                return new Download(yaml, usage(connection.getHeaderField("subscription-userinfo")));
            } catch (IOException error) {
                if (BuildConfig.DEBUG) android.util.Log.w("ClashStudioSub", error.getClass().getSimpleName());
                throw new ProfileStore.Failure(502, "订阅下载失败，请检查网络、证书和订阅地址");
            } finally { connection.disconnect(); }
        }
        throw new ProfileStore.Failure(502, "订阅重定向次数过多");
    }
    private static Object usage(String header) throws Exception {
        if (header == null) return null;
        Map<String,Long> values = new HashMap<>();
        for (String part : header.split(";")) {
            String[] pair = part.trim().split("=", 2);
            if (pair.length == 2) try { values.put(pair[0], Long.parseLong(pair[1])); } catch (NumberFormatException ignored) { }
        }
        long used;
        try { used = Math.addExact(Math.max(0, values.getOrDefault("upload", 0L)), Math.max(0, values.getOrDefault("download", 0L))); }
        catch (ArithmeticException overflow) { used = Long.MAX_VALUE; }
        long total = values.getOrDefault("total", 0L);
        return new JSONObject().put("used", used).put("total", total > 0 ? total : JSONObject.NULL).put("remaining", total > 0 ? Math.max(0, total-used) : JSONObject.NULL).put("percent", total > 0 ? Math.min(100.0, used*100.0/total) : JSONObject.NULL);
    }
}
