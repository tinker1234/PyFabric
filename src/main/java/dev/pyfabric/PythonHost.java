package dev.pyfabric;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

import net.fabricmc.loader.api.FabricLoader;
import net.fabricmc.loader.api.ModContainer;
import org.graalvm.polyglot.Context;
import org.graalvm.polyglot.HostAccess;
import org.graalvm.polyglot.Value;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Owns the single embedded Python interpreter shared by all Python mods. */
public final class PythonHost {
	private static PythonHost instance;

	private final Path root;      // <gameDir>/pyfabric
	private final Path modsDir;   // <gameDir>/pymods
	private final Context context;
	private final Value loader;

	private PythonHost(Path gameDir) throws IOException {
		this.root = gameDir.resolve("pyfabric");
		this.modsDir = gameDir.resolve("pymods");
		Files.createDirectories(modsDir);
		Path lib = root.resolve("lib");
		extractPythonLibrary(lib);
		GeneratedPacks.init(root.resolve("generated"));

		Logger py = LoggerFactory.getLogger("python");
		// Minecraft uses `float` everywhere; let Python floats (doubles) convert to it even when not exact
		// (by default 0.6 would be rejected because it is not exactly representable as a float).
		HostAccess hostAccess = HostAccess.newBuilder(HostAccess.ALL)
				.targetTypeMapping(Double.class, Float.class, null, Double::floatValue, HostAccess.TargetMappingPrecedence.LOWEST)
				.build();
		context = Context.newBuilder("python")
				.allowAllAccess(true)
				.allowHostAccess(hostAccess)
				.hostClassLoader(PythonHost.class.getClassLoader())
				.currentWorkingDirectory(gameDir.toAbsolutePath())
				.option("engine.WarnInterpreterOnly", "false")
				.out(new LogStream(py, false))
				.err(new LogStream(py, true))
				.build();

		Value sys = context.eval("python", "import sys; sys");
		sys.getMember("path").invokeMember("insert", 0, gameDir.toAbsolutePath().toString());
		sys.getMember("path").invokeMember("insert", 0, lib.toAbsolutePath().toString());
		loader = context.eval("python", "import pyfabric._loader as _l; _l");
	}

	public static PythonHost get() {
		return instance;
	}

	static PythonHost start(Path gameDir) throws IOException {
		instance = new PythonHost(gameDir);
		return instance;
	}

	public Path modsDir() {
		return modsDir;
	}

	/** Calls a function of the Python {@code pyfabric._loader} module. */
	public Value call(String fn, Object... args) {
		return loader.getMember(fn).execute(args);
	}

	/**
	 * Copies the bundled {@code pyfabric} Python package out of the mod jar so Python can import it
	 * (and so modders can read its source). Refreshed on every launch.
	 */
	private static void extractPythonLibrary(Path target) throws IOException {
		ModContainer self = FabricLoader.getInstance().getModContainer(PyFabric.MOD_ID).orElseThrow();
		Path src = self.findPath("python").orElseThrow(() -> new IOException("Bundled python/ folder missing from jar"));
		if (Files.exists(target)) {
			try (Stream<Path> old = Files.walk(target)) {
				List<Path> paths = new ArrayList<>(old.toList());
				java.util.Collections.reverse(paths);
				for (Path p : paths) Files.deleteIfExists(p);
			}
		}
		try (Stream<Path> files = Files.walk(src)) {
			for (Path p : files.toList()) {
				Path dest = target.resolve(src.relativize(p).toString());
				if (Files.isDirectory(p)) Files.createDirectories(dest);
				else Files.copy(p, dest, StandardCopyOption.REPLACE_EXISTING);
			}
		}
	}

	/** Routes Python's stdout/stderr into the game log, one line at a time. */
	private static final class LogStream extends OutputStream {
		private final Logger log;
		private final boolean err;
		private final ByteArrayOutputStream buf = new ByteArrayOutputStream();

		LogStream(Logger log, boolean err) {
			this.log = log;
			this.err = err;
		}

		@Override
		public synchronized void write(int b) {
			if (b == '\n') flushLine();
			else buf.write(b);
		}

		@Override
		public synchronized void write(byte[] b, int off, int len) {
			for (int i = off; i < off + len; i++) write(b[i]);
		}

		private void flushLine() {
			String line = buf.toString(StandardCharsets.UTF_8);
			buf.reset();
			if (line.endsWith("\r")) line = line.substring(0, line.length() - 1);
			if (err) log.warn(line);
			else log.info(line);
		}

		@Override
		public synchronized void flush() {
			if (buf.size() > 0) flushLine();
		}
	}
}
