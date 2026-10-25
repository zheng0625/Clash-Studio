package studio.clash.android;
import org.junit.Test;
import static org.junit.Assert.*;
public class SubscriptionQrTest {
    @Test public void httpsQueryAndEscapesArePreserved() throws Exception {
        assertEquals("https://example.invalid/sub?token=test%2Bvalue",SubscriptionQr.subscriptionUrl("  https://example.invalid/sub?token=test%2Bvalue  "));
    }
    @Test public void installLinkDecodesNestedUrlOnce() throws Exception {
        assertEquals("https://example.invalid/sub?token=test%2Bvalue",SubscriptionQr.subscriptionUrl("clash://install-config?url=https%3A%2F%2Fexample.invalid%2Fsub%3Ftoken%3Dtest%252Bvalue&name=review"));
    }
    @Test public void unsupportedSchemesCredentialsAndFragmentsAreRejected() throws Exception {
        for(String value:new String[]{"http://example.invalid/sub","https://user:pass@example.invalid/sub","javascript:alert(1)","ss://test","https://example.invalid/sub#fragment","clash://other?url=https%3A%2F%2Fexample.invalid"})
            try{SubscriptionQr.subscriptionUrl(value);fail(value);}catch(IllegalArgumentException expected){}
    }
}
