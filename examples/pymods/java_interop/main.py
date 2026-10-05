"""Java Interop - the escape hatches. Everything in Minecraft and Fabric API is reachable.

Shows:
* events.listen() with an event pyfabric has no shortcut for (sleeping, entity loading)
* building a Brigadier command by hand, exactly like a Java mod would
* Java collections, Optional, streams and enums from Python
* catching Java exceptions (pyfabric.JavaException)
"""
import java

from pyfabric import JavaException, events, log, mc, players, world

EntitySleepEvents = java.type("net.fabricmc.fabric.api.entity.event.v1.EntitySleepEvents")
ServerEntityEvents = java.type("net.fabricmc.fabric.api.event.lifecycle.v1.ServerEntityEvents")
CommandRegistrationCallback = java.type("net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback")
Commands = java.type("net.minecraft.commands.Commands")
IntegerArgumentType = java.type("com.mojang.brigadier.arguments.IntegerArgumentType")
ArrayList = java.type("java.util.ArrayList")
Collectors = java.type("java.util.stream.Collectors")


# ---- any Fabric event: the listener gets exactly the arguments of the Java interface -------------------------
@events.listen(EntitySleepEvents.START_SLEEPING)
def sleeping(entity, bed_pos):
    if isinstance(entity, mc.ServerPlayer):
        players.broadcast(f"&7{players.name(entity)} went to bed. Zzz...")


@events.listen(ServerEntityEvents.ENTITY_LOAD)
def name_pigs(entity, level):
    """Every pig that appears gets a random name (shows how cheap events are in Python)."""
    if entity.getType() == mc.EntityTypes.PIG and not entity.hasCustomName():
        import random
        entity.setCustomName(mc.Component.literal(random.choice(["Bacon", "Hamlet", "Porkchop", "Wilbur"])))


# ---- a raw Brigadier command, the Java way ------------------------------------------------------------------------
def register(dispatcher, build_context, selection):
    def run(ctx):
        n = IntegerArgumentType.getInteger(ctx, "n")
        ctx.getSource().sendSuccess(lambda: mc.Component.literal(f"{n} squared is {n * n}"), False)
        return 1

    dispatcher.register(
        Commands.literal("square").then(
            Commands.argument("n", IntegerArgumentType.integer(0, 46340)).executes(run)))


events.listen(CommandRegistrationCallback.EVENT, register)


# ---- Java collections, streams, Optionals ----------------------------------------------------------------------
names = ArrayList()
for name in ("stone", "dirt", "diamond_ore"):
    names.add(name)
upper = names.stream().map(lambda s: s.upper()).collect(Collectors.joining(", "))
log("Java stream result:", upper)

maybe = mc.BuiltInRegistries.ITEM.getOptional(mc.ident("minecraft:diamond"))
log("Optional present:", maybe.isPresent(), "->", maybe.get())

# Java exceptions are NOT subclasses of Exception in GraalPy - catch JavaException (or pyfabric.ERRORS).
try:
    mc.Identifier.parse("Not A Valid Id!")
except JavaException as e:
    log("Caught a Java exception as expected:", str(e).splitlines()[0][:80])


# ---- enums ----------------------------------------------------------------------------------------------------
log("Directions:", [str(d) for d in mc.Direction.values()])
