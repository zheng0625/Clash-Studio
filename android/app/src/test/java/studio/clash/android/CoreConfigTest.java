package studio.clash.android;

import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class CoreConfigTest {
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
