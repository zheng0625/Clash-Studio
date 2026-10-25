package studio.clash.android;

import org.json.*;
import java.util.*;

/** Network listeners and routing are owned by Android, never by an imported profile. */
final class CoreConfig {
    static JSONObject prepare(JSONObject source, JSONObject settings, int port) throws Exception {
        if (port < 1024 || port > 65535) throw new ProfileStore.Failure(422, "代理端口必须为 1024–65535");
        JSONObject config = ConfigEngine.copy(source);
        for (String field : Arrays.asList("external-controller", "external-controller-tls", "external-controller-unix", "external-controller-pipe", "external-ui", "external-ui-url", "secret", "listeners", "authentication", "interface-name", "routing-mark", "ss-config", "vmess-config", "tuic-server")) config.remove(field);
        for (String field : Arrays.asList("port", "socks-port", "redir-port", "tproxy-port")) config.put(field, 0);
        config.put("mixed-port", port).put("allow-lan", false).put("bind-address", "127.0.0.1")
            .put("tun", new JSONObject().put("enable", false)).put("find-process-mode", "off")
            .put("ipv6", settings.optBoolean("ipv6", true)).put("log-level", "warning")
            .put("profile", new JSONObject().put("store-selected", false).put("store-fake-ip", true));
        if (!Arrays.asList("rule", "global", "direct").contains(config.optString("mode"))) config.put("mode", "rule");
        JSONObject dns = config.optJSONObject("dns"); if (dns == null) dns = new JSONObject();
        dns.put("enable", true).put("listen", "").put("ipv6", settings.optBoolean("ipv6", true));
        if (!dns.has("enhanced-mode")) dns.put("enhanced-mode", "fake-ip");
        dns.put("fake-ip-range", "198.19.0.1/16");
        if (!dns.has("nameserver")) dns.put("nameserver", new JSONArray().put("https://223.5.5.5/dns-query").put("https://1.1.1.1/dns-query"));
        if (!dns.has("default-nameserver")) dns.put("default-nameserver", new JSONArray().put("223.5.5.5").put("1.1.1.1"));
        JSONObject override = settings.optJSONObject("dns_override");
        if (override != null && override.optBoolean("enabled")) {
            dns.put("enhanced-mode", override.getString("mode"));
            String[][] fields = {{"nameserver","nameserver"},{"fallback","fallback"},{"bootstrap","default-nameserver"},{"proxy_nameserver","proxy-server-nameserver"},{"fake_ip_filter","fake-ip-filter"}};
            for (String[] pair : fields) dns.put(pair[1], override.getJSONArray(pair[0]));
        }
        config.put("dns", dns);
        // Prevent profile paths from escaping the private core directory.
        for (String field : Arrays.asList("proxy-providers", "rule-providers")) {
            JSONObject providers = config.optJSONObject(field);
            if (providers != null) for (String key : ConfigEngine.keys(providers)) {
                JSONObject provider = providers.getJSONObject(key);
                if (provider.optString("type").equals("file")) throw new ProfileStore.Failure(422, "安卓暂不支持引用外部文件的 Provider，请使用 HTTPS Provider");
                provider.put("path", "providers/" + UUID.nameUUIDFromBytes((field+key).getBytes(java.nio.charset.StandardCharsets.UTF_8)) + ".yaml");
            }
        }
        return config;
    }
}
