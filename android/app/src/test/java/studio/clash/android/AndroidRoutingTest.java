package studio.clash.android;
import org.junit.*;
import org.junit.rules.TemporaryFolder;
import org.json.*;
import static org.junit.Assert.*;
public class AndroidRoutingTest {
    @Rule public TemporaryFolder folder = new TemporaryFolder();
    private JSONObject config() throws Exception { return ConfigEngine.parse(NativeApi.DEMO); }
    private JSONArray rules(String kind, String value, String target) throws Exception {
        return new JSONArray().put(new JSONObject().put("kind",kind).put("value",value).put("target",target).put("enabled",true));
    }
    @Test public void orderedOverlayPersistsWithoutEditingSource() throws Exception {
        AndroidRouting routing = new AndroidRouting(folder.getRoot()); JSONObject original=config();String snapshot=original.toString();
        JSONArray rules=rules("DOMAIN-SUFFIX","Example.COM","REJECT");rules.put(new JSONObject().put("kind","PROCESS-NAME").put("value","com.android.chrome").put("target","DIRECT").put("enabled",true));
        routing.save("one",1,rules,original);
        JSONObject merged=new AndroidRouting(folder.getRoot()).overlay("one",original);
        assertEquals("DOMAIN-SUFFIX,example.com,REJECT",merged.getJSONArray("rules").getString(0));
        assertEquals("PROCESS-NAME,com.android.chrome,DIRECT",merged.getJSONArray("rules").getString(1));
        assertEquals(original.getJSONArray("rules").getString(0),merged.getJSONArray("rules").getString(2));
        assertEquals(snapshot,original.toString());assertEquals(snapshot,routing.overlay("other",original).toString());
    }
    @Test public void staleWriteAndInvalidTargetPreserveSavedRules() throws Exception {
        AndroidRouting routing=new AndroidRouting(folder.getRoot());routing.save("one",1,rules("DOMAIN","example.com","DIRECT"),config());
        try{routing.save("one",1,new JSONArray(),config());fail();}catch(ProfileStore.Failure error){assertEquals(409,error.status);}
        try{routing.save("one",2,rules("DOMAIN","example.com","missing"),config());fail();}catch(ProfileStore.Failure error){assertEquals(422,error.status);}
        assertEquals(2,routing.revision());assertEquals(1,new AndroidRouting(folder.getRoot()).get("one",config()).getJSONArray("rules").length());
    }
    @Test public void invalidMatchersAndRuleInjectionAreRejected() throws Exception {
        String[][] invalid={{"DOMAIN","https://example.com"},{"DOMAIN","example.com,REJECT"},{"DOMAIN-SUFFIX",".example.com"},{"IP-CIDR","999.1.2.3/24"},{"IP-CIDR","1.2.3/24"},{"IP-CIDR6","2001:db8::/129"},{"PROCESS-NAME","Chrome"},{"MATCH","all"}};
        for(String[] value:invalid)try{AndroidRouting.validate(rules(value[0],value[1],"DIRECT"),config());fail(value[0]);}catch(ProfileStore.Failure expected){assertEquals(422,expected.status);}
    }
    @Test public void disabledRulesAreRetainedButNotCompiled() throws Exception {
        AndroidRouting routing=new AndroidRouting(folder.getRoot());JSONArray rules=rules("IP-CIDR","192.168.0.0/16","DIRECT");rules.getJSONObject(0).put("enabled",false);
        routing.save("one",1,rules,config());assertEquals(1,routing.get("one",config()).getJSONArray("rules").length());assertEquals(config().getJSONArray("rules").toString(),routing.overlay("one",config()).getJSONArray("rules").toString());
    }
    @Test public void ipv6AndPackageMatchersAreAccepted() throws Exception {
        assertEquals(1,AndroidRouting.validate(rules("IP-CIDR6","2001:db8::/32","DIRECT"),config()).length());
        assertEquals("192.168.1.1/24",AndroidRouting.validate(rules("IP-CIDR","192.168.1.01/24","DIRECT"),config()).getJSONObject(0).getString("value"));
        assertEquals(1,AndroidRouting.validate(rules("PROCESS-NAME","com.android.chrome","REJECT"),config()).length());
    }
}
