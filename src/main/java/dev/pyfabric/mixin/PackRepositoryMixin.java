package dev.pyfabric.mixin;

import java.util.LinkedHashSet;
import java.util.Set;

import dev.pyfabric.GeneratedPacks;
import net.minecraft.server.packs.PackType;
import net.minecraft.server.packs.repository.FolderRepositorySource;
import net.minecraft.server.packs.repository.PackRepository;
import net.minecraft.server.packs.repository.RepositorySource;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Adds the PyFabric generated pack to every resource-pack / data-pack repository. */
@Mixin(PackRepository.class)
public abstract class PackRepositoryMixin {
	@Shadow
	@Final
	@Mutable
	private Set<RepositorySource> sources;

	@Inject(method = "<init>", at = @At("RETURN"))
	private void pyfabric$addGeneratedPack(RepositorySource[] repositorySources, CallbackInfo ci) {
		PackType type = null;
		for (RepositorySource source : sources) {
			if (source instanceof FolderRepositorySource folder) {
				type = ((FolderRepositorySourceAccessor) folder).pyfabric$packType();
				break;
			}
		}
		if (type == null) return;
		Set<RepositorySource> copy = new LinkedHashSet<>(sources);
		copy.add(GeneratedPacks.source(type));
		sources = copy;
	}
}
