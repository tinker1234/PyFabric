"""Timber & Veins - two classic gameplay mods in ~60 lines.

* Break a log with an axe -> the whole tree comes down.
* Sneak while breaking an ore with a pickaxe -> the connected vein is mined too.

Shows: block break events, block tags, flood fill over the world, damaging the tool,
and a config file (config/pymods/timber.json) players can edit.
"""
from collections import deque

from pyfabric import events, mc, storage

cfg = storage.config({"max_logs": 256, "max_ores": 64, "require_sneak_for_trees": False})

LOGS = mc.tag_key("block", "minecraft:logs")
ORES = mc.tag_key("block", "c:ores")          # Fabric's shared "all ores" tag, includes modded ores


def connected(level, start, matches, limit):
    """Breadth-first search through the 26 neighbours of each block."""
    seen, queue, found = {start.asLong()}, deque([start]), []
    while queue and len(found) < limit:
        pos = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = pos.offset(dx, dy, dz)
                    key = n.asLong()
                    if key in seen:
                        continue
                    seen.add(key)
                    if matches(level.getBlockState(n)):
                        found.append(n)
                        queue.append(n)
    return found[:limit]


def break_all(level, player, positions):
    tool = player.getMainHandItem()
    for pos in positions:
        if tool.isEmpty():
            break                                   # tool broke
        level.destroyBlock(pos, True, player)
        tool.hurtAndBreak(1, player, mc.EquipmentSlot.MAINHAND)


@events.on_block_break
def chop(level, player, pos, state, block_entity):
    if level.isClientSide() or player.isCreative():
        return
    tool = player.getMainHandItem()
    if mc.is_(state, LOGS) and mc.has_tag(tool, "minecraft:axes"):
        if cfg["require_sneak_for_trees"] and not player.isShiftKeyDown():
            return
        block = state.getBlock()
        break_all(level, player, connected(level, pos, lambda s: s.getBlock() == block, cfg["max_logs"]))
    elif mc.is_(state, ORES) and mc.has_tag(tool, "minecraft:pickaxes") and player.isShiftKeyDown():
        block = state.getBlock()
        break_all(level, player, connected(level, pos, lambda s: s.getBlock() == block, cfg["max_ores"]))
