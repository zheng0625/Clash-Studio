package studio.clash.android;

import static org.junit.Assert.*;
import org.junit.Test;

/** Notice-stub rejection for subscription downloads; real configs and malformed YAML pass through. */
public class ConfigEngineTest {
    private static final String STUB_MEMBER =
        "proxies: []\nproxy-groups:\n  - name: FK\n    type: select\n    proxies: [请下载Clash Verge for windows]\nrules:\n  - MATCH,FK\n";
    private static final String STUB_GROUP_NAME =
        "proxy-groups:\n  - name: 请下载 mihomo 客户端\n    type: select\n    proxies: [DIRECT]\nrules:\n  - MATCH,请下载 mihomo 客户端\n";
    private static final String REAL =
        "proxies:\n  - {name: hk-01, type: socks5, server: example.invalid, port: 9}\nproxy-groups:\n  - {name: pick, type: select, proxies: [hk-01, DIRECT]}\nrules:\n  - MATCH,pick\n";

    @Test public void noticeStubMemberIsRejected() throws Exception {
        try { ConfigEngine.rejectClientNotice(STUB_MEMBER); fail("notice stub accepted"); }
        catch (ProfileStore.Failure error) { assertEquals(502, error.status); assertTrue(error.getMessage().contains("提示配置")); }
    }
    @Test public void noticeStubGroupNameIsRejected() throws Exception {
        try { ConfigEngine.rejectClientNotice(STUB_GROUP_NAME); fail("notice stub accepted"); }
        catch (ProfileStore.Failure error) { assertEquals(502, error.status); }
    }
    @Test public void realConfigPasses() throws Exception {
        ConfigEngine.rejectClientNotice(REAL);
    }
    @Test public void providerOnlyConfigPasses() throws Exception {
        ConfigEngine.rejectClientNotice("proxy-providers:\n  feed: {type: http, url: 'https://example.invalid/feed'}\nproxy-groups:\n  - {name: pick, type: select, proxies: [DIRECT], use: [feed]}\nrules:\n  - MATCH,pick\n");
    }
    @Test public void malformedYamlIsLeftToImportErrors() throws Exception {
        ConfigEngine.rejectClientNotice("请下载Clash Verge for windows");
        ConfigEngine.rejectClientNotice("proxies: [");
    }
    @Test public void downloadNoticeWithoutClientKeywordPasses() throws Exception {
        ConfigEngine.rejectClientNotice("proxy-groups:\n  - {name: 通知, type: select, proxies: [余额已用完]}\nrules:\n  - MATCH,通知\n");
    }
}
