package studio.clash.android;

import static org.junit.Assert.*;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import java.time.Instant;

/** Delay-probe rules: endpoints, bounds, node kinds, response shape and probe-config sanitization. */
public class DelaySpecTest {
    @Test public void endpointsAreLimitedToHttps204Probes() throws Exception {
        assertEquals("https://cp.cloudflare.com/generate_204", DelaySpec.url("cloudflare"));
        assertEquals("https://www.gstatic.com/generate_204", DelaySpec.url("gstatic"));
        try { DelaySpec.url("example"); fail("unexpected endpoint accepted"); }
        catch (ProfileStore.Failure error) { assertEquals(422, error.status); }
    }
    @Test public void timeoutStaysWithinFrontendBounds() throws Exception {
        assertEquals(1000, DelaySpec.timeout(1000));
        assertEquals(10000, DelaySpec.timeout(10000));
        for (int value : new int[]{999, 10001, 0, -1}) try { DelaySpec.timeout(value); fail("timeout " + value + " accepted"); }
            catch (ProfileStore.Failure error) { assertEquals(422, error.status); }
    }
    @Test public void onlyRealNodesAreMeasurable() throws Exception {
        JSONObject node = new JSONObject().put("name", "hk-01").put("type", "Socks5");
        assertTrue(DelaySpec.measurable(node));
        assertFalse(DelaySpec.measurable(null));
        assertFalse(DelaySpec.measurable(new JSONObject().put("type", "Selector").put("all", new JSONArray().put("hk-01"))));
        for (String type : new String[]{"Direct", "Reject", "REJECT-DROP", "Pass", "dns", "RejectDrop"})
            assertFalse(type, DelaySpec.measurable(new JSONObject().put("type", type)));
    }
    @Test public void negativeDelayBecomesUnreachableWithNullMilliseconds() throws Exception {
        JSONObject ok = DelaySpec.result("hk-01", "cloudflare", 5000, 182, Instant.parse("2026-10-24T08:00:00Z"));
        assertEquals("ok", ok.getString("status"));
        assertEquals(182, ok.getInt("delay_ms"));
        assertEquals("hk-01", ok.getString("name"));
        assertEquals("cloudflare", ok.getString("endpoint"));
        assertEquals(5000, ok.getInt("timeout_ms"));
        JSONObject unreachable = DelaySpec.result("hk-02", "gstatic", 5000, -1, Instant.parse("2026-10-24T08:00:00Z"));
        assertEquals("unreachable", unreachable.getString("status"));
        assertTrue(unreachable.isNull("delay_ms"));
    }
    @Test public void sanitizeTurnsAutoGroupsManualAndDisablesProviderChecks() throws Exception {
        JSONObject config = new JSONObject()
            .put("proxies", new JSONArray().put(new JSONObject().put("name", "hk-01").put("type", "socks5")))
            .put("proxy-groups", new JSONArray()
                .put(new JSONObject().put("name", "auto").put("type", "url-test").put("proxies", new JSONArray().put("hk-01")))
                .put(new JSONObject().put("name", "pick").put("type", "select").put("proxies", new JSONArray().put("hk-01"))))
            .put("proxy-providers", new JSONObject().put("feed", new JSONObject().put("type", "http").put("url", "https://example.invalid/feed")))
            .put("rule-providers", new JSONObject().put("rules", new JSONObject().put("type", "http").put("url", "https://example.invalid/rules")))
            .put("rules", new JSONArray().put("DOMAIN-SUFFIX,example.com,pick"));
        DelaySpec.sanitize(config);
        JSONArray groups = config.getJSONArray("proxy-groups");
        assertEquals("select", groups.getJSONObject(0).getString("type"));
        assertEquals("select", groups.getJSONObject(1).getString("type"));
        assertFalse(config.has("rule-providers"));
        assertEquals(1, config.getJSONArray("rules").length());
        assertEquals("MATCH,DIRECT", config.getJSONArray("rules").getString(0));
        assertFalse(config.getJSONObject("proxy-providers").getJSONObject("feed").getJSONObject("health-check").getBoolean("enable"));
        assertEquals("socks5", config.getJSONArray("proxies").getJSONObject(0).getString("type"));
    }
    @Test public void sanitizeAcceptsConfigsWithoutGroupsOrProviders() throws Exception {
        JSONObject config = new JSONObject().put("proxies", new JSONArray()).put("rules", new JSONArray());
        DelaySpec.sanitize(config);
        assertEquals("MATCH,DIRECT", config.getJSONArray("rules").getString(0));
    }
}
