package dev.pyfabric;

import net.minecraft.world.InteractionResult;
import org.graalvm.polyglot.Value;

/** Converts Python return values into what the Java caller expects. */
public final class Convert {
	/** Marker: "Python had no opinion", fall back to default / neutral behaviour. */
	public static final Object NO_RESULT = new Object();

	private Convert() {}

	public static Object result(Value r, Class<?> type) {
		if (type == void.class || type == Void.class) return null;
		if (r == null || r.isNull()) return NO_RESULT;
		try {
			if (type == boolean.class || type == Boolean.class) {
				return r.isBoolean() ? r.asBoolean() : NO_RESULT;
			}
			if (InteractionResult.class.isAssignableFrom(type)) {
				if (r.isBoolean()) return r.asBoolean() ? InteractionResult.SUCCESS : InteractionResult.FAIL;
				if (r.isHostObject() && r.asHostObject() instanceof InteractionResult ir) return ir;
				return NO_RESULT;
			}
			if (type == int.class || type == Integer.class) return r.fitsInInt() ? r.asInt() : NO_RESULT;
			if (type == float.class || type == Float.class) return r.fitsInFloat() ? r.asFloat() : (r.fitsInDouble() ? (float) r.asDouble() : NO_RESULT);
			if (type == double.class || type == Double.class) return r.fitsInDouble() ? r.asDouble() : NO_RESULT;
			if (type == long.class || type == Long.class) return r.fitsInLong() ? r.asLong() : NO_RESULT;
			if (type == String.class) return r.isString() ? r.asString() : r.toString();
			if (r.isHostObject()) {
				Object o = r.asHostObject();
				return type.isInstance(o) ? o : NO_RESULT;
			}
			return r.as(type);
		} catch (RuntimeException e) {
			return NO_RESULT;
		}
	}
}
