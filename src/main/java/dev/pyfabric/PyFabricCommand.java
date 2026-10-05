package dev.pyfabric;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import org.graalvm.polyglot.Value;

/**
 * {@code /pyfabric list}            - show loaded Python mods
 * {@code /pyfabric reload}          - hot-reload all Python mods (code, events, commands, recipes...)
 * {@code /pyfabric run <python>}    - run a line of Python in-game (owners only)
 */
final class PyFabricCommand {
	private PyFabricCommand() {}

	static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("pyfabric")
				.requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
				.then(Commands.literal("list").executes(ctx -> {
					Value lines = PythonHost.get().call("status_lines");
					for (long i = 0; i < lines.getArraySize(); i++) {
						String line = lines.getArrayElement(i).asString();
						ctx.getSource().sendSystemMessage(Component.literal(line)
								.withStyle(line.contains("FAILED") ? ChatFormatting.RED : ChatFormatting.WHITE));
					}
					return 1;
				}))
				.then(Commands.literal("reload").executes(ctx -> {
					long t = System.currentTimeMillis();
					Value summary = PythonHost.get().call("reload");
					ctx.getSource().sendSuccess(() -> Component.literal("[PyFabric] " + summary.asString()
							+ " (" + (System.currentTimeMillis() - t) + " ms)").withStyle(ChatFormatting.GREEN), true);
					return 1;
				}))
				.then(Commands.literal("run")
						.requires(Commands.hasPermission(Commands.LEVEL_OWNERS))
						.then(Commands.argument("code", StringArgumentType.greedyString()).executes(ctx -> {
							Value out = PythonHost.get().call("run_snippet", StringArgumentType.getString(ctx, "code"), ctx.getSource());
							String text = out.asString();
							if (!text.isEmpty()) {
								boolean error = text.startsWith("Traceback") || text.contains("Error:");
								ctx.getSource().sendSystemMessage(Component.literal(text)
										.withStyle(error ? ChatFormatting.RED : ChatFormatting.AQUA));
							}
							return 1;
						}))));
	}
}
