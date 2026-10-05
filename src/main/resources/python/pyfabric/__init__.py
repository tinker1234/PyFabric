"""PyFabric - write Minecraft Fabric mods in Python.

A Python mod is a folder in ``.minecraft/pymods/`` with a ``main.py`` (runs on client and server)
and optionally a ``client.py`` (runs only on the client). Typical imports::

    from pyfabric import events, registry, recipes, players, world, scheduler, storage, mc
    from pyfabric import command, CommandError, text, log

Modules:
    events     react to game events (joins, block breaks, damage, ticks, chat, any Fabric event)
    registry   new items, blocks, food, tools and creative tabs
    recipes    crafting / smelting / stonecutting recipes
    resources  textures, models, translations, loot tables, tags, raw data/asset files
    commands   chat commands with typed arguments (``command`` decorator)
    scheduler  run code later or every N ticks
    players    tell / give / heal / effect / teleport / titles ...
    world      set blocks, spawn entities, sounds, particles, explosions, run commands
    storage    JSON config files and per-world save data
    worldgen   ores that generate in new chunks
    mc         common Minecraft classes and id lookups (mc.item('minecraft:diamond'))
    text       chat text with colours (text("hi", color="gold"))
    client     key bindings, HUD drawing, client ticks (client.py only)

Every Java class is available too: ``import java; Foo = java.type("net.minecraft....Foo")``.
"""
from . import _core
from . import mc, events, registry, resources, recipes, commands, scheduler, players, world, storage, worldgen
from .commands import command, CommandError
from .mc import SUCCESS, CONSUME, PASS, FAIL
from ._core import JavaException, ERRORS
from .text import text, as_component, plain

__version__ = "1.1.0"

__all__ = ["mc", "events", "registry", "resources", "recipes", "commands", "scheduler", "players", "world",
           "storage", "worldgen", "command", "CommandError", "text", "as_component", "plain", "log", "mod", "server",
           "SUCCESS", "CONSUME", "PASS", "FAIL", "JavaException", "ERRORS"]


def log(*args, level="info"):
    """Write to the game log, tagged with your mod id. level: debug | info | warn | error."""
    _core.Bridge.log(_core.owner(), level, " ".join(str(a) for a in args))


def mod():
    """Info about the calling mod: .id .name .version .path .description."""
    return _core.mods.get(_core.owner())


def server():
    """The running MinecraftServer, or None if no world is running."""
    return _core.Bridge.server()


def is_client():
    """True when running inside the game client (also true in singleplayer)."""
    return bool(_core.Bridge.isClient())
