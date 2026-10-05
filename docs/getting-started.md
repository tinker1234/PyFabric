# Getting started with PyFabric

This tutorial builds a small mod step by step. You will add an item, a block, a recipe, react to events,
add a command and use hot reload. Every step is something you can try in-game straight away.

* [0. Setup](#0-setup)
* [1. Your mod folder](#1-your-mod-folder)
* [2. Saying hello](#2-saying-hello)
* [3. Hot reload](#3-hot-reload)
* [4. A new item](#4-a-new-item)
* [5. Giving the item a power](#5-giving-the-item-a-power)
* [6. A new block](#6-a-new-block)
* [7. Recipes](#7-recipes)
* [8. A command](#8-a-command)
* [9. Remembering things](#9-remembering-things)
* [10. Doing things over time](#10-doing-things-over-time)
* [11. Client-side code](#11-client-side-code)
* [12. When something goes wrong](#12-when-something-goes-wrong)
* [Where next](#where-next)

## 0. Setup

1. Install Minecraft **26.3** with **Fabric Loader** (0.19.5 or newer).
2. Download **Fabric API** for 26.3 and put it in `.minecraft/mods/`.
3. Put **`pyfabric-1.2.0.jar`** in `.minecraft/mods/`.
4. Start the game once. PyFabric creates the folder `.minecraft/pymods/`.

The same steps work for a dedicated server (put things in the server folder instead of `.minecraft`).

> **Tip — an editor:** any editor works, but one with Python support (VS Code, PyCharm) gives you syntax
> highlighting and catches typos. Auto-completion for Minecraft classes is not available because they are Java.

## 1. Your mod folder

A Python mod is a folder inside `pymods/`:

```
.minecraft/
  mods/
    fabric-api-….jar
    pyfabric-1.2.0.jar
  pymods/
    gemstones/              <- your mod; the folder name is the mod id (a-z, 0-9, _)
      main.py               <- runs on the client and on the server
      client.py             <- optional, runs only on the client
      pymod.json            <- optional metadata
      assets/gemstones/…    <- optional: textures, sounds, translations (like a resource pack)
      data/gemstones/…      <- optional: any data-pack files (like a data pack)
```

The mod id is used as the **namespace** of everything the mod adds: an item called `"sapphire"` becomes
`gemstones:sapphire`.

`pymod.json` is optional:

```json
{
  "name": "Gemstones",
  "version": "1.0.0",
  "description": "Sapphires and more",
  "authors": ["You"],
  "load_after": ["some_other_pymod"]
}
```

A single file such as `pymods/my_tweak.py` is also a complete mod — handy for small things.

## 2. Saying hello

Create `pymods/gemstones/main.py`:

```python
from pyfabric import log, events, players

log("Gemstones is loading!")

@events.on_player_join
def welcome(player):
    players.tell(player, "&bWelcome! Have you found any sapphires yet?")
```

Start the game and open a world. The log shows `[gemstones] Gemstones is loading!` and you get the
message in chat. `&b` is a Minecraft colour code (aqua) — they work in every message (`&a` green, `&c` red,
`&6` gold, `&l` bold, `&r` reset…).

`@events.on_player_join` is a **decorator**: it registers the function below it to be called when the event
happens. Each event passes its own arguments; see the [API reference](api-reference.md#events).

## 3. Hot reload

Change the message in `main.py`, save, and type in chat:

```
/pyfabric reload
```

Leave and rejoin the world (or ask a friend to join): the new message is used. Reloading reruns every mod's
code and swaps in the new event handlers, commands, item/block behaviour, recipes, loot tables and tags.

Two things need a **restart** instead: adding new items/blocks/key bindings (Minecraft locks its registries at
startup) and changing textures on the client (press `F3`+`T` to reload resources).

`/pyfabric list` shows every Python mod and whether it loaded.

## 4. A new item

```python
from pyfabric import registry

sapphire = registry.item("sapphire", rarity="uncommon", tooltip="Blue and brilliant")
```

Restart the game (new items need a restart). The sapphire is in the **Ingredients** creative tab, with a
purple-black "missing texture" for now. Add a 16×16 PNG at:

```
pymods/gemstones/assets/gemstones/textures/item/sapphire.png
```

and restart again. PyFabric generates the item model, the item definition and the English name ("Sapphire")
for you. If you prefer to borrow a vanilla texture while prototyping: `registry.item("sapphire", texture="minecraft:item/diamond")`.

Useful options: `stack_size=16`, `durability=250`, `fireproof=True`, `tab="combat"` and
`name="Star Sapphire"`. A **tool** is one argument away:

```python
sapphire_sword = registry.item("sapphire_sword", tool="sword", material="diamond", attack_damage=5)
```

and **food** too:

```python
candy = registry.item("sapphire_candy", food=registry.food(
    nutrition=4, saturation=0.5, always_edible=True,
    effects=[registry.effect("speed", seconds=20, amplifier=1)]))
```

## 5. Giving the item a power

Items get behaviour from **hooks** — decorators on the item handle:

```python
from pyfabric import mc, players, world

@sapphire.on_use
def use(level, player, hand):
    """Right-click: a burst of light and night vision."""
    if level.isClientSide():
        return mc.SUCCESS                       # the client just plays the arm swing
    players.effect(player, "night_vision", seconds=30)
    world.particles(level, "minecraft:glow", player, count=20, spread=1.0)
    world.sound(level, player, "minecraft:block.amethyst_block.chime")
    player.getCooldowns().addCooldown(player.getItemInHand(hand), 100)   # 5 s cooldown
    return mc.SUCCESS
```

Hooks *do* hot-reload — change the effect, `/pyfabric reload`, right-click again.

Many hooks run on both the client and the server. Change the world only on the server side
(`if level.isClientSide(): return ...` at the top), otherwise you will see "ghost" effects.

Return values matter for interaction hooks: `mc.SUCCESS` (it worked), `mc.PASS` (not handled, carry on),
`mc.FAIL` (block the action). Returning `None` means "default behaviour".

Other item hooks: `on_use_on_block`, `on_use_on_entity`, `on_hit`, `on_mine`, `on_inventory_tick`, `on_eaten`,
`on_crafted`, `tooltip`, `glint` — see the [reference](api-reference.md#item-hooks).

## 6. A new block

```python
sapphire_block = registry.block("sapphire_block", strength=5, sound="metal",
                                tool="pickaxe", tool_tier="iron", requires_tool=True, light=4)

sapphire_ore = registry.block("sapphire_ore", strength=3, tool="pickaxe", tool_tier="iron",
                              requires_tool=True, drops="sapphire", drop_count=(1, 2))
```

The texture goes in `assets/gemstones/textures/block/sapphire_block.png`. PyFabric generates the block model,
block state, item, loot table (it drops itself, or the item you name in `drops`, with Silk Touch and Fortune
working like vanilla ores) and the mining tags.

Make the ore appear in new chunks:

```python
from pyfabric import worldgen

worldgen.ore("sapphire_ore", size=5, per_chunk=6, min_y=-16, max_y=48)
```

Blocks have hooks too:

```python
@sapphire_block.on_step
def zoom(level, pos, state, entity):
    if not level.isClientSide() and isinstance(entity, mc.LivingEntity):   # not dropped items etc.
        players.effect(entity, "speed", seconds=2, amplifier=2, particles=False)
```

## 7. Recipes

```python
from pyfabric import recipes

recipes.shaped("sapphire_block", ["SSS", "SSS", "SSS"], S="sapphire")
recipes.shapeless("sapphire", ["sapphire_block"], count=9)
recipes.smelting("sapphire", "sapphire_ore", xp=1.0, blasting=True)
recipes.shaped("sapphire_sword", [" S ", " S ", " T "], S="sapphire", T="stick")
```

Short ids like `"sapphire"` mean *your* item if your mod declared it, otherwise the vanilla one (`"stick"` is
`minecraft:stick`). Tags work with `#`: `P="#minecraft:planks"`. Recipes hot-reload.

## 8. A command

```python
from pyfabric import command, CommandError, players

@command("gems give <target:player> [amount:int(1,64)=1]", permission=2)
def give_gems(ctx, target, amount):
    players.give(target, "gemstones:sapphire", amount)
    ctx.reply(f"Gave {amount} sapphire(s) to {players.name(target)}")

@command("gems count")
def count(ctx):
    player = ctx.require_player()               # errors nicely if run from the console
    inv = player.getInventory()
    n = sum(inv.getItem(i).getCount() for i in range(inv.getContainerSize())
            if mc.id_of(inv.getItem(i)) == "gemstones:sapphire")
    if n == 0:
        raise CommandError("You have no sapphires!")   # shown in red
    ctx.reply(f"You have {n} sapphire(s)")
```

The signature string describes the command: plain words are sub-commands, `<name:type>` is required,
`[name:type=default]` optional. Minecraft auto-completes and validates the arguments for you. Types:
`int`, `float`, `bool`, `word`, `string`, `text`, `player`, `players`, `entity`, `entities`, `pos`, `vec3`,
`item`, `block` — details in the [reference](api-reference.md#commands).

`permission=2` restricts it to operators.

## 9. Remembering things

**Settings** that server owners can edit go in a config file:

```python
from pyfabric import storage

cfg = storage.config({"ore_message": True, "bonus_chance": 0.1})
# creates config/pymods/gemstones.json with these defaults; edits are read on load / reload
```

**Game data** that belongs to a world (like player statistics) goes in world data:

```python
@events.on_block_break
def count_ores(level, player, pos, state, block_entity):
    if mc.id_of(state) == "gemstones:sapphire_ore":
        data = storage.world_data()                         # saved in <world>/pyfabric/gemstones.json
        mined = data.setdefault("mined", {})
        name = players.name(player)
        mined[name] = mined.get(name, 0) + 1
```

`world_data()` is saved automatically whenever the world saves. Use JSON-friendly values only (dict, list,
str, int, float, bool).

## 10. Doing things over time

```python
from pyfabric import scheduler

@scheduler.every(seconds=300)
def remind(server):
    players.broadcast("&7Tip: sapphire ore glows faintly in the dark.")

scheduler.after(seconds=5, fn=lambda server: log("five seconds after loading"))
```

Tasks run on the server thread (safe to change the world from) and are cancelled on reload.
`every()` and `after()` return a task with `.cancel()`.

## 11. Client-side code

Put client-only code in `client.py` next to `main.py`:

```python
# pymods/gemstones/client.py
from pyfabric import client

show = {"on": True}

@client.on_key("Toggle gem counter", "G")
def toggle(mc):
    show["on"] = not show["on"]

@client.hud
def draw(g, mc):
    if show["on"] and mc.player is not None:
        client.draw_text(g, "&bGemstones active", 4, 4)
```

`client.py` never runs on dedicated servers, so it may use client-only Minecraft classes.

## 12. When something goes wrong

* A mod that crashes while loading is skipped; the others still load. `/pyfabric list` shows `[FAILED]` with
  the error, and the log has the full Python traceback with file and line.
* Errors inside event handlers, hooks, commands and tasks never crash the game. They are logged (repeated
  errors are rate-limited) and online operators get a short red message.
* `/pyfabric run <code>` runs a line of Python on the server — great for poking at things:
  `/pyfabric run player.getHealth()`, `/pyfabric run mc.item("gemstones:sapphire")`,
  `/pyfabric run world.set_block(level, player.blockPosition().above(3), "minecraft:gold_block")`.
* Java errors appear as `JavaException` (they are *not* a subclass of Python's `Exception`) — catch
  `pyfabric.ERRORS` to handle both. More gotchas in [java-interop.md](java-interop.md).

## Where next

* Read the [example mods](examples.md) — each one is short and shows a different area.
* Browse the [API reference](api-reference.md).
* Learn to use **any** Minecraft or Fabric class: [java-interop.md](java-interop.md).
