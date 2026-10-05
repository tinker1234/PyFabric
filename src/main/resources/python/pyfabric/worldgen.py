"""World generation: make your blocks appear in newly generated chunks.

    worldgen.ore("ruby_ore", size=5, per_chunk=6, min_y=-48, max_y=32)

Ores are added to the generation of new chunks only (explore somewhere new to find them).
Call these while the game starts (in main.py).
"""
import java

from . import _core, resources

_t = java.type
BiomeModifications = _t("net.fabricmc.fabric.api.biome.v1.BiomeModifications")
BiomeSelectors = _t("net.fabricmc.fabric.api.biome.v1.BiomeSelectors")
Decoration = _t("net.minecraft.world.level.levelgen.GenerationStep$Decoration")
Registries = _t("net.minecraft.core.registries.Registries")
ResourceKey = _t("net.minecraft.resources.ResourceKey")
Identifier = _t("net.minecraft.resources.Identifier")

_REPLACEABLE = {
    "stone": "minecraft:stone_ore_replaceables",
    "deepslate": "minecraft:deepslate_ore_replaceables",
    "netherrack": "minecraft:base_stone_nether",
    "end_stone": None,
}
_DIMENSIONS = {
    "overworld": BiomeSelectors.foundInOverworld,
    "nether": BiomeSelectors.foundInTheNether,
    "end": BiomeSelectors.foundInTheEnd,
}
_added = set()   # feature ids already hooked into biomes (survives reloads)


def ore(block, *, deepslate_block=None, size=6, per_chunk=8, min_y=-64, max_y=64, spread="uniform",
        dimension="overworld", replaces=("stone",), id=None):
    """Generate an ore vein feature.

    block            the ore block id (e.g. 'ruby_ore')
    deepslate_block  optional variant placed where it replaces deepslate
    size             blocks per vein (iron is 9, diamond 4-8)
    per_chunk        veins per chunk
    min_y / max_y    height range; spread 'uniform' or 'triangle' (most common in the middle)
    dimension        'overworld' | 'nether' | 'end'
    replaces         which stone it replaces: 'stone', 'deepslate', 'netherrack', 'end_stone'
    """
    block_id = _core.resolve(block)
    fid = _core.namespaced(id or block_id.split(":", 1)[1])
    ns, path = fid.split(":", 1)

    targets = []
    for kind in replaces if isinstance(replaces, (list, tuple)) else (replaces,):
        state = deepslate_block if kind == "deepslate" and deepslate_block else block_id
        if kind == "end_stone":
            rule = {"predicate_type": "minecraft:block_match", "block": "minecraft:end_stone"}
        else:
            rule = {"predicate_type": "minecraft:tag_match", "tag": _REPLACEABLE[kind]}
        targets.append({"state": _core.resolve(state), "target": rule})
    if deepslate_block and "deepslate" not in (replaces if isinstance(replaces, (list, tuple)) else (replaces,)):
        targets.append({"state": _core.resolve(deepslate_block),
                        "target": {"predicate_type": "minecraft:tag_match", "tag": _REPLACEABLE["deepslate"]}})

    resources.data(f"{ns}/worldgen/feature/{path}.json", {
        "type": "minecraft:ore", "size": int(size), "discard_chance_on_air_exposure": 0.0, "targets": targets})
    height = {"type": "minecraft:trapezoid" if spread == "triangle" else "minecraft:uniform",
              "min_inclusive": {"absolute": int(min_y)}, "max_inclusive": {"absolute": int(max_y)}}
    resources.data(f"{ns}/worldgen/placed_feature/{path}.json", {
        "feature": fid,
        "placement": [{"type": "minecraft:count", "count": int(per_chunk)}, {"type": "minecraft:in_square"},
                      {"type": "minecraft:height_range", "height": height}, {"type": "minecraft:biome"}]})

    if fid not in _added:
        if _core.phase != "init":
            _core.Bridge.log(_core.owner(), "warn", f"New ore {fid} will generate after a restart")
            return fid
        key = ResourceKey.create(Registries.PLACED_FEATURE, Identifier.parse(fid))
        BiomeModifications.addFeature(_DIMENSIONS[dimension](), Decoration.UNDERGROUND_ORES, key)
        _added.add(fid)
    return fid
