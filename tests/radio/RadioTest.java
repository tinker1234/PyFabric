import dev.pyfabric.client.radio.RadioStream;
import java.util.*;
import java.util.concurrent.atomic.*;

public class RadioTest {
    static int pass = 0, fail = 0;
    static void check(String name, boolean ok, Object detail) {
        System.out.println((ok ? "PASS " : "FAIL ") + name + "  [" + detail + "]");
        if (ok) pass++; else fail++;
    }
    static class CountingSink implements RadioStream.Sink {
        final AtomicLong bytes = new AtomicLong(); volatile int rate, channels; volatile int maxAbs; volatile int opens;
        public void open(int r, int c) { rate = r; channels = c; opens++; }
        public void write(byte[] b, int len) {
            bytes.addAndGet(len);
            for (int i = 0; i + 1 < len; i += 2) { int s = (short) ((b[i] & 0xff) | (b[i + 1] << 8)); maxAbs = Math.max(maxAbs, Math.abs(s)); }
            try { Thread.sleep(2); } catch (InterruptedException e) {}
        }
        public void close() {}
    }
    static class Rec implements RadioStream.Listener {
        final List<String> titles = Collections.synchronizedList(new ArrayList<>());
        final List<String> states = Collections.synchronizedList(new ArrayList<>());
        volatile String station;
        public void state(RadioStream.State s, String m) { states.add(s + ": " + m); }
        public void title(String t) { titles.add(t); }
        public void station(String n) { station = n; }
    }
    static Object[] run(String url, double vol, long ms) throws Exception {
        CountingSink sink = new CountingSink(); Rec rec = new Rec();
        RadioStream r = new RadioStream(url, () -> vol, sink, rec).start();
        Thread.sleep(ms);
        Object[] res = {r, sink, rec};
        r.stop(); r.join(3000);
        return res;
    }
    public static void main(String[] a) throws Exception {
        String base = "http://127.0.0.1:" + a[0];
        Object[] o = run(base + "/icecast", 1.0, 3000);
        RadioStream r = (RadioStream) o[0]; CountingSink s = (CountingSink) o[1]; Rec rec = (Rec) o[2];
        check("icecast: decodes MP3 frames", r.framesPlayed() > 50, r.framesPlayed() + " frames");
        check("icecast: 44100 Hz stereo", s.rate == 44100 && s.channels == 2, s.rate + "/" + s.channels);
        check("icecast: real audio (tone peaks at -21.5 dBFS = 2755)", s.maxAbs > 2600 && s.maxAbs < 2900, "peak " + s.maxAbs);
        check("icecast: station name", "Fake Icecast Radio".equals(rec.station), rec.station);
        check("icecast: titles parsed (incl. UTF-8 + apostrophes)", rec.titles.contains("Café Tacvba - Ojalá que llueva café") && rec.titles.contains("It's a 'quoted' title"), rec.titles);
        check("icecast: PLAYING then STOPPED", rec.states.stream().anyMatch(x -> x.startsWith("PLAYING")) && rec.states.get(rec.states.size() - 1).startsWith("STOPPED"), rec.states);

        o = run(base + "/icecast", 0.25, 2000); s = (CountingSink) o[1];
        check("volume 0.25 scales samples to a quarter", s.maxAbs > 640 && s.maxAbs < 740, "peak " + s.maxAbs);

        o = run(base + "/shoutcast", 1.0, 2500); r = (RadioStream) o[0]; rec = (Rec) o[2];
        check("shoutcast v1 'ICY 200 OK' plays", r.framesPlayed() > 50, r.framesPlayed());
        check("shoutcast: station + title", "Fake Shoutcast FM".equals(rec.station) && !rec.titles.isEmpty(), rec.station + " " + rec.titles);

        o = run(base + "/redirect", 1.0, 2500); r = (RadioStream) o[0]; rec = (Rec) o[2];
        check("302 redirect -> .pls playlist -> stream", r.framesPlayed() > 50 && "Fake Shoutcast FM".equals(rec.station), r.framesPlayed() + " " + rec.station);

        o = run(base + "/icecast?drop=60000", 1.0, 6000); r = (RadioStream) o[0]; rec = (Rec) o[2];
        long reconnects = rec.states.stream().filter(x -> x.startsWith("RECONNECTING")).count();
        check("reconnects after the connection drops", reconnects >= 1 && r.framesPlayed() > 200, reconnects + " reconnects, " + r.framesPlayed() + " frames, " + rec.states);

        o = run(base + "/aac", 1.0, 1500); rec = (Rec) o[2];
        check("AAC rejected with a clear message", rec.states.stream().anyMatch(x -> x.startsWith("FAILED") && x.contains("AAC")), rec.states);
        o = run(base + "/hls.m3u8", 1.0, 1500); rec = (Rec) o[2];
        check("HLS rejected with a clear message", rec.states.stream().anyMatch(x -> x.startsWith("FAILED") && x.contains("HLS")), rec.states);
        o = run(base + "/notfound", 1.0, 2500); rec = (Rec) o[2];
        check("404 -> retries (RECONNECTING)", rec.states.stream().anyMatch(x -> x.startsWith("RECONNECTING") && x.contains("404")), rec.states);
        o = run("http://127.0.0.1:1/nothing", 1.0, 1500); rec = (Rec) o[2];
        check("connection refused -> retries", rec.states.stream().anyMatch(x -> x.startsWith("RECONNECTING")), rec.states);
        o = run("ftp://example.com/x", 1.0, 1500); rec = (Rec) o[2];
        check("bad scheme -> fails immediately", rec.states.size() == 1 && rec.states.get(0).startsWith("FAILED: Not an http"), rec.states);

        System.out.println("=== " + pass + "/" + (pass + fail) + " passed ===");
        System.exit(fail == 0 ? 0 : 1);
    }
}
