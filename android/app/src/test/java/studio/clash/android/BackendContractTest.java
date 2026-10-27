package studio.clash.android;

import org.json.*;
import org.junit.*;
import org.junit.rules.TemporaryFolder;
import java.io.*;
import java.nio.file.*;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.Assert.*;

public class BackendContractTest {
    @Rule public TemporaryFolder folder = new TemporaryFolder();
    private JSONObject fixtures() throws Exception {
        try (InputStream input = getClass().getResourceAsStream("/backend-contract.json")) {
            assertNotNull(input);
            return new JSONObject(new String(input.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8));
        }
    }
    @Test public void commonConfigurationsAndErrors() throws Exception {
        JSONObject fixtures = fixtures();
        JSONArray valid = fixtures.getJSONArray("valid");
        for (int i=0;i<valid.length();i++) {
            JSONObject row=valid.getJSONObject(i), config=ConfigEngine.preview(ConfigEngine.parse(row.getString("yaml")), ConfigEngine.edits()).getJSONObject("config");
            assertEquals(row.getInt("nodes"), config.getJSONArray("proxies").length());
            assertEquals(row.getInt("groups"), config.getJSONArray("proxy-groups").length());
            assertEquals(row.getJSONArray("rules").toString(), config.getJSONArray("rules").toString());
        }
        JSONArray invalid=fixtures.getJSONArray("invalid");
        for(int i=0;i<invalid.length();i++) {
            boolean rejected=false;
            try { ConfigEngine.parse(invalid.getString(i)); } catch(Exception expected) { rejected=true; }
            assertTrue(rejected);
        }
        JSONArray errors=fixtures.getJSONArray("errors");
        for(int i=0;i<errors.length();i++) {
            JSONObject row=errors.getJSONObject(i), error=ErrorContract.error(row.getInt("status"), ErrorContract.code(row.getInt("status")), "test");
            assertEquals(row.getString("code"),error.getString("code"));
            assertEquals(row.getBoolean("retryable"),error.getBoolean("retryable"));
        }
    }
    @Test public void deadlinesAndCancellationSurviveLateCallbacks() throws Exception {
        AtomicLong clock=new AtomicLong(10);
        LifecycleOperation old=new LifecycleOperation("old", 100, clock::get);
        old.check(); clock.set(110);
        try { old.check(); fail("late result accepted"); } catch(ProfileStore.Failure error) { assertEquals("OPERATION_CANCELLED",error.code); }
        LifecycleOperation next=new LifecycleOperation("next",100,clock::get);
        old.cancel(); next.check(); assertFalse(old.valid());
        next.cancel(); assertFalse(next.valid());
    }
    @Test public void migrationAndHotWritesPreserveColdDocument() throws Exception {
        File dir=folder.newFolder();
        ProfileStore store=new ProfileStore(dir);
        JSONObject row=store.create("test","file","",fixtures().getJSONArray("valid").getJSONObject(0).getString("yaml"),null);
        String id=row.getString("id");
        Path cold=dir.toPath().resolve("profiles-v1.json"), hot=dir.toPath().resolve("client-state-v2.json");
        byte[] before=Files.readAllBytes(cold);
        Files.delete(hot);
        store=new ProfileStore(dir);
        assertArrayEquals(before, Files.readAllBytes(cold));
        JSONObject choice=new JSONObject().put("profile_id",id).put("profile_revision",1).put("workspace_revision",1).put("group","Work").put("name","DIRECT");
        store.select(choice);
        assertArrayEquals(before,Files.readAllBytes(cold));
        assertEquals("DIRECT",new ProfileStore(dir).selections(id).getString("Work"));
        JSONObject stale=fixtures().getJSONObject("stale_revision");
        store.metadata(id,1,new JSONObject().put("title","updated"));
        try { store.delete(id,stale.getInt("request")); fail("stale revision accepted"); }
        catch(ProfileStore.Failure error) { assertEquals(stale.getInt("status"),error.status); }
        store.delete(id,stale.getInt("saved"));
        assertFalse(new JSONObject(Files.readString(hot)).getJSONObject("selections").has(id));
    }
    @Test public void failedHotReplacementKeepsAcknowledgedSelection() throws Exception {
        File dir=folder.newFolder(); ProfileStore store=new ProfileStore(dir);
        String id=store.create("test","file","",fixtures().getJSONArray("valid").getJSONObject(0).getString("yaml"),null).getString("id");
        JSONObject choice=new JSONObject().put("profile_id",id).put("profile_revision",1).put("workspace_revision",1).put("group","Work").put("name","A");
        store.select(choice);
        Path hot=dir.toPath().resolve("client-state-v2.json"), backup=dir.toPath().resolve("backup.json");
        Files.move(hot,backup); Files.createDirectory(hot);
        try { store.select(choice.put("name","DIRECT")); fail("write should fail"); } catch(IOException expected) { }
        assertEquals("A",store.selections(id).getString("Work"));
        Files.delete(hot); Files.move(backup,hot);
        assertEquals("A",new ProfileStore(dir).selections(id).getString("Work"));
    }
}
