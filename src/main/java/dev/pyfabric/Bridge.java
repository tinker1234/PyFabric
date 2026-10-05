package dev.pyfabric;

import java.lang.reflect.Field;
import java.nio.file.Path;
import java.util.Map;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.tree.CommandNode;
import net.fabricmc.api.EnvType;
import net.fabricmc.fabric.api.event.Event;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockBehaviour;
import org.graalvm.polyglot.PolyglotException;
import org.graalvm.polyglot.Value;

/**
 * The small Java surface the Python {@code pyfabric} package talks to.
 * Python mods normally use the {@code pyfabric} package instead of calling this directly.
 */
public final class Bridge {
	private static volatile MinecraftServer server;

	private Bridge() {}

	// ---- environment ------------------------------------------------------------------------------------------

	public static MinecraftServer server() {
		return server;
	}

	static void setServer(MinecraftServer s) {
		server = s;
	}

	public static boolean isClient() {
		return FabricLoader.getInstance().getEnvironmentType() == EnvType.CLIENT;
	}

	public static boolean isDevelopment() {
		return FabricLoader.getInstance().isDevelopmentEnvironment();
	}

	public static String gameDir() {
		return FabricLoader.getInstance().getGameDir().toAbsolutePath().normalize().toString();
	}

	public static String configDir() {
		return FabricLoader.getInstance().getConfigDir().toAbsolutePath().normalize().toString();
	}

	public static boolean isModLoaded(String id) {
		return FabricLoader.getInstance().isModLoaded(id);
	}

	public static String generatedDir(String kind) {
		Path p = "resources".equals(kind) ? GeneratedPacks.resourcesDir() : GeneratedPacks.dataDir();
		return p.toString();
	}

	// ---- events ---------------------------------------------------------------------------------------------

	public static void listen(Event<?> event, String key, String owner, Value fn) {
		EventSlots.listen(event, key, owner, fn);
	}

	public static String listenerType(Event<?> event) {
		return EventSlots.listenerType(event).getName();
	}

	// ---- registries -------------------------------------------------------------------------------------------

	public static boolean exists(String registry, String id) {
		Identifier rid = Identifier.parse(id);
		return switch (registry) {
			case "item" -> BuiltInRegistries.ITEM.containsKey(rid);
			case "block" -> BuiltInRegistries.BLOCK.containsKey(rid);
			default -> throw new IllegalArgumentException(registry);
		};
	}

	public static PyItem registerItem(String id, Item.Properties props) {
		Identifier rid = Identifier.parse(id);
		if (BuiltInRegistries.ITEM.containsKey(rid)) {
			Item existing = BuiltInRegistries.ITEM.getValue(rid);
			if (existing instanceof PyItem pi) return pi; // hot reload: reuse, Python re-attaches hooks
			throw new IllegalArgumentException("Item " + id + " already exists and was not made by PyFabric");
		}
		ResourceKey<Item> key = ResourceKey.create(Registries.ITEM, rid);
		try {
			return Registry.register(BuiltInRegistries.ITEM, key, new PyItem(props.setId(key), id));
		} catch (IllegalStateException e) {
			throw frozen("item", id, e);
		}
	}

	public static PyBlock registerBlock(String id, BlockBehaviour.Properties props) {
		Identifier rid = Identifier.parse(id);
		if (BuiltInRegistries.BLOCK.containsKey(rid)) {
			Block existing = BuiltInRegistries.BLOCK.getValue(rid);
			if (existing instanceof PyBlock pb) return pb;
			throw new IllegalArgumentException("Block " + id + " already exists and was not made by PyFabric");
		}
		ResourceKey<Block> key = ResourceKey.create(Registries.BLOCK, rid);
		try {
			return Registry.register(BuiltInRegistries.BLOCK, key, new PyBlock(props.setId(key), id));
		} catch (IllegalStateException e) {
			throw frozen("block", id, e);
		}
	}

	public static Item registerBlockItem(String id, Block block, Item.Properties props) {
		Identifier rid = Identifier.parse(id);
		if (BuiltInRegistries.ITEM.containsKey(rid)) return BuiltInRegistries.ITEM.getValue(rid);
		ResourceKey<Item> key = ResourceKey.create(Registries.ITEM, rid);
		try {
			return Registry.register(BuiltInRegistries.ITEM, key, new BlockItem(block, props.setId(key).useBlockDescriptionPrefix()));
		} catch (IllegalStateException e) {
			throw frozen("item", id, e);
		}
	}

	private static RuntimeException frozen(String what, String id, Exception cause) {
		return new IllegalStateException("Cannot add new " + what + " '" + id + "' after startup (registries are frozen). "
				+ "Restart the game to add new " + what + "s; hooks on existing ones are hot-reloaded.", cause);
	}

	/** Light level as a fast Java function (avoids calling Python for every block state). */
	public static java.util.function.ToIntFunction<net.minecraft.world.level.block.state.BlockState> constantLight(int level) {
		return s -> level;
	}

	// ---- commands ---------------------------------------------------------------------------------------------

	/** Wraps a Python function as a Brigadier command with proper error handling. */
	public static Command<CommandSourceStack> command(String owner, String name, Value fn) {
		return ctx -> {
			try {
				Value r = fn.execute(ctx);
				return r != null && r.fitsInInt() ? r.asInt() : 1;
			} catch (PolyglotException e) {
				if (e.isHostException() && e.asHostException() instanceof CommandSyntaxException cse) throw cse;
				Errors.report(owner, "command /" + name, e);
				ctx.getSource().sendFailure(Component.literal("Error in /" + name + ": " + Errors.summary(e)).withStyle(ChatFormatting.RED));
				return 0;
			}
		};
	}

	/** Removes a top-level command (used when a Python mod is reloaded or deletes a command). */
	@SuppressWarnings("unchecked")
	public static boolean removeCommand(CommandDispatcher<CommandSourceStack> dispatcher, String name) {
		CommandNode<CommandSourceStack> root = dispatcher.getRoot();
		boolean removed = false;
		for (String field : new String[]{"children", "literals", "arguments"}) {
			try {
				Field f = CommandNode.class.getDeclaredField(field);
				f.setAccessible(true);
				removed |= ((Map<String, ?>) f.get(root)).remove(name) != null;
			} catch (ReflectiveOperationException ignored) {
			}
		}
		return removed;
	}

	/** Re-sends the command tree so players see added/removed commands after a reload. */
	public static void resendCommands() {
		MinecraftServer s = server;
		if (s == null) return;
		s.getPlayerList().getPlayers().forEach(p -> s.getCommands().sendCommands(p));
	}

	// ---- data -------------------------------------------------------------------------------------------------

	/** Like /reload: re-reads data packs (recipes, loot tables, tags...) including PyFabric's generated pack. */
	public static void reloadData() {
		MinecraftServer s = server;
		if (s == null) return;
		s.execute(() -> s.reloadResources(s.getPackRepository().getSelectedIds()).exceptionally(t -> {
			PyFabric.LOGGER.error("Data reload failed", t);
			return null;
		}));
	}

	public static void reportError(String owner, String where, String summary, String details) {
		Errors.reportText(owner, where, summary, details);
	}

	public static void log(String owner, String level, String message) {
		org.slf4j.Logger l = org.slf4j.LoggerFactory.getLogger(owner);
		switch (level) {
			case "debug" -> l.debug(message);
			case "warn" -> l.warn(message);
			case "error" -> l.error(message);
			default -> l.info(message);
		}
	}
}
