package studio.clash.android;

import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class CoreConfigTest {
    @Test public void probeCacheTracksEffectiveDnsSettings() throws Exception {
        JSONObject source = new JSONObject("{\"proxies\":[],\"proxy-groups\":[],\"dns\":{\"nameserver\":[\"system\"]}}");
        JSONObject settings = ProfileStore.defaults();
        JSONObject plain = CoreConfig.prepare(source, settings, 17890);
        DelaySpec.sanitize(plain);
        String before = DelaySpec.configurationKey(plain);
        settings.put("dns_leak_prevention", true);
        JSONObject protectedConfig = CoreConfig.prepare(source, settings, 17890);
        DelaySpec.sanitize(protectedConfig);
        assertNotEquals(before, DelaySpec.configurationKey(protectedConfig));
        assertTrue(protectedConfig.getJSONObject("dns").getJSONArray("nameserver").getString(0).contains("#ClashStudio-DNS"));
        settings.put("dns_leak_prevention", false);
        JSONObject restored = CoreConfig.prepare(source, settings, 17890);
        DelaySpec.sanitize(restored);
        assertEquals(before, DelaySpec.configurationKey(restored));
    }
    @Test public void protectedDnsReplacesPoliciesAndCannotFallBackToDirect() throws Exception {
        JSONObject dns = new JSONObject().put("nameserver-policy", new JSONObject().put("+.example", "udp://127.0.0.1:5353#DIRECT"))
            .put("fallback", new JSONArray().put("system")).put("fallback-filter", new JSONObject())
            .put("proxy-server-nameserver-policy", new JSONObject()).put("prefer-h3", true)
            .put("proxy-server-nameserver", new JSONArray()).put("default-nameserver", new JSONArray()).put("direct-nameserver", new JSONArray());
        JSONObject source = new JSONObject().put("dns", dns).put("proxy-groups", new JSONArray().put(new JSONObject().put("name", "ClashStudio-DNS")));
        String original = source.toString();
        for (boolean override : new boolean[]{false, true}) {
            JSONObject settings = ProfileStore.defaults().put("dns_leak_prevention", true);
            settings.getJSONObject("dns_override").put("enabled", override);
            JSONObject config = CoreConfig.prepare(source, settings, 17890), protectedDns = config.getJSONObject("dns");
            assertEquals(original, source.toString());
            for (String key : new String[]{"nameserver-policy", "fallback", "fallback-filter", "proxy-server-nameserver-policy", "prefer-h3"}) assertFalse(protectedDns.has(key));
            JSONObject group = config.getJSONArray("proxy-groups").getJSONObject(1);
            assertEquals("ClashStudio-DNS-protected", group.getString("name"));
            assertTrue(group.getBoolean("include-all")); assertEquals("REJECT", group.getString("empty-fallback"));
            assertTrue(group.getString("exclude-type").contains("Direct"));
            assertTrue(protectedDns.getJSONArray("nameserver").getString(0).endsWith("#ClashStudio-DNS-protected"));
            assertTrue(protectedDns.getBoolean("enable")); assertTrue(protectedDns.getBoolean("respect-rules"));
            assertFalse(protectedDns.getBoolean("direct-nameserver-follow-policy"));
            for (String key : new String[]{"proxy-server-nameserver", "default-nameserver", "direct-nameserver"}) assertTrue(protectedDns.getJSONArray(key).length() > 0);
        }
        JSONObject restored = CoreConfig.prepare(source, ProfileStore.defaults(), 17890);
        assertEquals(1, restored.getJSONArray("proxy-groups").length());
        assertTrue(restored.getJSONObject("dns").has("nameserver-policy"));
        assertTrue(restored.getJSONObject("dns").has("fallback"));
    }
    @Test public void importedListenersCannotOpenPublicPortsOrDesktopTun() throws Exception {
        JSONObject source = new JSONObject("{\"external-controller\":\"0.0.0.0:9090\",\"allow-lan\":true,\"mixed-port\":80,\"port\":8000,\"tun\":{\"enable\":true},\"listeners\":[{\"port\":9000}],\"mode\":\"global\"}");
        JSONObject config = CoreConfig.prepare(source, ProfileStore.defaults(), 17890);
        assertFalse(config.has("external-controller")); assertFalse(config.has("listeners"));
        assertEquals("127.0.0.1", config.getString("bind-address")); assertFalse(config.getBoolean("allow-lan"));
        assertFalse(config.getJSONObject("tun").getBoolean("enable")); assertEquals(0, config.getInt("port"));
        assertEquals(17890, config.getInt("mixed-port")); assertEquals("global", config.getString("mode"));
        assertTrue(source.getBoolean("allow-lan"));
    }
    @Test public void dnsOverrideAndIpv6AreAppliedTogether() throws Exception {
        JSONObject settings = ProfileStore.defaults().put("ipv6", false);
        settings.getJSONObject("dns_override").put("enabled", true).put("mode", "redir-host")
            .put("nameserver", new JSONArray().put("https://dns.example/dns-query")).put("bootstrap", new JSONArray().put("1.1.1.1"));
        JSONObject config = CoreConfig.prepare(new JSONObject(), settings, 19090), dns = config.getJSONObject("dns");
        assertTrue(dns.getBoolean("enable")); assertEquals("", dns.getString("listen"));
        assertEquals("redir-host", dns.getString("enhanced-mode")); assertFalse(dns.getBoolean("ipv6"));
        assertEquals("https://dns.example/dns-query", dns.getJSONArray("nameserver").getString(0));
    }
    @Test public void providerPathsAreConfinedAndFileReferencesRejected() throws Exception {
        JSONObject source = new JSONObject("{\"proxy-providers\":{\"remote\":{\"type\":\"http\",\"url\":\"https://example.test/nodes\",\"path\":\"../../profiles-v1.json\"}}}");
        String path = CoreConfig.prepare(source, ProfileStore.defaults(), 17890).getJSONObject("proxy-providers").getJSONObject("remote").getString("path");
        assertTrue(path.startsWith("providers/")); assertFalse(path.contains(".."));
        source.getJSONObject("proxy-providers").getJSONObject("remote").put("type", "file");
        try { CoreConfig.prepare(source, ProfileStore.defaults(), 17890); fail("file providers must be explicit"); } catch (ProfileStore.Failure expected) { assertEquals(422, expected.status); }
    }
}
