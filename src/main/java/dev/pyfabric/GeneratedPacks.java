package dev.pyfabric;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

import net.minecraft.SharedConstants;
import net.minecraft.network.chat.Component;
import net.minecraft.server.packs.PackLocationInfo;
import net.minecraft.server.packs.PackSelectionConfig;
import net.minecraft.server.packs.PackType;
import net.minecraft.server.packs.PathPackResources;
import net.minecraft.server.packs.repository.KnownPack;
import net.minecraft.server.packs.repository.Pack;
import net.minecraft.server.packs.repository.PackSource;
import net.minecraft.server.packs.repository.RepositorySource;

/**
 * Two always-on packs that hold everything Python mods ship or generate:
 * <ul>
 *   <li>{@code pyfabric/generated/resources} - assets (textures, models, lang) - a client resource pack</li>
 *   <li>{@code pyfabric/generated/data} - data (recipes, loot tables, tags) - a server data pack</li>
 * </ul>
 * The Python side rewrites their contents on every (re)load.
 */
public final class GeneratedPacks {
	private static Path resources;
	private static Path data;

	private GeneratedPacks() {}

	static void init(Path root) throws IOException {
		resources = root.resolve("resources");
		data = root.resolve("data");
		writeMeta(resources, PackType.CLIENT_RESOURCES);
		writeMeta(data, PackType.SERVER_DATA);
	}

	public static Path resourcesDir() {
		return resources;
	}

	public static Path dataDir() {
		return data;
	}

	private static void writeMeta(Path dir, PackType type) throws IOException {
		Files.createDirectories(dir);
		int format = SharedConstants.getCurrentVersion().packVersion(type).major();
		Files.writeString(dir.resolve("pack.mcmeta"), """
				{
				  "pack": {
				    "description": "Content of PyFabric Python mods",
				    "min_format": %d,
				    "max_format": %d
				  }
				}
				""".formatted(format, format));
	}

	private static String contentHash(Path dir) {
		try (java.util.stream.Stream<Path> files = Files.walk(dir)) {
			java.security.MessageDigest md = java.security.MessageDigest.getInstance("SHA-1");
			for (Path p : files.filter(Files::isRegularFile).sorted().toList()) {
				md.update(dir.relativize(p).toString().replace('\\', '/').getBytes(java.nio.charset.StandardCharsets.UTF_8));
				md.update(Files.readAllBytes(p));
			}
			return java.util.HexFormat.of().formatHex(md.digest()).substring(0, 16);
		} catch (Exception e) {
			return "unknown";
		}
	}

	public static RepositorySource source(PackType type) {
		return consumer -> {
			Path dir = type == PackType.CLIENT_RESOURCES ? resources : data;
			if (dir == null) return;
			// A KnownPack id marks the content as "stable" (worldgen from unknown packs makes Minecraft warn about
			// experimental settings). The version is a content hash, so a client with different Python mods is
			// never assumed to already have this data.
			Optional<KnownPack> known = type == PackType.SERVER_DATA
					? Optional.of(new KnownPack(PyFabric.MOD_ID, "python_mods", contentHash(dir)))
					: Optional.empty();
			PackLocationInfo info = new PackLocationInfo("pyfabric:" + (type == PackType.CLIENT_RESOURCES ? "resources" : "data"),
					Component.literal("PyFabric Python mods"), PackSource.BUILT_IN, known);
			Pack pack = Pack.readMetaAndCreate(info, new PathPackResources.PathResourcesSupplier(dir), type,
					new PackSelectionConfig(true, Pack.Position.TOP, false));
			if (pack != null) consumer.accept(pack);
			else PyFabric.LOGGER.error("Could not create PyFabric {} pack from {}", type, dir);
		};
	}
}
