# How PyFabric works

A short tour of the architecture, for the curious and for anyone extending PyFabric.

```
 Minecraft 26.3 + Fabric Loader + Fabric API
 └── pyfabric.jar (Java, ~1,200 lines + a ~2,500-line Python package)
       ├── GraalPy (Python 3.12 on the JVM, bundled jar-in-jar)
       ├── PythonHost ── one Python interpreter (Context) for all mods
       ├── Bridge ────── the small Java surface the Python package calls
       ├── EventSlots ── reload-safe adapter from Python functions to any Fabric Event
       ├── PyItem / PyBlock ── Item/Block subclasses that call Python hooks
       ├── GeneratedPacks + mixin ── always-on resource pack & data pack
       └── /pyfabric command
 └── python/pyfabric/ (Python, the API modders use) → extracted to .minecraft/pyfabric/lib
 └── .minecraft/pymods/<your mods>
```

## Embedding Python

Minecraft is a Java program, so PyFabric runs Python *inside the JVM* with
[GraalPy](https://www.graalvm.org/python/) (Oracle's Python 3 implementation built on the Truffle framework).
GraalPy and its standard library are ordinary Maven artifacts; the build bundles them into
`pyfabric.jar` with Fabric's jar-in-jar mechanism, so players install one file and need no Python.

There is **one** `Context` (interpreter) for the whole game, created during mod initialisation:

* `allowAllAccess(true)` + `hostClassLoader(<Fabric's class loader>)` let Python see every Minecraft, Fabric
  and mod class through `java.type(...)`.
* A custom `HostAccess` adds a lossy `double → float` conversion, because Minecraft takes `float` everywhere
  and Python only has doubles.
* Python's stdout/stderr are routed into the game log.

Because Minecraft 26.x is no longer obfuscated, the class and method names Python uses are the same in the
development environment and in a real game — no remapping layer is needed.

## Loading mods

`pyfabric/_loader.py` scans `pymods/`, orders mods by `load_after`, and imports each as a Python package:
`pymods/ruby_gear/main.py` becomes the module `pymods.ruby_gear.main` (the game directory is on `sys.path`
and `pymods` is a namespace package). That makes relative imports (`from . import util`) and cross-mod
imports (`from pymods.ruby_gear import main`) work. A mod that raises during import is marked failed; the
rest keep loading.

`main.py` runs from the Fabric `main` entrypoint (registries still open), `client.py` from the `client`
entrypoint.

The calling mod is found by walking the Python stack for a module named `pymods.<id>...` — that's how
`registry.item("ruby")` knows to call it `ruby_gear:ruby` and how errors are attributed to the right mod.

## Events: `EventSlots`

Fabric events take a Java listener object implementing the event's interface, and listeners can never be
unregistered. For each Python subscription PyFabric:

1. finds the listener interface by reading the element type of the event's internal handler array,
2. creates a `java.lang.reflect.Proxy` implementing it, whose handler calls the Python function and converts
   the result (`None` → "no opinion", `True/False`, `InteractionResult`),
3. remembers the proxy as a *slot* under a stable key (mod + event + function name).

On reload every slot is switched off. When the reloaded code subscribes again with the same key, the slot is
switched back on with the new function — so nothing is registered twice. A switched-off slot behaves exactly
like "no listener": it delegates to an invoker built from an empty listener array, so it returns whatever the
event returns when nobody listens.

The Python side wraps every handler in `_core.guard`, which reports errors with a proper Python traceback
(rate limited, and shown to online operators) and returns `None` instead of crashing.

## Items and blocks

Python can't subclass Java classes in GraalPy, so PyFabric ships `PyItem extends Item` and
`PyBlock extends Block`. Each holds a `Hooks` table (name → Python function); every overridden method looks
up its hook and falls back to vanilla behaviour if there is none or it returned `None`. Hot reload clears the
tables and the re-run code fills them again. Registering the same id again during a reload returns the
existing object instead of touching the (frozen) registry.

## Resources: generated packs

Items and blocks need models, translations, loot tables and tags; recipes are data-pack JSON. PyFabric keeps
two folders in `.minecraft/pyfabric/generated/`:

* `resources/` — a resource pack (`assets/…`)
* `data/` — a data pack (`data/…`)

After the mods run, `resources.write_packs()` copies every mod's own `assets/` and `data/` folders in, then adds
generated JSON (never overwriting shipped files; translations and tags are merged).

A mixin on `PackRepository`'s constructor adds a repository source for the right pack type (detected from the
repository's folder source) to *every* pack repository — the client's resource packs and each world's data
packs. The packs are *required* (always enabled, can't be turned off) and the data pack carries a `KnownPack`
id whose version is a hash of its contents, which keeps Minecraft from flagging worlds as "experimental"
because of data-pack world generation.

## Commands

Python keeps a table of declared commands. One permanent listener on `CommandRegistrationCallback` builds
Brigadier trees from the table whenever Minecraft (re)creates its command dispatcher (server start, `/reload`).
A signature like `"home set [name:word=home]"` becomes `literal("home").then(literal("set").executes(...)
.then(argument("name", word()).executes(...)))`. Hot reload removes the old roots from the live dispatcher and
triggers a data reload, which rebuilds them.

## Hot reload, step by step

1. `EventSlots.deactivateAll()` and `Hooks.clearAll()` (PyFabric's own internal listeners stay on)
2. reset hooks registered by the Python modules (commands table, scheduler, generated resources…)
3. delete `pymods.*` from `sys.modules`, rediscover mods, import them again
4. rewrite the generated packs, drop old commands, `server.reloadResources(...)` (like `/reload`)

## The radio

`/radio` and `pyfabric.radio` share one Java player (`src/client/java/dev/pyfabric/client/radio`):

* `RadioHttp` — a tiny HTTP/1.0 client (Java's `HttpURLConnection` rejects old Shoutcast servers' `ICY 200 OK`
  status line), following redirects.
* `IcyInputStream` — strips the ICY metadata blocks the server interleaves every `icy-metaint` bytes and
  reports `StreamTitle` changes.
* `RadioStream` — follows `.pls`/`.m3u` playlists, decodes MP3 frames with JLayer, applies the volume and
  writes PCM to a sink; reconnects with back-off when the stream drops.
* `JavaSoundSink` — plays through Java Sound, separate from Minecraft's OpenAL sound engine, so the radio
  keeps playing across menus and dimension changes.
* `RadioClient` — the game glue: Minecraft's volume sliders, chat/actionbar messages, saved settings, and
  listeners for Python (always called on the client thread).

## Repository layout

```
build.gradle, gradle.properties       Fabric Loom build; GraalPy bundled via `include`
src/main/java/dev/pyfabric/           Java side (Bridge, PythonHost, EventSlots, PyItem, PyBlock, ...)
src/main/java/dev/pyfabric/mixin/     the pack repository mixin
src/client/java/                      client entrypoint (runs client.py files)
src/main/resources/python/pyfabric/   the Python API
examples/pymods/                      example mods
tools/make_textures.py                generates the example textures
docs/                                 this documentation
```

## Testing

The example mods were verified on a headless dedicated server with *mock players*: real `ServerPlayer`
objects connected through Netty's `EmbeddedChannel` (the same technique Minecraft's GameTest framework uses),
so join events fire and every chat packet, title and actionbar message they receive can be inspected. The
tests use items, break blocks with the real block-breaking code, fire chat events, kill entities, and check
the results — 63 checks covering every example, run against both the development environment and a plain
Fabric server install with the built jar. The client side (textures, HUD, key binding, creative tabs,
tooltips) was checked by running the game under a virtual display.
