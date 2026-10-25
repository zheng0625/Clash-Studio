package studio.clash.vpnprobe;

import android.app.Activity;
import android.os.Bundle;
import android.net.*;
import android.widget.TextView;
import org.json.JSONObject;
import java.net.*;
import java.io.*;

/** Separate UID proves that VPN captures another application's TCP and UDP traffic. */
public class ProbeActivity extends Activity {
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        TextView text = new TextView(this); text.setText("Checking VPN TCP / UDP…"); setContentView(text);
        new Thread(() -> {
            JSONObject result = new JSONObject();
            try {
                ConnectivityManager manager = getSystemService(ConnectivityManager.class);
                NetworkCapabilities caps = manager.getNetworkCapabilities(manager.getActiveNetwork());
                result.put("vpn", caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN));
                result.put("uid", android.os.Process.myUid());
                try (DatagramSocket socket = new DatagramSocket()) {
                    socket.setSoTimeout(8000);
                    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                    DataOutputStream dns = new DataOutputStream(bytes);
                    dns.writeShort(1234); dns.writeShort(256); dns.writeShort(1); dns.writeShort(0); dns.writeShort(0); dns.writeShort(0);
                    for (String part : "example.com".split("\\.")) { dns.writeByte(part.length()); dns.writeBytes(part); }
                    dns.writeByte(0); dns.writeShort(1); dns.writeShort(1);
                    byte[] packet = bytes.toByteArray(); socket.send(new DatagramPacket(packet, packet.length, InetAddress.getByName("198.19.0.2"), 53));
                    DatagramPacket answer = new DatagramPacket(new byte[4096], 4096); socket.receive(answer);
                    byte[] data = answer.getData();
                    result.put("udp_dns", answer.getLength() > 12 && data[0] == 4 && (data[1]&255) == 210 && (data[3]&15) == 0 && ((data[6]&255)*256+(data[7]&255)) > 0);
                } catch (Exception error) { result.put("udp_dns", false); result.put("dns_error", error.toString()); }
                result.put("resolved", java.util.Arrays.toString(InetAddress.getAllByName("www.baidu.com")));
                HttpURLConnection connection = (HttpURLConnection)new URL("https://www.baidu.com/robots.txt?clashstudio=" + System.nanoTime()).openConnection(java.net.Proxy.NO_PROXY);
                connection.setConnectTimeout(10000); connection.setReadTimeout(10000); connection.setUseCaches(false);
                try {
                    result.put("http_status", connection.getResponseCode());
                    try (InputStream input = connection.getInputStream()) { byte[] buffer = new byte[16384]; int count = input.read(buffer); result.put("bytes", count); }
                    result.put("https", true);
                } finally { connection.disconnect(); }
            } catch (Exception error) { try { result.put("https", false); result.put("error", error.toString()); } catch (Exception ignored) { } }
            try (FileOutputStream file = openFileOutput("result.json", MODE_PRIVATE)) { file.write(result.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)); } catch (Exception ignored) { }
            runOnUiThread(() -> text.setText(result.toString()));
        }, "vpn-probe").start();
    }
}
