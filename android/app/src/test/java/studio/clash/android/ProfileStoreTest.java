package studio.clash.android;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.*;
import org.junit.rules.TemporaryFolder;
import java.io.File;
import java.nio.file.Files;
import java.util.concurrent.*;
import static org.junit.Assert.*;

public class ProfileStoreTest {
    @Rule public TemporaryFolder folder = new TemporaryFolder();
    private File directory;
    private ProfileStore store;
    private static final String YAML = "proxies:\n - {name: A, type: socks5, server: example.invalid, port: 9}\n - {name: B, type: socks5, server: example.invalid, port: 9}\nproxy-groups:\n - {name: 出口, type: select, proxies: [A, B, DIRECT]}\nrules: [MATCH,出口]\n".replace("rules: [MATCH,出口]", "rules: ['MATCH,出口']");
    @Before public void setup() throws Exception { directory = folder.newFolder(); store = new ProfileStore(directory); }
    private JSONObject create() throws Exception { return store.create("测试订阅", "file", "", YAML, null); }
    private interface Operation { void run() throws Exception; }
    private void failure(int status, Operation operation) throws Exception {
        try { operation.run(); fail("Expected failure " + status); } catch (ProfileStore.Failure error) { assertEquals(status, error.status); }
    }
    @Test public void persistsProfilesAndDoesNotExposeSecretsInList() throws Exception {
        JSONObject profile = create(); String id = profile.getString("id");
        ProfileStore reopened = new ProfileStore(directory);
        assertEquals(2, reopened.get(id).getInt("proxy_count"));
        assertEquals("测试订阅", reopened.list().getJSONObject(0).getString("title"));
        assertFalse(reopened.list().getJSONObject(0).has("source_yaml"));
        assertFalse(reopened.list().getJSONObject(0).has("source_url"));
        profile.put("title", "外部修改"); assertEquals("测试订阅", reopened.get(id).getString("title"));
    }
    @Test public void renamesReferencesAndRestoresHistory() throws Exception {
        JSONObject profile = create(), edits = ConfigEngine.copy(profile.getJSONObject("edits")); String id = profile.getString("id");
        edits.getJSONObject("proxy_renames").put("A", "香港");
        edits.getJSONObject("group_overrides").put("出口", new JSONObject().put("name", "新出口"));
        JSONObject saved = store.saveEdits(id, 1, edits), config = saved.getJSONObject("preview").getJSONObject("config");
        assertEquals("香港", config.getJSONArray("proxies").getJSONObject(0).getString("name"));
        assertEquals("香港", config.getJSONArray("proxy-groups").getJSONObject(0).getJSONArray("proxies").getString(0));
        assertEquals("MATCH,新出口", config.getJSONArray("rules").getString(0));
        assertEquals(2, saved.getInt("revision"));
        assertEquals(1, store.histories(id).length());
        assertEquals(3, store.restore(id, 2, 1).getInt("revision"));
        assertEquals("A", store.get(id).getJSONObject("preview").getJSONObject("config").getJSONArray("proxies").getJSONObject(0).getString("name"));
    }
    @Test public void invalidEditsAndRefreshKeepPublishedData() throws Exception {
        JSONObject profile = create(), edits = ConfigEngine.copy(profile.getJSONObject("edits")); String id = profile.getString("id");
        edits.getJSONObject("group_overrides").put("出口", new JSONObject().put("proxies", new JSONArray().put("missing")));
        assertTrue(store.draft(id, 1, edits).getJSONArray("errors").length() > 0);
        failure(422, () -> store.saveEdits(id, 1, edits));
        failure(422, () -> store.refresh(id, 1, YAML.replace("proxies: [A, B, DIRECT]", "proxies: [missing]"), null));
        assertEquals(1, store.get(id).getInt("revision"));
        assertEquals(YAML, new ProfileStore(directory).get(id).getString("source_yaml"));
    }
    @Test public void rejectsStaleDeleteEditAndSelection() throws Exception {
        String id = create().getString("id");
        store.metadata(id, 1, new JSONObject().put("title", "新版"));
        failure(409, () -> store.delete(id, 1));
        failure(409, () -> store.saveEdits(id, 1, ConfigEngine.edits()));
        failure(409, () -> store.select(new JSONObject().put("profile_id", id).put("profile_revision", 1).put("workspace_revision", 1).put("group", "出口").put("name", "B")));
        assertEquals("新版", new ProfileStore(directory).get(id).getString("title"));
    }
    @Test public void selectionsPersistAndRejectForeignMembers() throws Exception {
        String id = create().getString("id");
        JSONObject selection = new JSONObject().put("profile_id", id).put("profile_revision", 1).put("workspace_revision", 1).put("group", "出口").put("name", "B");
        store.select(selection);
        assertEquals("B", new ProfileStore(directory).catalog(id).getJSONObject("proxies").getJSONObject("出口").getString("now"));
        selection.put("name", "missing"); failure(422, () -> store.select(selection));
        assertEquals("B", store.catalog(id).getJSONObject("proxies").getJSONObject("出口").getString("now"));
    }
    @Test public void excludesNodesAndPreservesRuleOrder() throws Exception {
        JSONObject profile = create(), edits = ConfigEngine.copy(profile.getJSONObject("edits"));
        edits.getJSONArray("excluded_proxies").put("B");
        edits.getJSONArray("added_rules").put("DOMAIN,example.org,A");
        edits.getJSONArray("rule_order").put("DOMAIN,example.org,A").put("MATCH,出口");
        JSONObject config = store.saveEdits(profile.getString("id"), 1, edits).getJSONObject("preview").getJSONObject("config");
        assertEquals(1, config.getJSONArray("proxies").length());
        assertEquals(2, config.getJSONArray("proxy-groups").getJSONObject(0).getJSONArray("proxies").length());
        assertEquals("DOMAIN,example.org,A", config.getJSONArray("rules").getString(0));
    }
    @Test public void rejectsDuplicateKeysUnsafeTagsAndAliasExpansion() throws Exception {
        for (String yaml : new String[]{"proxies: []\nproxies: []", "!!java.net.URL ['https://example.invalid']", "proxies: &x [*x]"}) {
            try { store.create("非法", "file", "", yaml, null); fail("Must reject YAML"); } catch (Exception expected) { }
        }
        assertEquals(0, store.list().length());
    }
    @Test public void cyclicGroupsCannotBePublished() throws Exception {
        JSONObject profile = create(), edits = ConfigEngine.copy(profile.getJSONObject("edits"));
        edits.getJSONObject("group_overrides").put("出口", new JSONObject().put("proxies", new JSONArray().put("出口")));
        failure(422, () -> store.saveEdits(profile.getString("id"), 1, edits));
        assertEquals(1, store.get(profile.getString("id")).getInt("revision"));
    }
    @Test public void settingsPersistAndInvalidUpdatesAreAtomic() throws Exception {
        JSONObject settings = store.settings(); settings.put("mixed_port", 19090); store.saveSettings(settings);
        assertEquals(19090, new ProfileStore(directory).settings().getInt("mixed_port"));
        settings.put("mixed_port", 80); failure(422, () -> store.saveSettings(settings));
        assertEquals(19090, store.settings().getInt("mixed_port"));
    }
    @Test public void dnsProtectionPersistsWhenEnabledAndDisabled() throws Exception {
        assertFalse(store.settings().optBoolean("dns_leak_prevention", false));
        for (boolean enabled : new boolean[]{true, false}) {
            store.saveSettings(store.settings().put("dns_leak_prevention", enabled));
            assertEquals(enabled, new ProfileStore(directory).settings().getBoolean("dns_leak_prevention"));
        }
    }
    @Test public void concurrentChangesCannotLoseUpdates() throws Exception {
        String id = create().getString("id"); ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Callable<Boolean> edit = () -> { try { store.metadata(id, 1, new JSONObject().put("title", Thread.currentThread().getName())); return true; } catch (ProfileStore.Failure error) { assertEquals(409, error.status); return false; } };
            Future<Boolean> a = pool.submit(edit), b = pool.submit(edit);
            assertNotEquals(a.get(), b.get()); assertEquals(2, new ProfileStore(directory).get(id).getInt("revision"));
        } finally { pool.shutdownNow(); }
    }
    @Test public void corruptStoreIsPreservedAndNeverReset() throws Exception {
        File data = new File(directory, "profiles-v1.json"); Files.write(data.toPath(), "broken".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        try { new ProfileStore(directory); fail("Must reject corrupt data"); } catch (Exception expected) { }
        assertEquals("broken", new String(Files.readAllBytes(data.toPath()), java.nio.charset.StandardCharsets.UTF_8));
    }
    @Test public void nativeApiImportsAndRejectsInsecureUrlBeforeNetwork() throws Exception {
        NativeApi api = new NativeApi(directory);
        NativeApi.Response imported = api.request("/api/subscriptions", "POST", new JSONObject().put("title", "演示").put("source_type", "demo"));
        assertEquals(200, imported.status);
        assertEquals(1, ((JSONArray)api.request("/api/subscriptions", "GET", null).data).length());
        assertEquals(422, api.request("/api/subscriptions", "POST", new JSONObject().put("title", "HTTP").put("source_type", "url").put("source_url", "http://example.invalid/config")).status);
        assertEquals(403, api.request("https://example.invalid/api/subscriptions", "GET", null).status);
    }
    @Test public void activityHostReinitializationCannotOverwriteAnotherHostsChanges() throws Exception {
        NativeApi first = NativeApi.open(directory), second = NativeApi.open(directory);
        assertEquals(200, first.request("/api/subscriptions", "POST", new JSONObject().put("title", "共享后端").put("source_type", "demo")).status);
        JSONObject settings = ProfileStore.defaults().put("mixed_port", 23456);
        assertEquals(200, second.request("/api/client/settings", "PUT", settings).status);
        ProfileStore reopened = new ProfileStore(directory);
        assertEquals(1, reopened.list().length());
        assertEquals(23456, reopened.settings().getInt("mixed_port"));
    }
}
