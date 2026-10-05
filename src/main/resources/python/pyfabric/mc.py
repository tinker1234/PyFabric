"""Shortcuts to frequently used Minecraft classes, plus id -> object lookups.

Every Minecraft / Fabric class is reachable from Python with ``java.type("full.class.Name")``
(Minecraft 26.x uses Mojang's official names, so they match the decompiled source and the wiki).
This module just saves you the typing for the common ones::

    from pyfabric.mc import Items, BlockPos, Component
    from pyfabric import mc
    diamond = mc.item("minecraft:diamond")
"""
import java

_t = java.type

# --- core -----------------------------------------------------------------------------------------------
Identifier = _t("net.minecraft.resources.Identifier")
ResourceKey = _t("net.minecraft.resources.ResourceKey")
BuiltInRegistries = _t("net.minecraft.core.registries.BuiltInRegistries")
Registries = _t("net.minecraft.core.registries.Registries")
Registry = _t("net.minecraft.core.Registry")
BlockPos = _t("net.minecraft.core.BlockPos")
Direction = _t("net.minecraft.core.Direction")
Vec3 = _t("net.minecraft.world.phys.Vec3")
AABB = _t("net.minecraft.world.phys.AABB")
Mth = _t("net.minecraft.util.Mth")

# --- text -----------------------------------------------------------------------------------------------
Component = _t("net.minecraft.network.chat.Component")
ChatFormatting = _t("net.minecraft.ChatFormatting")

# --- items & blocks --------------------------------------------------------------------------------------
Items = _t("net.minecraft.world.item.Items")
Item = _t("net.minecraft.world.item.Item")
ItemStack = _t("net.minecraft.world.item.ItemStack")
Blocks = _t("net.minecraft.world.level.block.Blocks")
Block = _t("net.minecraft.world.level.block.Block")
BlockState = _t("net.minecraft.world.level.block.state.BlockState")
SoundType = _t("net.minecraft.world.level.block.SoundType")
MapColor = _t("net.minecraft.world.level.material.MapColor")
DataComponents = _t("net.minecraft.core.component.DataComponents")

# --- entities & players -----------------------------------------------------------------------------------
Entity = _t("net.minecraft.world.entity.Entity")
LivingEntity = _t("net.minecraft.world.entity.LivingEntity")
EntityType = _t("net.minecraft.world.entity.EntityType")
EntityTypes = _t("net.minecraft.world.entity.EntityTypes")   # the constants: EntityTypes.PIG, EntityTypes.ZOMBIE...
EntitySpawnReason = _t("net.minecraft.world.entity.EntitySpawnReason")
Player = _t("net.minecraft.world.entity.player.Player")
ServerPlayer = _t("net.minecraft.server.level.ServerPlayer")
GameType = _t("net.minecraft.world.level.GameType")
MobEffects = _t("net.minecraft.world.effect.MobEffects")
MobEffectInstance = _t("net.minecraft.world.effect.MobEffectInstance")
Attributes = _t("net.minecraft.world.entity.ai.attributes.Attributes")
EquipmentSlot = _t("net.minecraft.world.entity.EquipmentSlot")

# --- world -----------------------------------------------------------------------------------------------
Level = _t("net.minecraft.world.level.Level")
ServerLevel = _t("net.minecraft.server.level.ServerLevel")
ExplosionInteraction = _t("net.minecraft.world.level.Level$ExplosionInteraction")
SoundEvents = _t("net.minecraft.sounds.SoundEvents")
SoundSource = _t("net.minecraft.sounds.SoundSource")
ParticleTypes = _t("net.minecraft.core.particles.ParticleTypes")
MinecraftServer = _t("net.minecraft.server.MinecraftServer")

# --- interaction -------------------------------------------------------------------------------------------
InteractionResult = _t("net.minecraft.world.InteractionResult")
InteractionHand = _t("net.minecraft.world.InteractionHand")

SUCCESS = InteractionResult.SUCCESS   # the action happened (swing arm, stop further processing)
CONSUME = InteractionResult.CONSUME   # the action happened, no arm swing
PASS = InteractionResult.PASS         # not handled, let others / vanilla handle it
FAIL = InteractionResult.FAIL         # cancel the action


# --- id -> object lookups -----------------------------------------------------------------------------------

def ident(id_or_obj):
    """Identifier from 'namespace:path' (namespace defaults to minecraft)."""
    if not isinstance(id_or_obj, str):
        return id_or_obj
    return Identifier.parse(id_or_obj)


def _resolve(id):
    from . import _core
    return _core.resolve(id)


def _lookup(registry, id, kind):
    rid = ident(id)
    if not registry.containsKey(rid):
        raise KeyError(f"Unknown {kind} '{id}'")
    return registry.getValue(rid)


def item(id):
    """The Item for 'minecraft:diamond' (or an Item/handle passed through)."""
    if not isinstance(id, str):
        return getattr(id, "item", id)
    return _lookup(BuiltInRegistries.ITEM, _resolve(id), "item")


def block(id):
    """The Block for 'minecraft:stone' (or a Block/handle passed through)."""
    if not isinstance(id, str):
        return getattr(id, "block", id)
    return _lookup(BuiltInRegistries.BLOCK, _resolve(id), "block")


def state(id):
    """Default BlockState of a block id."""
    return block(id).defaultBlockState()


def stack(id, count=1):
    """ItemStack of an item id, Item or pyfabric item handle."""
    return ItemStack(item(id), int(count))


def entity_type(id):
    return _lookup(BuiltInRegistries.ENTITY_TYPE, id, "entity type")


def effect(id):
    """Holder<MobEffect> for 'speed', 'minecraft:regeneration', ..."""
    return BuiltInRegistries.MOB_EFFECT.wrapAsHolder(_lookup(BuiltInRegistries.MOB_EFFECT, id, "effect"))


def sound(id):
    return _lookup(BuiltInRegistries.SOUND_EVENT, id, "sound")


def particle(id):
    return _lookup(BuiltInRegistries.PARTICLE_TYPE, id, "particle")


def id_of(obj):
    """'minecraft:diamond' for an Item, Block, EntityType, ItemStack, BlockState or Entity (None if unknown)."""
    if isinstance(obj, ItemStack):
        obj = obj.getItem()
    elif isinstance(obj, BlockState):
        obj = obj.getBlock()
    elif isinstance(obj, Entity):
        obj = obj.getType()
    for cls, reg in ((Item, BuiltInRegistries.ITEM), (Block, BuiltInRegistries.BLOCK),
                     (EntityType, BuiltInRegistries.ENTITY_TYPE)):
        if isinstance(obj, cls):
            return str(reg.getKey(obj))
    return None


def pos(x, y=None, z=None):
    """BlockPos from (x, y, z), a tuple, a Vec3 or an entity."""
    if y is None:
        if hasattr(x, "blockPosition"):
            return x.blockPosition()
        if isinstance(x, BlockPos):
            return x
        if isinstance(x, (tuple, list)):
            x, y, z = x
        else:
            return BlockPos.containing(x)
    return BlockPos(int(x), int(y), int(z))


# --- tags --------------------------------------------------------------------------------------------------
# Java's ``is`` method clashes with Python's keyword, so use these helpers (or getattr(obj, "is")(...)).
TagKey = _t("net.minecraft.tags.TagKey")
BlockTags = _t("net.minecraft.tags.BlockTags")
ItemTags = _t("net.minecraft.tags.ItemTags")

_TAG_REGISTRIES = {"block": "BLOCK", "item": "ITEM", "entity_type": "ENTITY_TYPE", "fluid": "FLUID",
                   "biome": "BIOME", "damage_type": "DAMAGE_TYPE"}


def tag_key(registry, tag_id):
    """TagKey for e.g. tag_key('block', 'minecraft:logs')."""
    return TagKey.create(getattr(Registries, _TAG_REGISTRIES[registry]), ident(tag_id.lstrip("#")))


def is_(obj, what):
    """Java's obj.is(what) - works for BlockState, ItemStack, Holder, EntityType, FluidState..."""
    return bool(getattr(obj, "is")(what))


def has_tag(obj, tag):
    """has_tag(block_state, 'minecraft:logs'), has_tag(item_stack, 'minecraft:axes'), has_tag(entity, 'minecraft:undead').

    Works for BlockState, Block, ItemStack, Item, Entity and EntityType. Tags are loaded with the world,
    so this only works once a world is running (not at the top level of main.py).
    """
    kind = None
    if isinstance(obj, Entity):
        obj = obj.getType()
    if isinstance(obj, EntityType):
        obj, kind = obj.builtInRegistryHolder(), "entity_type"
    elif isinstance(obj, Block):
        obj, kind = obj.defaultBlockState(), "block"
    elif isinstance(obj, Item):
        obj, kind = obj.builtInRegistryHolder(), "item"
    elif isinstance(obj, ItemStack):
        kind = "item"
    elif isinstance(obj, BlockState):
        kind = "block"
    if isinstance(tag, str):
        if kind is None:
            raise TypeError(f"has_tag: can't tell the registry of {obj!r}; pass a TagKey (mc.tag_key(...))")
        tag = tag_key(kind, tag)
    return is_(obj, tag)
