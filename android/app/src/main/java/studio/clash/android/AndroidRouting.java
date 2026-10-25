package studio.clash.android;

import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Per-subscription routing overlays; the downloaded subscription is never rewritten. */
final class AndroidRouting {
    private final Path file;
    private JSONObject state;
    AndroidRouting(File directory) throws Exception {
        file = directory.toPath().resolve("routing-v1.json");
        if (Files.exists(file) && Files.size(file) > 8 * 1024 * 1024) throw new IOException("routing store size");
        state = Files.exists(file) ? new JSONObject(new String(Files.readAllBytes(file), StandardCharsets.UTF_8))
            : new JSONObject().put("revision", 1).put("profiles", new JSONObject());
    }
    synchronized int revision() throws Exception { return state.getInt("revision"); }
    synchronized JSONObject get(String id, JSONObject config) throws Exception {
        JSONArray rules = state.getJSONObject("profiles").optJSONArray(id);
        return new JSONObject().put("revision", revision()).put("rules", rules == null ? new JSONArray() : new JSONArray(rules.toString()))
            .put("targets", targets(config));
    }
    static JSONArray targets(JSONObject config) throws Exception {
        LinkedHashSet<String> values = new LinkedHashSet<>(Arrays.asList("DIRECT", "REJECT"));
        for (String field : Arrays.asList("proxies", "proxy-groups"))
            for (Object item : ConfigEngine.items(config.optJSONArray(field) == null ? new JSONArray() : config.getJSONArray(field)))
                values.add(((JSONObject)item).getString("name"));
        return new JSONArray(values);
    }
    synchronized JSONObject save(String id, int revision, JSONArray rules, JSONObject config) throws Exception {
        if (revision != revision()) throw new ProfileStore.Failure(409, "分流规则已改变，请重新加载后保存");
        JSONArray checked = validate(rules, config);
        JSONObject next = new JSONObject(state.toString());
        next.put("revision", revision + 1);
        if (checked.length() == 0) next.getJSONObject("profiles").remove(id);
        else next.getJSONObject("profiles").put(id, checked);
        byte[] bytes = next.toString().getBytes(StandardCharsets.UTF_8);
        if (bytes.length > 8 * 1024 * 1024) throw new ProfileStore.Failure(413, "分流规则数据过大");
        Path temporary = Files.createTempFile(file.getParent(), "routing-", ".tmp");
        try {
            try (FileOutputStream output = new FileOutputStream(temporary.toFile())) { output.write(bytes); output.getFD().sync(); }
            Files.move(temporary, file, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            state = next;
        } finally { Files.deleteIfExists(temporary); }
        return get(id, config);
    }
    static JSONArray validate(JSONArray rules, JSONObject config) throws Exception {
        if (rules.length() > 500) throw new ProfileStore.Failure(422, "每份订阅最多保存 500 条精确分流规则");
        Set<String> targets = new HashSet<>(ConfigEngine.strings(targets(config)));
        JSONArray result = new JSONArray();
        for (Object item : ConfigEngine.items(rules)) {
            if (!(item instanceof JSONObject)) throw new ProfileStore.Failure(422, "分流规则格式无效");
            JSONObject rule = (JSONObject)item;
            String kind = rule.getString("kind"), value = rule.getString("value").trim(), target = rule.getString("target");
            if (value.isEmpty() || value.length() > 253 || value.matches("(?s).*[\\s,\\r\\n].*")) throw new ProfileStore.Failure(422, "匹配值不能为空，且不能包含空格、逗号或换行");
            if (!targets.contains(target) || target.contains(",") || target.contains("\n") || target.contains("\r"))
                throw new ProfileStore.Failure(422, "目标出口已不存在，请重新选择");
            switch (kind) {
                case "DOMAIN": case "DOMAIN-SUFFIX":
                    try { value = java.net.IDN.toASCII(value, java.net.IDN.USE_STD3_ASCII_RULES).toLowerCase(Locale.ROOT); }
                    catch (Exception error) { throw new ProfileStore.Failure(422, "请输入域名，不要包含协议或路径"); }
                    if (value.startsWith(".") || value.endsWith(".") || value.length() > 253) throw new ProfileStore.Failure(422, "域名格式无效");
                    break;
                case "IP-CIDR": case "IP-CIDR6":
                    String[] parts = value.split("/", -1);
                    try {
                        boolean ipv6 = kind.equals("IP-CIDR6");
                        if (parts.length != 2 || !parts[0].matches(ipv6 ? "[0-9a-fA-F:]+" : "[0-9.]+")) throw new Exception();
                        java.net.InetAddress parsed = java.net.InetAddress.getByName(parts[0]);
                        byte[] address = parsed.getAddress();
                        int prefix = Integer.parseInt(parts[1]);
                        if (address.length != (ipv6 ? 16 : 4) || prefix < 0 || prefix > (ipv6 ? 128 : 32)) throw new Exception();
                        if (!ipv6 && parts[0].split("\\.", -1).length != 4) throw new Exception();
                        value = parsed.getHostAddress() + "/" + prefix;
                    } catch (Exception error) { throw new ProfileStore.Failure(422, "请输入有效网段及前缀长度"); }
                    break;
                case "PROCESS-NAME":
                    if (!value.matches("[A-Za-z0-9_]+(?:\\.[A-Za-z0-9_]+)+")) throw new ProfileStore.Failure(422, "安卓应用匹配请使用包名，例如 com.android.chrome");
                    break;
                default: throw new ProfileStore.Failure(422, "不支持的分流匹配类型");
            }
            result.put(new JSONObject().put("kind", kind).put("value", value).put("target", target).put("enabled", rule.optBoolean("enabled", true)));
        }
        return result;
    }
    synchronized JSONObject overlay(String id, JSONObject config) throws Exception {
        JSONObject copy = ConfigEngine.copy(config);
        JSONArray rules = state.getJSONObject("profiles").optJSONArray(id);
        if (rules == null || rules.length() == 0) return copy;
        JSONArray checked = validate(rules, config), merged = new JSONArray();
        for (Object item : ConfigEngine.items(checked)) {
            JSONObject rule = (JSONObject)item;
            if (rule.getBoolean("enabled")) merged.put(rule.getString("kind") + "," + rule.getString("value") + "," + rule.getString("target"));
        }
        for (Object item : ConfigEngine.items(copy.getJSONArray("rules"))) merged.put(item);
        copy.put("rules", merged);
        return copy;
    }
}
