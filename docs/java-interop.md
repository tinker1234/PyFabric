# Using Java & Minecraft classes from Python

PyFabric's helpers cover the common things, but **every** class of Minecraft, Fabric API, other installed
mods and the Java standard library can be used directly from Python. This page explains how, and lists the
handful of differences between Python and Java worth knowing.

## Getting a class

```python
import java

Items = java.type("net.minecraft.world.item.Items")
ItemStack = java.type("net.minecraft.world.item.ItemStack")
Properties = java.type("net.minecraft.world.item.Item$Properties")      # nested classes use $
ArrayList = java.type("java.util.ArrayList")

stack = ItemStack(Items.DIAMOND, 3)        # constructors: call the class
Items.DIAMOND                               # static fields
mc.Identifier.parse("minecraft:stone")      # static methods
stack.getCount()                            # instance methods
```

`pyfabric.mc` already holds the most common classes (`mc.Items`, `mc.BlockPos`, `mc.Component`…).

### Which names?

From 26.1 on, Minecraft ships **unobfuscated** with Mojang's official names, and Fabric uses them too. The
names you see in Fabric's documentation, in the decompiled game (`./gradlew genSources` in any Fabric
project) and in other mods' source code are exactly the names that work at runtime. A few examples:

| What | Class |
|---|---|
| Items / blocks | `net.minecraft.world.item.Items`, `net.minecraft.world.level.block.Blocks` |
| Entity type constants | `net.minecraft.world.entity.EntityTypes` (`EntityTypes.PIG`) |
| A world | `net.minecraft.server.level.ServerLevel` |
| A player on the server | `net.minecraft.server.level.ServerPlayer` |
| Chat text | `net.minecraft.network.chat.Component` |
| Ids | `net.minecraft.resources.Identifier` |
| Fabric events | `net.fabricmc.fabric.api.event...`, `net.fabricmc.fabric.api.entity.event.v1...` |

Explore interactively in-game: `/pyfabric run dir(player)` lists everything a player object offers,
`/pyfabric run player.getClass()` tells you its class.

## Python ↔ Java values

| Java | In Python |
|---|---|
| `int`, `long`, `short`, `byte` | `int` |
| `float`, `double` | `float` — Python floats are accepted for Java `float` parameters (PyFabric enables that conversion) |
| `boolean` | `bool` |
| `String` | `str` |
| `null` | `None` |
| `List`, arrays | indexable and iterable: `players[0]`, `for p in players`, `len(players)`; `list(x)` makes a Python list |
| `Set`, `Collection`, `Iterable` | iterable: `for x in collection` |
| `Map` | use the Java methods: `m.get(k)`, `m.put(k, v)`, `m.keySet()` |
| `Optional` | `opt.isPresent()`, `opt.get()`, `opt.orElse(None)` |
| `Stream` | Java methods: `stream.filter(lambda x: ...).toList()` |
| enums | `Direction.NORTH`, `Direction.values()`, compare with `==` |

Python values go the other way automatically when you call Java methods.

## Passing Python functions to Java

Any Python function or lambda can be passed where Java expects a *functional interface* (an interface with
one abstract method — `Runnable`, `Supplier`, `Predicate`, `Function`, Brigadier's `Command`, Fabric event
listeners…):

```python
ctx.getSource().sendSuccess(lambda: mc.Component.literal("done"), False)     # Supplier<Component>
names.stream().map(lambda s: s.upper()).toList()                              # Function
```

For Fabric events use `events.listen()` rather than `Event.register()` directly: it figures out the
listener type, handles errors and makes the handler hot-reloadable.

**Not supported:** subclassing Java classes in Python (`class MyItem(Item)`) and mixins. That's why
PyFabric provides `registry.item()` / `registry.block()` with hooks — they are Java subclasses that call your
Python functions. If you need a mixin or a custom block entity, write that small part as a regular Java
Fabric mod and call it from Python.

## The gotchas

### 1. Java exceptions are not `Exception`

GraalPy raises Java exceptions as `polyglot.ForeignException`, which derives from `BaseException`. A plain
`except Exception:` does **not** catch them:

```python
from pyfabric import JavaException, ERRORS

try:
    mc.Identifier.parse("Bad Id!")
except JavaException as e:          # Java errors only
    log("bad id:", e)

try:
    risky()
except ERRORS as e:                  # Python *and* Java errors
    ...
```

Java exceptions also carry no Python line numbers. PyFabric's error reports show the Java stack and name
the Python function they came from.

### 2. A field and a method with the same name → you get the field

Some classes have both, e.g. `Vec3` has fields `x, y, z` and methods `x(), y(), z()`. Python attribute
access returns the field:

```python
v = player.position()
v.x          # 12.5   (the field)
v.x()        # TypeError: 'float' object is not callable
```

### 3. `is` is a Python keyword

Java's `state.is(BlockTags.LOGS)` can't be written in Python. Use `mc.is_(state, BlockTags.LOGS)`,
`mc.has_tag(state, "minecraft:logs")` or `getattr(state, "is")(BlockTags.LOGS)`.

### 4. Getting a `java.lang.Class`

`java.type(...)` returns the class for calling static members. When a method wants a `Class` object
(e.g. `level.getEntitiesOfClass(Zombie.class, box)`), use `getattr(Zombie, "class")`.
`isinstance(entity, Zombie)` works directly, with classes and interfaces.

### 5. Client side vs server side

In singleplayer the client and the integrated server run in the same game, and many hooks run on both.
Change the world only on the server: `if level.isClientSide(): return`. `client.py` is never loaded on a
dedicated server, so only use client classes (`net.minecraft.client.*`) there.

### 6. Threads

Server code runs on the server thread, rendering and client ticks on the render thread. PyFabric has one
Python interpreter (with a GIL), so Python code is never run in parallel; still, don't touch the world from
your own threads — use `scheduler.after()` to get back on the server thread.

### 7. Commands inside commands are queued

`world.run_command()` called while another command is running (your own command handler, or
`/pyfabric run`) runs *after* the outer command finishes. Outside commands (events, scheduled tasks) it
runs immediately.

### 8. Load time vs. play time

The top level of `main.py` runs while the game is still starting: registries are open (that's why items
are declared there) but tags and item components aren't loaded yet. Creating `ItemStack`s or checking tags
there fails with "Tags not bound" / "Components not bound yet" — do that inside event handlers, hooks,
commands or scheduled tasks instead.

### 9. Overloads

When a Java method has several overloads, the arguments' Python types pick one. If the choice is ambiguous,
convert explicitly: `float(x)`, `int(x)`, `str(x)`.

## Recipes: doing things the Java way

Raw Brigadier command (exactly like a Java mod):

```python
CommandRegistrationCallback = java.type("net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback")
Commands = java.type("net.minecraft.commands.Commands")
IntegerArgumentType = java.type("com.mojang.brigadier.arguments.IntegerArgumentType")

def register(dispatcher, build_context, selection):
    def run(ctx):
        n = IntegerArgumentType.getInteger(ctx, "n")
        ctx.getSource().sendSuccess(lambda: mc.Component.literal(f"{n * n}"), False)
        return 1
    dispatcher.register(Commands.literal("square").then(
        Commands.argument("n", IntegerArgumentType.integer()).executes(run)))

events.listen(CommandRegistrationCallback.EVENT, register)
```

Item properties PyFabric doesn't wrap:

```python
EquipmentSlot = java.type("net.minecraft.world.entity.EquipmentSlot")
hat = registry.item("party_hat", properties=lambda p: p.equippable(EquipmentSlot.HEAD))
```

Block entity data, NBT, attributes, AI goals, packets — all reachable the same way. The
[`java_interop`](../examples/pymods/java_interop/main.py) example shows several of these.
