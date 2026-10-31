package studio.clash.android;

import org.json.JSONArray;
import org.json.JSONObject;
import java.time.Instant;
import java.util.*;

/** Pure delay-probe rules shared by the running core and the on-demand probe core. */
final class DelaySpec {
    private static final Map<String,String> ENDPOINTS = new HashMap<>();
    static {
        ENDPOINTS.put("cloudflare", "https://cp.cloudflare.com/generate_204");
        ENDPOINTS.put("gstatic", "https://www.gstatic.com/generate_204");
    }
    private static final Set<String> NON_PROXIES = new HashSet<>(Arrays.asList("direct", "reject", "reject-drop", "rejectdrop", "pass", "dns"));
    private DelaySpec() { }
    static String url(String endpoint) throws ProfileStore.Failure {
        String value = ENDPOINTS.get(endpoint);
        if (value == null) throw new ProfileStore.Failure(422, "检测地址无效");
        return value;
    }
    static int timeout(int timeoutMs) throws ProfileStore.Failure {
        if (timeoutMs < 1000 || timeoutMs > 10000) throw new ProfileStore.Failure(422, "测速超时须为 1000–10000 毫秒");
        return timeoutMs;
    }
    static boolean measurable(JSONObject node) {
        return node != null && !node.has("all") && !NON_PROXIES.contains(node.optString("type").toLowerCase(Locale.ROOT));
    }
    static String configurationKey(JSONObject config) throws Exception {
        StringBuilder key = new StringBuilder();
        byte[] bytes = ConfigEngine.dump(config).getBytes(java.nio.charset.StandardCharsets.UTF_8);
        for (byte value : java.security.MessageDigest.getInstance("SHA-256").digest(bytes)) key.append(String.format("%02x", value));
        return key.toString();
    }
    /** The bridge reports failure as a negative delay; zero never survives the bridge. */
    static JSONObject result(String name, String endpoint, int timeoutMs, int delay, Instant checkedAt) throws Exception {
        return new JSONObject().put("name", name).put("endpoint", endpoint).put("timeout_ms", timeoutMs)
            .put("status", delay > 0 ? "ok" : "unreachable").put("delay_ms", delay > 0 ? delay : JSONObject.NULL)
            .put("checked_at", checkedAt.toString());
    }
    /** Loopback probe shape: manual groups, silent providers, no user rules; matching the desktop probe core. */
    static void sanitize(JSONObject config) throws Exception {
        JSONArray groups = config.optJSONArray("proxy-groups");
        if (groups != null) for (Object item : ConfigEngine.items(groups)) {
            JSONObject group = (JSONObject)item;
            if (Arrays.asList("url-test", "fallback", "load-balance").contains(group.optString("type"))) group.put("type", "select");
        }
        config.remove("rule-providers");
        config.put("rules", new JSONArray().put("MATCH,DIRECT"));
        JSONObject providers = config.optJSONObject("proxy-providers");
        if (providers != null) for (String key : ConfigEngine.keys(providers))
            providers.getJSONObject(key).put("health-check", new JSONObject().put("enable", false));
    }
}
