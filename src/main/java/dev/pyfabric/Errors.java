package dev.pyfabric;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import org.graalvm.polyglot.PolyglotException;
import org.graalvm.polyglot.SourceSection;

/**
 * Reports errors thrown by Python code without ever crashing the game.
 * Repeated errors from the same place (e.g. a broken tick handler) are rate limited.
 */
public final class Errors {
	private static final long WINDOW_MS = 10_000;
	private static final Map<String, long[]> LAST = new ConcurrentHashMap<>(); // key -> {lastLoggedAt, suppressed}

	private Errors() {}

	public static void report(String owner, String where, Throwable t) {
		reportText(owner, where, summary(t), traceback(t));
	}

	/** Reports an error already formatted by Python (which has better tracebacks than Java can produce). */
	public static void reportText(String owner, String where, String summary, String details) {
		String key = owner + "|" + where;
		long now = System.currentTimeMillis();
		long[] state = LAST.computeIfAbsent(key, k -> new long[]{0, 0});
		synchronized (state) {
			if (now - state[0] < WINDOW_MS) {
				state[1]++;
				return;
			}
			long suppressed = state[1];
			state[0] = now;
			state[1] = 0;
			PyFabric.LOGGER.error("[{}] Python error in {}{}\n{}", owner, where,
					suppressed > 0 ? " (" + suppressed + " similar errors suppressed)" : "", details);
			notifyOps("[PyFabric] " + owner + ": " + summary + " (in " + where + ", see log)");
		}
	}

	/** One-line description, e.g. "NameError: name 'foo' is not defined". */
	public static String summary(Throwable t) {
		String m = t.getMessage();
		if (m == null) m = t.getClass().getSimpleName();
		int nl = m.indexOf('\n');
		return nl > 0 ? m.substring(0, nl) : m;
	}

	/** Python-style traceback for guest exceptions, normal stack trace otherwise. */
	public static String traceback(Throwable t) {
		if (t instanceof PolyglotException pe && pe.isGuestException()) {
			StringBuilder sb = new StringBuilder("Traceback (most recent call last):\n");
			java.util.List<String> frames = new java.util.ArrayList<>();
			for (PolyglotException.StackFrame f : pe.getPolyglotStackTrace()) {
				if (!f.isGuestFrame()) continue;
				SourceSection s = f.getSourceLocation();
				if (s == null || s.getSource() == null) continue;
				String file = s.getSource().getPath() != null ? s.getSource().getPath() : s.getSource().getName();
				if (file != null && file.contains("<frozen")) continue;
				String line = s.isAvailable() && s.hasLines() ? s.getCharacters().toString().strip() : "";
				int nl = line.indexOf('\n');
				if (nl >= 0) line = line.substring(0, nl).strip();
				frames.add("  File \"" + file + "\", line " + s.getStartLine() + ", in " + f.getRootName()
						+ (line.isEmpty() || line.length() > 160 ? "" : "\n    " + line));
			}
			java.util.Collections.reverse(frames);
			frames.forEach(fr -> sb.append(fr).append('\n'));
			sb.append(pe.getMessage());
			if (pe.isHostException()) {
				// A Java exception: show where in Java it came from too.
				Throwable host = pe.asHostException();
				sb.append("\nJava stack (most recent call first):");
				int n = 0;
				for (StackTraceElement el : host.getStackTrace()) {
					if (el.getClassName().startsWith("com.oracle.truffle") || n++ >= 8) break;
					sb.append("\n    at ").append(el);
				}
			}
			return sb.toString();
		}
		java.io.StringWriter sw = new java.io.StringWriter();
		t.printStackTrace(new java.io.PrintWriter(sw));
		return sw.toString();
	}

	private static void notifyOps(String text) {
		MinecraftServer server = Bridge.server();
		if (server == null) return;
		server.execute(() -> {
			Component msg = Component.literal(text).withStyle(ChatFormatting.RED);
			for (ServerPlayer p : server.getPlayerList().getPlayers()) {
				if (server.getPlayerList().isOp(p.nameAndId())) p.sendSystemMessage(msg);
			}
		});
	}
}
