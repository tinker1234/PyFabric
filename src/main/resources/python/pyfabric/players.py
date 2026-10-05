"""Everyday helpers for players and other living entities (server side).

    players.tell(player, "&aHello!")
    players.give(player, "minecraft:diamond", 3)
    players.effect(player, "speed", seconds=30, amplifier=1)
    players.title(player, "Round 1", "Fight!")
"""
import java

from . import _core, mc
from .text import as_component

_t = java.type
TitlePacket = _t("net.minecraft.network.protocol.game.ClientboundSetTitleTextPacket")
SubtitlePacket = _t("net.minecraft.network.protocol.game.ClientboundSetSubtitleTextPacket")
TimesPacket = _t("net.minecraft.network.protocol.game.ClientboundSetTitlesAnimationPacket")
Relative = _t("net.minecraft.world.entity.Relative")
HashSet = _t("java.util.HashSet")


def server():
    """The running MinecraftServer (None before it starts)."""
    return _core.Bridge.server()


def online():
    """List of online ServerPlayers."""
    s = server()
    return [] if s is None else list(s.getPlayerList().getPlayers())


def get(name):
    """Online player by name, or None."""
    s = server()
    return None if s is None else s.getPlayerList().getPlayerByName(name)


def name(entity):
    return str(entity.getName().getString())


def tell(player, message):
    """Chat message to one player."""
    player.sendSystemMessage(as_component(message))


def actionbar(player, message):
    """Message above the hotbar."""
    player.sendOverlayMessage(as_component(message))


def broadcast(message):
    """Chat message to everyone online (and the console)."""
    s = server()
    if s is not None:
        s.getPlayerList().broadcastSystemMessage(as_component(message), False)


def title(player, title, subtitle=None, fade_in=10, stay=60, fade_out=20):
    """Big title on the screen (times in ticks)."""
    conn = player.connection
    conn.send(TimesPacket(int(fade_in), int(stay), int(fade_out)))
    if subtitle is not None:
        conn.send(SubtitlePacket(as_component(subtitle)))
    conn.send(TitlePacket(as_component(title)))


def give(player, item, count=1):
    """Give items (drops them at the player's feet if the inventory is full)."""
    stack = mc.stack(item, count) if not hasattr(item, "getCount") else item
    player.getInventory().add(stack)
    if not stack.isEmpty():          # inventory full: drop the rest at the player's feet
        ItemEntity = _t("net.minecraft.world.entity.item.ItemEntity")
        player.level().addFreshEntity(ItemEntity(player.level(), player.getX(), player.getY(), player.getZ(), stack))
    return stack


def held(player):
    """ItemStack in the main hand."""
    return player.getMainHandItem()


def heal(entity, amount=None):
    """Heal by ``amount`` hearts-halves, or fully."""
    if amount is None:
        entity.setHealth(entity.getMaxHealth())
    else:
        entity.heal(float(amount))


def feed(player, food=20, saturation=5.0):
    data = player.getFoodData()
    data.setFoodLevel(int(food))
    data.setSaturation(float(saturation))


def effect(entity, effect_id, seconds=10, amplifier=0, particles=True):
    """Apply a potion effect: effect(player, 'night_vision', seconds=60)."""
    entity.addEffect(mc.MobEffectInstance(mc.effect(effect_id), int(seconds * 20), int(amplifier), False, bool(particles)))


def clear_effects(entity):
    entity.removeAllEffects()


def teleport(entity, x, y=None, z=None, level=None):
    """Teleport to coordinates / a BlockPos / another entity, optionally in another dimension."""
    if y is None:
        target = x
        if hasattr(target, "position") and hasattr(target, "level"):
            level = level or target.level()
            v = target.position()
            x, y, z = v.x, v.y, v.z
        else:
            x, y, z = target.getX() + 0.5, target.getY(), target.getZ() + 0.5
    level = level or entity.level()
    entity.teleportTo(level, float(x), float(y), float(z), HashSet(), entity.getYRot(), entity.getXRot(), True)


def set_flying(player, allowed=True):
    """Let a survival player fly (like creative)."""
    abilities = player.getAbilities()
    abilities.mayfly = bool(allowed)
    if not allowed:
        abilities.flying = False
    player.onUpdateAbilities()


def gamemode(player, mode):
    """'survival' | 'creative' | 'adventure' | 'spectator'."""
    player.setGameMode(mc.GameType.byName(mode))


def is_op(player):
    s = server()
    return s is not None and s.getPlayerList().isOp(player.nameAndId())


def looking_at(player, distance=5.0):
    """BlockPos the player is looking at, or None."""
    hit = player.pick(float(distance), 1.0, False)   # partial tick 1.0 = current rotation
    HitType = _t("net.minecraft.world.phys.HitResult$Type")
    return hit.getBlockPos() if hit.getType() == HitType.BLOCK else None
