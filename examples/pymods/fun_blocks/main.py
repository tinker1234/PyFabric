"""Fun Blocks - blocks that react to players.

Shows: block hooks (stepped on, fallen on, right-clicked, punched, random ticks, redstone power,
scheduled ticks), block properties (speed, light, no loot), and reusing vanilla textures.
"""
from pyfabric import mc, players, recipes, registry, world

TAB = registry.creative_tab("fun_blocks", title="Fun Blocks", icon="bounce_pad")

bounce_pad = registry.block("bounce_pad", strength=0.6, sound="slime_block", tool=None, tab=TAB)
speed_path = registry.block("speed_path", strength=1.0, speed=1.6, sound="stone", tab=TAB)
healing_pad = registry.block("healing_pad", strength=1.5, light=7, tab=TAB)
landmine = registry.block("landmine", strength=0.5, drops=None, tab=TAB)
doorbell = registry.block("doorbell", strength=0.8, sound="wood", tool="axe", tab=TAB)
# No texture of our own: reuse a vanilla one.
pulse_block = registry.block("pulse_block", strength=1.5, texture="minecraft:block/redstone_lamp_on",
                             light=10, tab=TAB)


# ---- bounce pad: launch anything that lands on it, no fall damage --------------------------------------------
@bounce_pad.on_fall
def bounce(level, state, pos, entity, distance):
    motion = entity.getDeltaMovement()
    entity.setDeltaMovement(motion.x, 1.4, motion.z)
    entity.needsSync = True               # tell the client its velocity changed
    if not level.isClientSide():
        world.sound(level, pos, "minecraft:block.slime_block.fall", pitch=1.5)
    return True                           # True = cancel fall damage


@bounce_pad.on_step
def hop(level, pos, state, entity):
    if not entity.isShiftKeyDown():       # sneak to stand on it safely
        motion = entity.getDeltaMovement()
        entity.setDeltaMovement(motion.x, 0.9, motion.z)
        entity.needsSync = True


# ---- healing pad: regeneration while standing on it --------------------------------------------------------
@healing_pad.on_step
def heal(level, pos, state, entity):
    if not level.isClientSide() and isinstance(entity, mc.Player) and level.getGameTime() % 20 == 0:
        players.heal(entity, 2)
        world.particles(level, "minecraft:heart", entity, count=2)


# ---- landmine: explodes a moment after someone steps on it --------------------------------------------------
@landmine.on_step
def arm(level, pos, state, entity):
    if not level.isClientSide() and isinstance(entity, mc.LivingEntity):
        if not level.getBlockTicks().hasScheduledTick(pos, landmine.block):
            world.sound(level, pos, "minecraft:block.tripwire.click_on", pitch=2.0)
            level.scheduleTick(pos, landmine.block, 10)       # fires on_scheduled_tick in 10 ticks


@landmine.on_scheduled_tick
def boom(state, level, pos, random):
    level.removeBlock(pos, False)
    world.explode(level, pos, power=2.5)


# ---- doorbell: right-click to ring, everyone nearby hears it -------------------------------------------------
@doorbell.on_use
def ring(state, level, pos, player, hit):
    if not level.isClientSide():
        world.sound(level, pos, "minecraft:block.note_block.bell", volume=2.0)
        for p in world.entities_near(level, pos, 32, mc.Player):
            if p != player:
                players.actionbar(p, f"&e{players.name(player)} rang the doorbell!")
    return mc.SUCCESS


@doorbell.on_punch
def knock(state, level, pos, player):
    if not level.isClientSide():
        world.sound(level, pos, "minecraft:block.wooden_door.close", pitch=0.7)


# ---- pulse block: a redstone power source that reacts to its surroundings ------------------------------------
@pulse_block.redstone_power
def power(state, level, pos, direction):
    return 15                                               # full strength to every side


@pulse_block.on_random_tick
def sparkle(state, level, pos, random):
    world.particles(level, "minecraft:electric_spark", pos.above(), count=4, spread=0.3)


# ---- recipes -----------------------------------------------------------------------------------------------------
recipes.shaped("bounce_pad", ["SSS", "PPP"], S="minecraft:slime_ball", P="#minecraft:planks", count=2)
recipes.shaped("speed_path", ["SSS", "BBB"], S="minecraft:sugar", B="minecraft:stone_bricks", count=6)
recipes.shaped("healing_pad", ["GGG", "QQQ"], G="minecraft:glistering_melon_slice", Q="minecraft:quartz_block")
recipes.shaped("landmine", ["P", "T"], P="minecraft:stone_pressure_plate", T="minecraft:tnt")
recipes.shapeless("doorbell", ["#minecraft:planks", "minecraft:note_block"])
recipes.shaped("pulse_block", ["RRR", "RLR", "RRR"], R="minecraft:redstone", L="minecraft:redstone_lamp")
