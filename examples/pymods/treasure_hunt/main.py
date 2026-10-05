"""Treasure Hunt - a small mini-game built from the pieces of the other examples.

/hunt start [radius]   hide a chest full of loot somewhere near the players
/hunt stop             end the game
While a hunt runs, every player sees "hot / cold" hints above the hotbar. Whoever opens the
chest first wins.

Shows: game state in a Python class, filling a vanilla chest (block entity) from Python,
the use-block event, a repeating task that starts and stops, cross-mod optional content.
"""
import math
import random

import java

from pyfabric import CommandError, command, events, mc, players, registry, scheduler, world

Heightmap = java.type("net.minecraft.world.level.levelgen.Heightmap$Types")

LOOT = ["minecraft:diamond", "minecraft:emerald", "minecraft:golden_apple", "minecraft:ender_pearl",
        "minecraft:experience_bottle", "minecraft:name_tag"]
try:
    registry.get("ruby_gear:ruby")            # if the Ruby Gear example is installed, rubies are treasure too
    LOOT.append("ruby_gear:ruby")
except KeyError:
    pass


class Hunt:
    def __init__(self, level, pos):
        self.level = level
        self.pos = pos
        self.task = scheduler.every(seconds=1, fn=self.hints)
        self.started = scheduler.current_tick()

    def hints(self, server):
        for p in players.online():
            if p.level() != self.level:
                continue
            d = p.blockPosition().distManhattan(self.pos)
            if d < 6:
                hint = "&c&lBURNING HOT!"
            elif d < 15:
                hint = "&6Hot"
            elif d < 30:
                hint = "&eWarm"
            elif d < 60:
                hint = "&bCold"
            else:
                hint = "&9Freezing"
            players.actionbar(p, f"Treasure: {hint}")

    def stop(self):
        self.task.cancel()


hunt = None


def surface(level, x, z):
    """The first air block above the ground at x, z (where the chest goes)."""
    return mc.BlockPos(x, level.getHeight(Heightmap.MOTION_BLOCKING_NO_LEAVES, x, z), z)


@command("hunt start [radius:int(8,200)=40]", permission=2)
def start(ctx, radius):
    global hunt
    if hunt is not None:
        raise CommandError("A hunt is already running")
    center = mc.pos(ctx.position)
    level = ctx.level
    angle = random.uniform(0, 6.283)
    dist = random.uniform(radius * 0.5, radius)
    x = center.getX() + int(math.cos(angle) * dist)
    z = center.getZ() + int(math.sin(angle) * dist)
    pos = surface(level, x, z)

    world.set_block(level, pos, "minecraft:chest")
    chest = level.getBlockEntity(pos)
    for slot in random.sample(range(27), 6):
        chest.setItem(slot, mc.stack(random.choice(LOOT), random.randint(1, 4)))

    hunt = Hunt(level, pos)
    players.broadcast(f"&6&lA treasure chest has been hidden within {radius} blocks! Follow the hints.")
    for p in players.online():
        players.title(p, "&6Treasure Hunt!", "&eFind the hidden chest", stay=60)


@command("hunt stop", permission=2)
def stop(ctx):
    global hunt
    if hunt is None:
        raise CommandError("No hunt running")
    p = hunt.pos
    hunt.stop()
    hunt = None
    players.broadcast(f"&7The hunt was cancelled. The chest was at {p.getX()} {p.getY()} {p.getZ()}.")


@events.on_use_block
def opened(player, level, hand, hit):
    global hunt
    if hunt is None or level.isClientSide() or hit.getBlockPos() != hunt.pos:
        return None
    seconds = (scheduler.current_tick() - hunt.started) // 20
    hunt.stop()
    hunt = None
    players.broadcast(f"&a&l{players.name(player)} found the treasure in {seconds} seconds!")
    world.particles(level, "minecraft:totem_of_undying", player, count=60, spread=1.0, speed=0.3)
    world.sound(level, player, "minecraft:ui.toast.challenge_complete")
    return None            # let the chest open normally
