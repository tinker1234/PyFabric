package dev.pyfabric.client.radio;

import java.io.IOException;
import java.io.Reader;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Properties;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;

import dev.pyfabric.PyFabric;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.ChatFormatting;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.network.chat.Component;
import net.minecraft.sounds.SoundSource;

/**
 * The in-game internet radio: one stream at a time, played on the client.
 * Volume = radio volume x Minecraft's Master x Music sliders. Used by {@code /radio} and {@code pyfabric.radio}.
 */
public final class RadioClient {
	private static final Path SETTINGS = FabricLoader.getInstance().getConfigDir().resolve("pyfabric-radio.properties");
	private static final List<Consumer<String>> TITLE_LISTENERS = new CopyOnWriteArrayList<>();
	private static final List<Consumer<String>> STATE_LISTENERS = new CopyOnWriteArrayList<>();

	private static volatile RadioStream stream;
	private static volatile double volume = 1.0;
	private static volatile boolean announceTitles = true;
	private static String lastUrl = "";

	static {
		loadSettings();
	}

	private RadioClient() {}

	// ---- control ------------------------------------------------------------------------------------------

	public static synchronized void play(String url) {
		stopQuietly();
		lastUrl = url.trim();
		saveSettings();
		stream = new RadioStream(lastUrl, RadioClient::effectiveVolume, sink(), new GameListener()).start();
	}

	public static synchronized void stop() {
		stopQuietly();
	}

	private static void stopQuietly() {
		RadioStream s = stream;
		stream = null;
		if (s != null) s.stop();
	}

	/** Radio volume 0..1 (multiplied by Minecraft's Master and Music sliders). */
	public static void setVolume(double v) {
		volume = Math.max(0, Math.min(1, v));
		saveSettings();
	}

	public static double getVolume() {
		return volume;
	}

	/** Show "Now playing" above the hotbar when the song changes (default on). */
	public static void setAnnounceTitles(boolean on) {
		announceTitles = on;
		saveSettings();
	}

	public static boolean isPlaying() {
		RadioStream s = stream;
		return s != null && s.state() != RadioStream.State.STOPPED && s.state() != RadioStream.State.FAILED;
	}

	/** CONNECTING, PLAYING, RECONNECTING, STOPPED or FAILED. */
	public static String getState() {
		RadioStream s = stream;
		return s == null ? "STOPPED" : s.state().name();
	}

	public static String getTitle() {
		RadioStream s = stream;
		return s == null ? null : s.title();
	}

	public static String getStation() {
		RadioStream s = stream;
		return s == null ? null : s.stationName();
	}

	public static String getUrl() {
		RadioStream s = stream;
		return s != null ? s.url() : lastUrl;
	}

	public static String getLastUrl() {
		return lastUrl;
	}

	/** Called on the client thread with the new song title. */
	public static void onTitle(Consumer<String> listener) {
		TITLE_LISTENERS.add(listener);
	}

	/** Called on the client thread with "STATE: message" whenever the radio's state changes. */
	public static void onState(Consumer<String> listener) {
		STATE_LISTENERS.add(listener);
	}

	public static void clearListeners() {
		TITLE_LISTENERS.clear();
		STATE_LISTENERS.clear();
	}

	// ---- internals ----------------------------------------------------------------------------------------

	private static double effectiveVolume() {
		Minecraft mc = Minecraft.getInstance();
		double game = mc == null || mc.options == null ? 1.0 : mc.options.getFinalSoundSourceVolume(SoundSource.MUSIC);
		return volume * game;
	}

	private static RadioStream.Sink sink() {
		// For headless testing: -Dpyfabric.radio.sink=null decodes but discards the audio.
		if ("null".equals(System.getProperty("pyfabric.radio.sink"))) {
			return new RadioStream.Sink() {
				public void open(int rate, int channels) {}

				public void write(byte[] pcm, int len) {
					try {
						Thread.sleep(Math.max(1, len * 1000L / (44100 * 4)));
					} catch (InterruptedException ignored) {
					}
				}

				public void close() {}
			};
		}
		return new JavaSoundSink();
	}

	private static void onClientThread(Runnable r) {
		Minecraft mc = Minecraft.getInstance();
		if (mc != null) mc.execute(r);
	}

	private static void tellPlayer(Component message, boolean actionbar) {
		LocalPlayer player = Minecraft.getInstance().player;
		if (player == null) return;
		if (actionbar) player.sendOverlayMessage(message);
		else player.sendSystemMessage(message);
	}

	private static final class GameListener implements RadioStream.Listener {
		private RadioStream.State last;

		@Override
		public void state(RadioStream.State state, String message) {
			RadioStream.State previous = last;
			last = state;
			PyFabric.LOGGER.info("[radio] {}: {}", state, message);
			onClientThread(() -> {
				switch (state) {
					case PLAYING -> {
						if (previous != RadioStream.State.PLAYING)
							tellPlayer(Component.literal("Radio: playing " + message).withStyle(ChatFormatting.GREEN), false);
					}
					case RECONNECTING -> {
						if (previous == RadioStream.State.PLAYING)
							tellPlayer(Component.literal("Radio: connection lost (" + message + "), reconnecting...").withStyle(ChatFormatting.YELLOW), false);
					}
					case FAILED -> tellPlayer(Component.literal("Radio: " + message).withStyle(ChatFormatting.RED), false);
					default -> {
					}
				}
				for (Consumer<String> l : STATE_LISTENERS) safe(l, state.name() + ": " + message);
			});
		}

		@Override
		public void title(String title) {
			PyFabric.LOGGER.info("[radio] Now playing: {}", title);
			onClientThread(() -> {
				if (announceTitles) {
					tellPlayer(Component.literal("♪ ").append(Component.literal(title)).withStyle(ChatFormatting.AQUA), true);
				}
				for (Consumer<String> l : TITLE_LISTENERS) safe(l, title);
			});
		}

		@Override
		public void station(String name) {
		}

		private static void safe(Consumer<String> l, String value) {
			try {
				l.accept(value);
			} catch (RuntimeException e) {
				PyFabric.LOGGER.error("Radio listener failed", e);
			}
		}
	}

	private static void loadSettings() {
		if (!Files.exists(SETTINGS)) return;
		Properties p = new Properties();
		try (Reader r = Files.newBufferedReader(SETTINGS)) {
			p.load(r);
			volume = Math.max(0, Math.min(1, Double.parseDouble(p.getProperty("volume", "1.0"))));
			announceTitles = Boolean.parseBoolean(p.getProperty("announce_titles", "true"));
			lastUrl = p.getProperty("last_url", "");
		} catch (IOException | NumberFormatException e) {
			PyFabric.LOGGER.warn("Could not read {}: {}", SETTINGS, e.toString());
		}
	}

	private static synchronized void saveSettings() {
		Properties p = new Properties();
		p.setProperty("volume", Double.toString(volume));
		p.setProperty("announce_titles", Boolean.toString(announceTitles));
		p.setProperty("last_url", lastUrl == null ? "" : lastUrl);
		try (Writer w = Files.newBufferedWriter(SETTINGS)) {
			p.store(w, "PyFabric radio");
		} catch (IOException e) {
			PyFabric.LOGGER.warn("Could not save {}: {}", SETTINGS, e.toString());
		}
	}
}
