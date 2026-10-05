"""Reacting to things that happen in the game.

Two ways to subscribe:

1. Friendly decorators for the common events::

       @events.on_player_join
       def hi(player):
           players.tell(player, "Welcome!")

2. ``listen`` works with *any* Fabric API event (all of Fabric API is available)::

       import java
       ServerTickEvents = java.type("net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents")

       @events.listen(ServerTickEvents.END_SERVER_TICK)
       def tick(server):
           ...

Handlers may return ``None`` to "have no opinion". For events that can be cancelled, return ``False``
(boolean events) or ``mc.FAIL`` / ``mc.SUCCESS`` / ``mc.PASS`` (InteractionResult events).
All subscriptions are hot-reload safe: ``/pyfabric reload`` swaps in your new code.
"""
import java
from . import _core

_counts = {}


@_core.on_reset
def _reset():
    _counts.clear()


def _key(owner, event, fn):
    name = f"{getattr(fn, '__module__', '?')}.{getattr(fn, '__qualname__', repr(fn))}"
    etype = str(_core.Bridge.listenerType(event)).rsplit(".", 1)[-1]
    base = f"{owner}|{etype}@{_core.identity(event)}|{name}"
    n = _counts.get(base, 0)
    _counts[base] = n + 1
    return base if n == 0 else f"{base}#{n}"


def listen(event, fn=None, *, adapter=None, _owner=None):
    """Subscribe ``fn`` to a Fabric ``Event``. Use directly or as ``@listen(Event)``.

    ``adapter`` (optional) converts the raw listener arguments before calling ``fn``.
    """
    def register(f):
        owner = _owner or _core.owner()
        key = _key(owner, event, f)
        target = f if adapter is None else (lambda *args: adapter(f, *args))
        where = f"event {key.split('|')[1].split('@')[0]} -> {_core.fn_name(f)}()"
        _core.Bridge.listen(event, key, owner, _core.guard(owner, where, target))
        return f

    return register if fn is None else register(fn)


def _event(cls, field):
    return getattr(java.type(cls), field)


def _shortcut(cls, field, adapter=None, doc=""):
    def decorator(fn):
        return listen(_event(cls, field), fn, adapter=adapter, _owner=_core.owner())
    decorator.__doc__ = doc
    return decorator


_LIFE = "net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents"
_TICK = "net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents"
_PLAYER = "net.fabricmc.fabric.api.entity.event.v1.ServerPlayerEvents"
_BREAK = "net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents"
_LIVING = "net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents"
_COMBAT = "net.fabricmc.fabric.api.entity.event.v1.ServerEntityCombatEvents"
_MSG = "net.fabricmc.fabric.api.message.v1.ServerMessageEvents"

# ---- server lifecycle ---------------------------------------------------------------------------------
on_server_start = _shortcut(_LIFE, "SERVER_STARTED", doc="fn(server) - the server finished starting.")
on_server_stop = _shortcut(_LIFE, "SERVER_STOPPING", doc="fn(server) - the server is shutting down.")
on_tick = _shortcut(_TICK, "END_SERVER_TICK", doc="fn(server) - every server tick (20 per second).")
on_world_tick = _shortcut(_TICK, "END_LEVEL_TICK", doc="fn(level) - every tick, once per dimension.")

# ---- players ------------------------------------------------------------------------------------------
on_player_join = _shortcut(_PLAYER, "JOIN", doc="fn(player) - a player joined the server.")
on_player_leave = _shortcut(_PLAYER, "LEAVE", doc="fn(player) - a player is leaving the server.")
on_player_respawn = _shortcut(_PLAYER, "AFTER_RESPAWN",
                              doc="fn(old_player, new_player, alive) - after respawn or returning from the End.")

# ---- blocks ---------------------------------------------------------------------------------------------
on_block_break = _shortcut(_BREAK, "AFTER", doc="fn(level, player, pos, state, block_entity) - a player broke a block.")
before_block_break = _shortcut(_BREAK, "BEFORE",
                               doc="fn(level, player, pos, state, block_entity) - return False to cancel the break.")

# ---- interaction ------------------------------------------------------------------------------------------
on_use_item = _shortcut("net.fabricmc.fabric.api.event.player.UseItemCallback", "EVENT",
                        doc="fn(player, level, hand) - right click with an item. Return mc.SUCCESS/FAIL/PASS.")
on_use_block = _shortcut("net.fabricmc.fabric.api.event.player.UseBlockCallback", "EVENT",
                         doc="fn(player, level, hand, hit) - right click on a block. Return mc.SUCCESS/FAIL/PASS.")
on_use_entity = _shortcut("net.fabricmc.fabric.api.event.player.UseEntityCallback", "EVENT",
                          doc="fn(player, level, hand, entity, hit) - right click on an entity.")
on_attack_entity = _shortcut("net.fabricmc.fabric.api.event.player.AttackEntityCallback", "EVENT",
                             doc="fn(player, level, hand, entity, hit) - left click on an entity.")
on_attack_block = _shortcut("net.fabricmc.fabric.api.event.player.AttackBlockCallback", "EVENT",
                            doc="fn(player, level, hand, pos, direction) - left click on a block.")

# ---- living entities ----------------------------------------------------------------------------------------
on_damage = _shortcut(_LIVING, "ALLOW_DAMAGE",
                      doc="fn(entity, source, amount) - an entity is about to be hurt. Return False to cancel.")
after_damage = _shortcut(_LIVING, "AFTER_DAMAGE",
                         doc="fn(entity, source, base_amount, taken, blocked) - an entity was hurt.")
before_death = _shortcut(_LIVING, "ALLOW_DEATH",
                         doc="fn(entity, source, amount) - an entity is about to die. Return False to keep it alive.")
on_death = _shortcut(_LIVING, "AFTER_DEATH", doc="fn(entity, source) - an entity died.")
on_kill = _shortcut(_COMBAT, "AFTER_KILLED_OTHER_ENTITY",
                    doc="fn(level, killer, victim, source) - an entity killed another one.")


# ---- chat ----------------------------------------------------------------------------------------------------
def _chat_adapter(fn, message, player, params):
    return fn(player, str(message.signedContent()))


def on_chat(fn):
    """fn(player, message: str) - a player sent a chat message."""
    return listen(_event(_MSG, "CHAT_MESSAGE"), fn, adapter=_chat_adapter, _owner=_core.owner())


def allow_chat(fn):
    """fn(player, message: str) - return False to block the message."""
    return listen(_event(_MSG, "ALLOW_CHAT_MESSAGE"), fn, adapter=_chat_adapter, _owner=_core.owner())
