package dev.pyfabric.client.radio;

import static net.fabricmc.fabric.api.client.command.v2.ClientCommands.argument;
import static net.fabricmc.fabric.api.client.command.v2.ClientCommands.literal;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.fabric.api.client.command.v2.FabricClientCommandSource;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;

/**
 * Client-side command (works on any server, even vanilla ones):
 * <pre>
 * /radio                    status
 * /radio play &lt;url&gt;        play an Icecast / Shoutcast / MP3 stream (or a .pls / .m3u link)
 * /radio play               play the last station again
 * /radio stop
 * /radio volume &lt;0-100&gt;
 * /radio titles on|off      "Now playing" above the hotbar
 * </pre>
 */
public final class RadioCommand {
	private RadioCommand() {}

	public static void register(CommandDispatcher<FabricClientCommandSource> dispatcher) {
		dispatcher.register(literal("radio")
				.executes(ctx -> status(ctx.getSource()))
				.then(literal("play")
						.executes(ctx -> {
							String last = RadioClient.getLastUrl();
							if (last == null || last.isBlank()) {
								ctx.getSource().sendError(Component.literal("Usage: /radio play <stream url>"));
								return 0;
							}
							return play(ctx.getSource(), last);
						})
						.then(argument("url", StringArgumentType.greedyString())
								.executes(ctx -> play(ctx.getSource(), StringArgumentType.getString(ctx, "url")))))
				.then(literal("stop").executes(ctx -> {
					boolean was = RadioClient.isPlaying();
					RadioClient.stop();
					ctx.getSource().sendFeedback(Component.literal(was ? "Radio stopped" : "The radio isn't playing"));
					return 1;
				}))
				.then(literal("volume")
						.executes(ctx -> {
							ctx.getSource().sendFeedback(Component.literal("Radio volume: " + Math.round(RadioClient.getVolume() * 100) + "%"
									+ " (also follows your Music volume slider)"));
							return 1;
						})
						.then(argument("percent", IntegerArgumentType.integer(0, 100)).executes(ctx -> {
							int p = IntegerArgumentType.getInteger(ctx, "percent");
							RadioClient.setVolume(p / 100.0);
							ctx.getSource().sendFeedback(Component.literal("Radio volume set to " + p + "%"));
							return 1;
						})))
				.then(literal("titles")
						.then(literal("on").executes(ctx -> {
							RadioClient.setAnnounceTitles(true);
							ctx.getSource().sendFeedback(Component.literal("Song titles will be shown"));
							return 1;
						}))
						.then(literal("off").executes(ctx -> {
							RadioClient.setAnnounceTitles(false);
							ctx.getSource().sendFeedback(Component.literal("Song titles hidden"));
							return 1;
						}))));
	}

	private static int play(FabricClientCommandSource source, String url) {
		RadioClient.play(url);
		source.sendFeedback(Component.literal("Radio: connecting to " + url.trim() + " ...").withStyle(ChatFormatting.GRAY));
		return 1;
	}

	private static int status(FabricClientCommandSource source) {
		if (!RadioClient.isPlaying()) {
			String last = RadioClient.getLastUrl();
			source.sendFeedback(Component.literal("Radio is off. /radio play <url>"
					+ (last == null || last.isBlank() ? "" : " (or /radio play to resume " + last + ")")));
			return 1;
		}
		String station = RadioClient.getStation();
		String title = RadioClient.getTitle();
		source.sendFeedback(Component.literal("Radio " + RadioClient.getState().toLowerCase() + ": "
				+ (station != null ? station : RadioClient.getUrl())).withStyle(ChatFormatting.GREEN));
		if (title != null) source.sendFeedback(Component.literal("♪ " + title).withStyle(ChatFormatting.AQUA));
		source.sendFeedback(Component.literal("Volume " + Math.round(RadioClient.getVolume() * 100) + "%").withStyle(ChatFormatting.GRAY));
		return 1;
	}
}
