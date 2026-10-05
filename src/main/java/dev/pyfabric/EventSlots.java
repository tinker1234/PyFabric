package dev.pyfabric;

import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Function;

import net.fabricmc.fabric.api.event.Event;
import org.graalvm.polyglot.Value;

/**
 * Lets Python subscribe to ANY Fabric API {@link Event} with a plain function, in a way that survives hot reload.
 *
 * <p>Fabric events cannot be unregistered, so each Python subscription gets a permanent Java proxy ("slot")
 * whose target function can be swapped. On reload every slot is switched off; when the reloaded script
 * subscribes again with the same key, the slot is switched back on with the new function. A switched-off
 * slot behaves exactly like "no listener" by delegating to the event's own empty invoker.
 */
public final class EventSlots {
	private static final Map<String, Slot> SLOTS = new ConcurrentHashMap<>();
	private static final Map<Event<?>, Object> NEUTRAL = new ConcurrentHashMap<>();
	private static final Map<Event<?>, Class<?>> TYPES = new ConcurrentHashMap<>();

	private EventSlots() {}

	/**
	 * @param event the Fabric event, e.g. {@code ServerTickEvents.END_SERVER_TICK}
	 * @param key   stable identity of this subscription (mod id + event + function name)
	 * @param owner mod id, for error reports
	 * @param fn    Python callable; receives the listener's arguments, its return value is converted
	 */
	public static void listen(Event<?> event, String key, String owner, Value fn) {
		if (!fn.canExecute()) throw new IllegalArgumentException("Event handler must be callable, got " + fn);
		Slot existing = SLOTS.get(key);
		if (existing != null && existing.event == event) {
			existing.owner = owner;
			existing.fn = fn;
			return;
		}
		Class<?> type = listenerType(event);
		Slot slot = new Slot(key, owner, event, fn);
		Object proxy = Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type}, slot);
		SLOTS.put(key, slot);
		register(event, proxy);
	}

	/** Switch off every Python mod listener (used right before a hot reload). pyfabric's own stay on. */
	public static void deactivateAll() {
		SLOTS.values().forEach(s -> {
			if (!s.key.startsWith("pyfabric|core|")) s.fn = null;
		});
	}

	public static int activeCount() {
		return (int) SLOTS.values().stream().filter(s -> s.fn != null).count();
	}

	@SuppressWarnings("unchecked")
	private static <T> void register(Event<T> event, Object listener) {
		event.register((T) listener);
	}

	/** The listener interface of an event, recovered from Fabric's backing array. */
	public static Class<?> listenerType(Event<?> event) {
		return TYPES.computeIfAbsent(event, e -> {
			try {
				Field handlers = findField(e.getClass(), "handlers");
				Object arr = handlers.get(e);
				return arr.getClass().getComponentType();
			} catch (ReflectiveOperationException ex) {
				throw new IllegalStateException("Unsupported event implementation " + e.getClass(), ex);
			}
		});
	}

	/** Invoker built from zero listeners: returns exactly what the event returns when nobody is listening. */
	@SuppressWarnings("unchecked")
	private static Object neutral(Event<?> event) {
		return NEUTRAL.computeIfAbsent(event, e -> {
			try {
				Field f = findField(e.getClass(), "invokerFactory");
				Function<Object[], Object> factory = (Function<Object[], Object>) f.get(e);
				return factory.apply((Object[]) Array.newInstance(listenerType(e), 0));
			} catch (ReflectiveOperationException ex) {
				throw new IllegalStateException(ex);
			}
		});
	}

	private static Field findField(Class<?> c, String name) throws NoSuchFieldException {
		for (Class<?> k = c; k != null; k = k.getSuperclass()) {
			try {
				Field f = k.getDeclaredField(name);
				f.setAccessible(true);
				return f;
			} catch (NoSuchFieldException ignored) {
			}
		}
		throw new NoSuchFieldException(name);
	}

	private static final class Slot implements InvocationHandler {
		final String key;
		final Event<?> event;
		volatile String owner;
		volatile Value fn;

		Slot(String key, String owner, Event<?> event, Value fn) {
			this.key = key;
			this.owner = owner;
			this.event = event;
			this.fn = fn;
		}

		@Override
		public Object invoke(Object proxy, Method m, Object[] args) throws Throwable {
			if (m.getDeclaringClass() == Object.class) {
				return switch (m.getName()) {
					case "hashCode" -> System.identityHashCode(proxy);
					case "equals" -> proxy == args[0];
					default -> "PythonListener[" + key + "]";
				};
			}
			if (m.isDefault()) return InvocationHandler.invokeDefault(proxy, m, args);
			Value f = fn;
			if (f != null) {
				try {
					Value r = f.execute(args == null ? new Object[0] : args);
					Object c = Convert.result(r, m.getReturnType());
					if (c != Convert.NO_RESULT) return c;
				} catch (RuntimeException e) {
					Errors.report(owner, "event " + key.substring(key.indexOf('|') + 1), e);
				}
			}
			try {
				return m.invoke(neutral(event), args);
			} catch (InvocationTargetException e) {
				throw e.getCause();
			}
		}
	}
}
