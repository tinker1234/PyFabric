package dev.pyfabric.client.radio;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;
import java.util.function.DoubleSupplier;

import javazoom.jl.decoder.Bitstream;
import javazoom.jl.decoder.BitstreamException;
import javazoom.jl.decoder.Decoder;
import javazoom.jl.decoder.DecoderException;
import javazoom.jl.decoder.Header;
import javazoom.jl.decoder.SampleBuffer;

/**
 * Plays one internet radio stream (Icecast / Shoutcast / plain HTTP MP3) on a background thread:
 * connects, follows redirects and .pls/.m3u playlists, strips ICY metadata, decodes MP3 with JLayer,
 * applies the volume and writes PCM to a {@link Sink}. Reconnects automatically when the stream drops.
 *
 * <p>Has no Minecraft dependencies (so it can be tested on its own); {@link RadioClient} is the game glue.
 */
public final class RadioStream {
	public enum State { CONNECTING, PLAYING, RECONNECTING, STOPPED, FAILED }

	/** Where decoded audio goes. {@link JavaSoundSink} plays it; tests use a counting sink. */
	public interface Sink {
		void open(int sampleRate, int channels) throws Exception;

		/** Blocks while the device buffer is full, which paces playback in real time. */
		void write(byte[] pcm16le, int length);

		void close();
	}

	/** Called from the radio thread. */
	public interface Listener {
		void state(State state, String message);

		void title(String title);

		void station(String name);
	}

	private static final int MAX_FAILURES = 8;
	private static final long STABLE_MS = 30_000;

	private final String url;
	private final DoubleSupplier volume;
	private final Sink sink;
	private final Listener listener;
	private final Thread thread;
	private volatile boolean stopped;
	private volatile RadioHttp.Response current;
	private volatile State state = State.CONNECTING;
	private volatile String title;
	private volatile String stationName;
	private volatile long framesPlayed;

	public RadioStream(String url, DoubleSupplier volume, Sink sink, Listener listener) {
		this.url = url.trim();
		this.volume = volume;
		this.sink = sink;
		this.listener = listener;
		this.thread = new Thread(this::run, "PyFabric Radio");
		this.thread.setDaemon(true);
	}

	public RadioStream start() {
		thread.start();
		return this;
	}

	public void stop() {
		stopped = true;
		RadioHttp.Response r = current;
		if (r != null) r.close();          // unblocks a pending read
		thread.interrupt();
	}

	public void join(long millis) throws InterruptedException {
		thread.join(millis);
	}

	public String url() { return url; }

	public State state() { return state; }

	public String title() { return title; }

	public String stationName() { return stationName; }

	/** Decoded MP3 frames so far (useful for tests and diagnostics). */
	public long framesPlayed() { return framesPlayed; }

	private void setState(State s, String message) {
		state = s;
		listener.state(s, message);
	}

	private void run() {
		String scheme = url.contains("://") ? url.substring(0, url.indexOf("://")).toLowerCase(Locale.ROOT) : "";
		if (!scheme.equals("http") && !scheme.equals("https")) {
			setState(State.FAILED, "Not an http:// or https:// stream URL: " + url);
			return;
		}
		int failures = 0;
		boolean sinkOpen = false;
		int openRate = -1, openChannels = -1;
		try {
			while (!stopped) {
				long connectedAt = System.currentTimeMillis();
				try {
					setState(failures == 0 ? State.CONNECTING : State.RECONNECTING, url);
					try (RadioHttp.Response response = openAudio(URI.create(url.replace(" ", "%20")), 0)) {
						current = response;
						String name = response.header("icy-name");
						if (name != null && !name.isBlank() && !name.equals(stationName)) {
							stationName = name.trim();
							listener.station(stationName);
						}
						InputStream audio = response.body();
						String metaInt = response.header("icy-metaint");
						if (metaInt != null) {
							int interval = Integer.parseInt(metaInt.trim());
							if (interval > 0) audio = new IcyInputStream(audio, interval, t -> {
								title = t;
								listener.title(t);
							});
						}

						Bitstream bitstream = new Bitstream(new BufferedInputStream(audio, 32 * 1024));
						Decoder decoder = new Decoder();
						byte[] pcm = new byte[0];
						boolean announced = false;
						while (!stopped) {
							Header header = bitstream.readFrame();
							if (header == null) throw new IOException("The stream ended");
							SampleBuffer out;
							try {
								out = (SampleBuffer) decoder.decodeFrame(header, bitstream);
							} catch (DecoderException | ArrayIndexOutOfBoundsException e) {
								bitstream.closeFrame();        // a damaged frame: skip it
								continue;
							}
							bitstream.closeFrame();
							int rate = out.getSampleFrequency(), channels = out.getChannelCount();
							if (!sinkOpen || rate != openRate || channels != openChannels) {
								if (sinkOpen) sink.close();
								sinkOpen = false;
								try {
									sink.open(rate, channels);
								} catch (Exception e) {
									throw new UnsupportedStreamException("Can't open the audio output (" + rate + " Hz, "
											+ channels + " ch): " + (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()));
								}
								sinkOpen = true;
								openRate = rate;
								openChannels = channels;
							}
							int n = out.getBufferLength();
							if (pcm.length < n * 2) pcm = new byte[n * 2];
							toPcm(out.getBuffer(), n, gain(), pcm);
							sink.write(pcm, n * 2);
							framesPlayed++;
							if (!announced) {
								announced = true;
								setState(State.PLAYING, stationName != null ? stationName : url);
							}
							if (failures > 0 && System.currentTimeMillis() - connectedAt > STABLE_MS) failures = 0;
						}
					} finally {
						current = null;
					}
				} catch (Exception e) {
					if (stopped) break;
					if (e instanceof UnsupportedStreamException) {
						setState(State.FAILED, e.getMessage());
						return;
					}
					if (System.currentTimeMillis() - connectedAt > STABLE_MS) failures = 0;
					failures++;
					if (failures > MAX_FAILURES) {
						setState(State.FAILED, "Gave up after " + MAX_FAILURES + " attempts: " + describe(e));
						return;
					}
					setState(State.RECONNECTING, describe(e));
					long delay = Math.min(15_000L, 1000L << Math.min(failures - 1, 4));
					try {
						Thread.sleep(delay);
					} catch (InterruptedException ie) {
						if (stopped) break;
					}
				}
			}
		} finally {
			if (sinkOpen) sink.close();
			if (state != State.FAILED) setState(State.STOPPED, url);
		}
	}

	private double gain() {
		double v = volume.getAsDouble();
		return Double.isNaN(v) ? 0 : Math.max(0, Math.min(1, v));
	}

	/** 16-bit samples -> little-endian bytes, scaled by the volume. */
	static void toPcm(short[] samples, int n, double gain, byte[] out) {
		for (int i = 0; i < n; i++) {
			int s = (int) Math.round(samples[i] * gain);
			out[2 * i] = (byte) s;
			out[2 * i + 1] = (byte) (s >> 8);
		}
	}

	/** Connects, following .pls / .m3u playlists to the actual stream. */
	private RadioHttp.Response openAudio(URI uri, int depth) throws IOException {
		RadioHttp.Response r = RadioHttp.get(uri);
		String type = r.contentType();
		String path = r.uri().getPath() == null ? "" : r.uri().getPath().toLowerCase(Locale.ROOT);
		boolean playlist = type.contains("scpls") || type.contains("mpegurl") || type.contains("pls+xml")
				|| ((path.endsWith(".pls") || path.endsWith(".m3u") || path.endsWith(".m3u8"))
				&& !type.startsWith("audio/mpeg"));
		if (playlist) {
			String body;
			try (r) {
				body = RadioHttp.readSmallBody(r.body(), 256 * 1024);
			}
			if (body.contains("#EXT-X-")) {
				throw new UnsupportedStreamException("This is an HLS stream (.m3u8 segments), which isn't supported - use the station's MP3 stream URL");
			}
			if (depth >= 3) throw new UnsupportedStreamException("Playlist points to another playlist too many times");
			URI next = firstStreamUrl(body, r.uri());
			if (next == null) throw new UnsupportedStreamException("No stream URL found in the playlist");
			return openAudio(next, depth + 1);
		}
		if (!type.isEmpty() && !isMp3(type)) {
			r.close();
			throw new UnsupportedStreamException("Only MP3 streams are supported; this station sends '" + type + "'"
					+ (type.contains("aac") ? " (AAC)" : type.contains("ogg") ? " (Ogg)" : ""));
		}
		return r;
	}

	private static boolean isMp3(String type) {
		return type.equals("audio/mpeg") || type.equals("audio/mp3") || type.equals("audio/mpeg3")
				|| type.equals("audio/x-mpeg") || type.equals("audio/x-mp3") || type.equals("application/octet-stream")
				|| type.equals("audio/mpg");
	}

	/** First http(s) URL in a .pls ("File1=...") or .m3u (one URL per line) playlist. */
	static URI firstStreamUrl(String body, URI base) {
		for (String raw : body.split("\\r?\\n")) {
			String line = raw.trim();
			if (line.isEmpty() || line.startsWith("#") || line.startsWith("[")) continue;
			int eq = line.indexOf('=');
			if (line.regionMatches(true, 0, "File", 0, 4) && eq > 0) line = line.substring(eq + 1).trim();
			else if (eq > 0 && !line.contains("://")) continue;   // other .pls keys (Title1=, Length1=...)
			try {
				URI u = base.resolve(new URI(line.replace(" ", "%20")));
				String scheme = u.getScheme();
				if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) return u;
			} catch (URISyntaxException | IllegalArgumentException ignored) {
			}
		}
		return null;
	}

	private static String describe(Exception e) {
		if (e instanceof BitstreamException) return "Bad MP3 data from the stream";
		String m = e.getMessage();
		return m == null ? e.getClass().getSimpleName() : m;
	}

	/** A problem reconnecting won't fix (wrong format, HLS, empty playlist). */
	static final class UnsupportedStreamException extends IOException {
		UnsupportedStreamException(String message) {
			super(message);
		}
	}
}
