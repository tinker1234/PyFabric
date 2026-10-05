package dev.pyfabric;

import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import org.graalvm.polyglot.Value;

/** Named Python callbacks attached to a Java object (a PyItem or PyBlock). Swappable for hot reload. */
public final class Hooks {
	private static final Set<Hooks> ALL = ConcurrentHashMap.newKeySet();

	private final String what;
	private final Map<String, Value> fns = new ConcurrentHashMap<>();
	private volatile String owner = "?";

	public Hooks(String what) {
		this.what = what;
		ALL.add(this);
	}

	public void set(String name, Value fn, String owner) {
		if (fn == null || fn.isNull()) {
			fns.remove(name);
			return;
		}
		if (!fn.canExecute()) throw new IllegalArgumentException("Hook '" + name + "' must be callable");
		this.owner = owner;
		fns.put(name, fn);
	}

	public boolean has(String name) {
		return fns.containsKey(name);
	}

	public void clear() {
		fns.clear();
	}

	public static void clearAll() {
		ALL.forEach(Hooks::clear);
	}

	/** Calls the hook, returning {@link Convert#NO_RESULT} if it is missing, returned None or failed. */
	public Object call(String name, Class<?> returnType, Object... args) {
		Value fn = fns.get(name);
		if (fn == null) return Convert.NO_RESULT;
		try {
			return Convert.result(fn.execute(args), returnType);
		} catch (RuntimeException e) {
			Errors.report(owner, what + " hook '" + name + "'", e);
			return Convert.NO_RESULT;
		}
	}

	/** Calls the hook and returns the raw Python value (or null). */
	public Value callRaw(String name, Object... args) {
		Value fn = fns.get(name);
		if (fn == null) return null;
		try {
			return fn.execute(args);
		} catch (RuntimeException e) {
			Errors.report(owner, what + " hook '" + name + "'", e);
			return null;
		}
	}
}
