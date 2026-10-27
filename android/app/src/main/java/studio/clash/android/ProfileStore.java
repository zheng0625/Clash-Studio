package studio.clash.android;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/** App-private, atomic storage. Revisions reject stale edits rather than overwrite them. */
final class ProfileStore {
    private final Path file;
    private final Path hotFile;
    private boolean hotCleanupPending;
    private JSONObject state;
    private final LinkedHashMap<String, JSONObject> hydrated = new LinkedHashMap<>(16, .75f, true);
    static class Failure extends Exception {
        final int status; final String code;
        Failure(int status, String message) { this(status, message, ErrorContract.code(status)); }
        Failure(int status, String message, String code) { super(message); this.status = status; this.code = code; }
    }
    ProfileStore(File directory) throws Exception {
        Files.createDirectories(directory.toPath()); file = directory.toPath().resolve("profiles-v1.json"); hotFile = directory.toPath().resolve("client-state-v2.json");
        if (Files.exists(file)) {
            if (Files.size(file) > 64L * 1024 * 1024) throw new IOException("本地数据文件过大，请先备份检查");
            state = new JSONObject(new String(Files.readAllBytes(file), java.nio.charset.StandardCharsets.UTF_8));
            if (state.getInt("version") != 1) throw new IOException("不支持的本地数据版本");
            state.getJSONObject("profiles"); state.getJSONObject("selections"); state.getJSONObject("settings");
        } else state = new JSONObject().put("version", 1).put("profiles", new JSONObject()).put("selections", new JSONObject()).put("settings", defaults());
        if (Files.exists(hotFile)) {
            if (Files.size(hotFile) > 4L * 1024 * 1024) throw new IOException("高频状态文件过大");
            JSONObject hot = new JSONObject(new String(Files.readAllBytes(hotFile), java.nio.charset.StandardCharsets.UTF_8));
            if (hot.getInt("version") != 2) throw new IOException("不支持的高频状态版本");
            state.put("selections", hot.getJSONObject("selections")).put("settings", hot.getJSONObject("settings"));
        } else commitHot(hotState()); // The untouched v1 document remains the migration backup.
        pruneHot();
    }
    static JSONObject defaults() throws Exception {
        return new JSONObject("{\"allow_lan\":false,\"ipv6\":true,\"dns_leak_prevention\":false,\"lan_auth\":false,\"mixed_port\":17890,\"lan_username\":\"\",\"lan_password\":\"\",\"dns_override\":{\"enabled\":false,\"mode\":\"fake-ip\",\"nameserver\":[],\"fallback\":[],\"bootstrap\":[],\"proxy_nameserver\":[],\"fake_ip_filter\":[]}}");
    }
    private JSONObject hotState() throws Exception {
        JSONObject choices = new JSONObject();
        for (String id : ConfigEngine.keys(state.getJSONObject("selections"))) if (state.getJSONObject("profiles").has(id)) choices.put(id, state.getJSONObject("selections").getJSONObject(id));
        return new JSONObject().put("version", 2).put("settings", ConfigEngine.copy(state.getJSONObject("settings"))).put("selections", ConfigEngine.copy(choices));
    }
    private void commitHot(JSONObject hot) throws Exception {
        if (hot.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 4 * 1024 * 1024) throw new Failure(413, "节点选择及设置数据过大");
        AtomicDocument.write(hotFile, hot.toString());
        state.put("settings", hot.getJSONObject("settings")).put("selections", hot.getJSONObject("selections"));
        hotCleanupPending = false;
    }
    private JSONObject cleanedHotState() throws Exception {
        JSONObject hot = hotState(), choices = hot.getJSONObject("selections");
        for (String id : ConfigEngine.keys(choices)) choices.put(id, selections(id));
        return hot;
    }
    private void pruneHot() throws Exception {
        JSONObject hot = cleanedHotState();
        if (!hot.getJSONObject("selections").toString().equals(state.getJSONObject("selections").toString())) commitHot(hot);
    }
    synchronized boolean hotCleanupPending() { return hotCleanupPending; }
    private void commit(JSONObject next) throws Exception {
        byte[] bytes = next.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
        if (bytes.length > 64 * 1024 * 1024) throw new Failure(413, "本地数据超过 64 MB，请减少订阅内容或删除不再需要的订阅");
        Path temporary = file.resolveSibling("profiles-v1.json.tmp");
        try {
            try (FileChannel channel = FileChannel.open(temporary, StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.TRUNCATE_EXISTING)) {
                ByteBuffer buffer = ByteBuffer.wrap(bytes);
                while (buffer.hasRemaining()) channel.write(buffer);
                channel.force(true);
            }
            Files.move(temporary, file, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            state = next;
            try { commitHot(cleanedHotState()); } catch (IOException error) { hotCleanupPending = true; }
        } finally { Files.deleteIfExists(temporary); }
    }
    private JSONObject record(String id) throws Exception {
        JSONObject value = state.getJSONObject("profiles").optJSONObject(id);
        if (value == null) throw new Failure(404, "订阅不存在");
        return ConfigEngine.copy(value);
    }
    private void check(JSONObject value, int revision) throws Exception {
        if (value.getInt("revision") != revision) throw new Failure(409, "订阅已更新，请刷新后重试");
    }
    private JSONObject publish(JSONObject record, JSONObject preview) throws Exception {
        if (preview.getJSONArray("errors").length() != 0) throw new Failure(422, preview.getJSONArray("errors").join("；"));
        JSONObject next = ConfigEngine.copy(state);
        next.getJSONObject("profiles").put(record.getString("id"), record);
        commit(next);
        return hydrate(record);
    }
    private void history(JSONObject record) throws Exception {
        JSONArray old = record.getJSONArray("history"), keep = new JSONArray();
        JSONObject snapshot = ConfigEngine.copy(record); snapshot.remove("history");
        keep.put(new JSONObject().put("id", record.getInt("revision")).put("created_at", Instant.now().toString()).put("label", "保存记录").put("record", snapshot));
        for (int i = 0; i < Math.min(old.length(), 4); i++) keep.put(old.get(i));
        record.put("history", keep).put("revision", record.getInt("revision") + 1).put("updated_at", Instant.now().toString());
    }
    private JSONObject preview(JSONObject record, JSONObject edits) throws Exception { return ConfigEngine.preview(record.getJSONObject("source"), edits); }
    private JSONObject hydrate(JSONObject record) throws Exception {
        String key = record.getString("id") + ":" + record.getInt("revision");
        JSONObject cached = hydrated.get(key);
        if (cached != null) return ConfigEngine.copy(cached);
        JSONObject result = ConfigEngine.copy(record), preview = preview(record, record.getJSONObject("edits"));
        JSONObject config = preview.getJSONObject("config");
        result.remove("history");
        result.put("preview", preview).put("proxy_count", config.getJSONArray("proxies").length()).put("group_count", config.getJSONArray("proxy-groups").length()).put("rule_count", config.getJSONArray("rules").length());
        hydrated.put(key, ConfigEngine.copy(result));
        while (hydrated.size() > 8) hydrated.remove(hydrated.keySet().iterator().next());
        return result;
    }
    synchronized JSONArray list() throws Exception {
        JSONArray result = new JSONArray();
        for (String id : ConfigEngine.keys(state.getJSONObject("profiles"))) {
            JSONObject item = hydrate(record(id));
            for (String key : Arrays.asList("source", "source_yaml", "source_url", "preview", "edits", "subscription_path")) item.remove(key);
            result.put(item);
        }
        return result;
    }
    synchronized JSONObject get(String id) throws Exception { return hydrate(record(id)); }
    synchronized JSONObject create(String title, String type, String url, String yaml, Object usage) throws Exception {
        if (state.getJSONObject("profiles").length() >= 50) throw new Failure(413, "最多保存 50 份订阅");
        if (!Arrays.asList("url", "file", "demo").contains(type)) throw new Failure(422, "不支持的订阅类型");
        title = title.trim();
        if (title.isEmpty() || title.length() > 100) throw new Failure(422, "订阅名称须为 1–100 个字符");
        JSONObject source = ConfigEngine.parse(yaml), edits = ConfigEngine.edits();
        String id = UUID.randomUUID().toString().replace("-", ""), now = Instant.now().toString();
        JSONObject record = new JSONObject().put("id", id).put("title", title).put("source_type", type).put("source_url", url)
            .put("source_host", url.isEmpty() ? "" : new java.net.URI(url).getHost()).put("source_yaml", yaml).put("source", source)
            .put("edits", edits).put("revision", 1).put("enabled", true).put("interval_minutes", 0).put("created_at", now).put("updated_at", now)
            .put("refreshed_at", now).put("last_error", "").put("usage", usage == null ? JSONObject.NULL : usage).put("subscription_path", "/sub/" + id)
            .put("history", new JSONArray());
        return publish(record, preview(record, edits));
    }
    synchronized JSONObject saveEdits(String id, int revision, JSONObject edits) throws Exception {
        JSONObject value = record(id); check(value, revision);
        JSONObject preview = preview(value, edits);
        history(value); value.put("edits", ConfigEngine.copy(edits));
        return publish(value, preview);
    }
    synchronized JSONObject draft(String id, int revision, JSONObject edits) throws Exception { JSONObject value = record(id); check(value, revision); return preview(value, edits); }
    synchronized JSONObject refresh(String id, int revision, String yaml, Object usage) throws Exception {
        JSONObject value = record(id); check(value, revision);
        JSONObject source = ConfigEngine.parse(yaml);
        history(value); value.put("source", source).put("source_yaml", yaml).put("refreshed_at", Instant.now().toString()).put("last_error", "");
        if (usage != null) value.put("usage", usage);
        return publish(value, preview(value, value.getJSONObject("edits")));
    }
    synchronized JSONObject metadata(String id, int revision, JSONObject body) throws Exception {
        JSONObject value = record(id); check(value, revision);
        String title = body.optString("title", value.getString("title")).trim();
        if (title.isEmpty() || title.length() > 100) throw new Failure(422, "订阅名称须为 1–100 个字符");
        if (body.optInt("interval_minutes", 0) != 0) throw new Failure(501, "安卓自动刷新尚未接入，请使用手动刷新");
        history(value); value.put("title", title).put("enabled", body.optBoolean("enabled", value.getBoolean("enabled")));
        return publish(value, preview(value, value.getJSONObject("edits")));
    }
    synchronized void delete(String id, int revision) throws Exception {
        check(record(id), revision); JSONObject next = ConfigEngine.copy(state);
        next.getJSONObject("profiles").remove(id); next.getJSONObject("selections").remove(id); commit(next);
    }
    synchronized JSONArray histories(String id) throws Exception {
        JSONArray result = new JSONArray();
        for (Object item : ConfigEngine.items(record(id).getJSONArray("history"))) {
            JSONObject value = ConfigEngine.copy((JSONObject)item), snapshot = value.getJSONObject("record");
            value.remove("record"); value.put("size", snapshot.getString("source_yaml").getBytes(java.nio.charset.StandardCharsets.UTF_8).length); result.put(value);
        }
        return result;
    }
    synchronized JSONObject historical(String id, int historyId) throws Exception {
        for (Object item : ConfigEngine.items(record(id).getJSONArray("history"))) {
            JSONObject snapshot = (JSONObject)item;
            if (snapshot.getInt("id") == historyId) return ConfigEngine.copy(snapshot);
        }
        throw new Failure(404, "历史版本不存在");
    }
    synchronized JSONObject restore(String id, int revision, int historyId) throws Exception {
        JSONObject current = record(id); check(current, revision);
        JSONObject old = historical(id, historyId).getJSONObject("record"); history(current);
        for (String key : Arrays.asList("source", "source_yaml", "edits", "title", "enabled", "usage", "refreshed_at")) current.put(key, old.get(key));
        return publish(current, preview(current, current.getJSONObject("edits")));
    }
    synchronized JSONObject catalog(String id) throws Exception {
        JSONObject profile = get(id), config = profile.getJSONObject("preview").getJSONObject("config"), proxies = new JSONObject();
        for (String builtin : Arrays.asList("DIRECT", "REJECT")) proxies.put(builtin, new JSONObject().put("name", builtin).put("type", builtin.equals("DIRECT") ? "Direct" : "Reject"));
        for (Object item : ConfigEngine.items(config.getJSONArray("proxies"))) {
            JSONObject node = (JSONObject)item;
            proxies.put(node.getString("name"), new JSONObject().put("name", node.getString("name")).put("type", node.getString("type")));
        }
        JSONObject selections = state.getJSONObject("selections").optJSONObject(id);
        for (Object item : ConfigEngine.items(config.getJSONArray("proxy-groups"))) {
            JSONObject group = (JSONObject)item;
            String name = group.getString("name"), type = group.getString("type"), chosen = selections == null ? "" : selections.optString(name, "");
            JSONArray members = group.optJSONArray("proxies"); if (members == null) members = new JSONArray();
            if (!ConfigEngine.strings(members).contains(chosen)) chosen = members.length() == 0 ? "" : members.getString(0);
            proxies.put(name, new JSONObject().put("name", name).put("type", type.equals("select") ? "Selector" : type).put("all", members).put("now", chosen));
        }
        return new JSONObject().put("proxies", proxies).put("key", id + ":" + profile.getInt("revision")).put("live", false)
            .put("has_providers", config.has("proxy-providers")).put("profile_revision", profile.getInt("revision")).put("workspace_revision", 1);
    }
    synchronized void select(JSONObject body) throws Exception {
        select(body, null);
    }
    synchronized void validateSelection(JSONObject body, JSONObject live) throws Exception {
        String id = body.getString("profile_id"), group = body.getString("group"), name = body.getString("name");
        check(record(id), body.getInt("profile_revision"));
        if (body.getInt("workspace_revision") != 1) throw new Failure(409, "方案版本已改变，请刷新");
        JSONObject entry = (live == null ? catalog(id).getJSONObject("proxies") : live).optJSONObject(group);
        if (entry == null || !entry.optString("type").equals("Selector") || !ConfigEngine.strings(entry.getJSONArray("all")).contains(name)) throw new Failure(422, "节点不属于可选策略组");
    }
    synchronized void select(JSONObject body, JSONObject live) throws Exception {
        validateSelection(body, live);
        String id = body.getString("profile_id"), group = body.getString("group"), name = body.getString("name");
        JSONObject next = hotState(), selections = next.getJSONObject("selections");
        JSONObject profile = selections.optJSONObject(id); if (profile == null) { profile = new JSONObject(); selections.put(id, profile); }
        profile.put(group, name); commitHot(next);
    }
    synchronized JSONObject selections(String id) throws Exception {
        record(id);
        JSONObject selections = state.getJSONObject("selections").optJSONObject(id), result = new JSONObject();
        if (selections == null) return result;
        JSONObject catalog = catalog(id).getJSONObject("proxies");
        for (String name : ConfigEngine.keys(selections)) {
            JSONObject group = catalog.optJSONObject(name); String selected = selections.optString(name);
            if (name.equals("GLOBAL") ? catalog.has(selected) : group != null && group.optString("type").equals("Selector") && ConfigEngine.strings(group.getJSONArray("all")).contains(selected)) result.put(name, selected);
        }
        return result;
    }
    synchronized JSONObject settings() throws Exception { return ConfigEngine.copy(state.getJSONObject("settings")); }
    synchronized void saveSettings(JSONObject body) throws Exception {
        int port = body.getInt("mixed_port"); if (port < 1024 || port > 65535) throw new Failure(422, "端口必须为 1024–65535 之间的整数");
        JSONObject nextSettings = defaults();
        for (String key : ConfigEngine.keys(nextSettings)) if (body.has(key)) nextSettings.put(key, body.get(key));
        JSONObject dns = nextSettings.getJSONObject("dns_override");
        if (!Arrays.asList("fake-ip", "redir-host").contains(dns.getString("mode"))) throw new Failure(422, "DNS 模式无效");
        for (String key : Arrays.asList("nameserver", "fallback", "bootstrap", "proxy_nameserver", "fake_ip_filter")) ConfigEngine.strings(dns.getJSONArray(key));
        if (dns.getBoolean("enabled") && (dns.getJSONArray("nameserver").length() == 0 || dns.getJSONArray("bootstrap").length() == 0)) throw new Failure(422, "开启 DNS 覆写时请填写主 DNS 和引导 DNS");
        if (nextSettings.getBoolean("lan_auth") && (!nextSettings.getString("lan_username").matches("[A-Za-z0-9_-]{1,64}") || nextSettings.getString("lan_password").length() < 8)) throw new Failure(422, "请填写有效用户名及至少 8 位密码");
        JSONObject next = hotState(); next.put("settings", nextSettings); commitHot(next);
    }
}
