# PyFabric API reference

```python
from pyfabric import (events, registry, recipes, resources, commands, scheduler, players, world,
                      storage, worldgen, mc, command, CommandError, text, log, mod, server, is_client,
                      SUCCESS, CONSUME, PASS, FAIL, JavaException, ERRORS)
from pyfabric import client        # only in client.py
```

The source of every module is extracted to `.minecraft/pyfabric/lib/pyfabric/` on each start, so you can
always read exactly what a function does.

**Ids.** Wherever an id is expected you can write:

* a full id: `"minecraft:diamond"`, `"ruby_gear:ruby"`
* a short id: `"ruby"` means *your mod's* `ruby` if your mod declared it, otherwise `minecraft:ruby`
  (so `"stick"` is `minecraft:stick`)
* an item/block handle returned by `registry.item()` / `registry.block()`

**Positions.** Helpers that take a position accept a `BlockPos`, a `Vec3`, an `(x, y, z)` tuple or an entity.

* [Top level](#top-level)
* [events](#events)
* [registry](#registry) — [items](#registryitem), [item hooks](#item-hooks), [blocks](#registryblock), [block hooks](#block-hooks), [food](#food), [creative tabs](#creative-tabs)
* [recipes](#recipes)
* [resources](#resources)
* [worldgen](#worldgen)
* [commands](#commands)
* [scheduler](#scheduler)
* [players](#players)
* [world](#world)
* [storage](#storage)
* [text](#text)
* [mc](#mc)
* [client](#client)
* [Hot reload rules](#hot-reload-rules)

---

## Top level

| | |
|---|---|
| `log(*args, level="info")` | Write to the game log tagged with your mod id. `level`: `debug`, `info`, `warn`, `error`. `print()` also works (tagged `python`). |
| `mod()` | Info about the calling mod: `.id`, `.name`, `.version`, `.description`, `.authors`, `.path`, `.state`. |
| `server()` | The running `MinecraftServer`, or `None` when no world is running. |
| `is_client()` | `True` inside the game client (also in singleplayer). |
| `SUCCESS`, `CONSUME`, `PASS`, `FAIL` | `InteractionResult` values to return from interaction hooks/events. |
| `JavaException` | The Python type of exceptions thrown by Java code. **Not** a subclass of `Exception`. |
| `ERRORS` | `(Exception, JavaException)` — `except ERRORS:` catches both. |
| `command`, `CommandError` | see [commands](#commands) |
| `text(...)` | see [text](#text) |

---

## events

React to things happening in the game. All handlers are hot-reload safe and errors in them are reported,
never crash the game.

**Return values.** Return `None` (or nothing) to have no opinion. Events that can be cancelled take
`False` (boolean events) or `FAIL` (`InteractionResult` events). For `InteractionResult` events, `True` is
treated as `SUCCESS` and `False` as `FAIL`.

### Shortcuts

| Decorator | Handler signature | Notes |
|---|---|---|
| `@events.on_server_start` | `fn(server)` | server finished starting |
| `@events.on_server_stop` | `fn(server)` | server is stopping |
| `@events.on_tick` | `fn(server)` | end of every server tick (20/s) |
| `@events.on_world_tick` | `fn(level)` | every tick, once per dimension |
| `@events.on_player_join` | `fn(player)` | |
| `@events.on_player_leave` | `fn(player)` | |
| `@events.on_player_respawn` | `fn(old_player, new_player, alive)` | `alive` is True when returning from the End |
| `@events.on_block_break` | `fn(level, player, pos, state, block_entity)` | after a player broke a block |
| `@events.before_block_break` | `fn(level, player, pos, state, block_entity)` | return `False` to cancel |
| `@events.on_use_item` | `fn(player, level, hand)` | right-click with any item; return `SUCCESS`/`FAIL`/`PASS` |
| `@events.on_use_block` | `fn(player, level, hand, hit)` | right-click on a block (`hit.getBlockPos()`) |
| `@events.on_use_entity` | `fn(player, level, hand, entity, hit)` | right-click on an entity |
| `@events.on_attack_entity` | `fn(player, level, hand, entity, hit)` | left-click on an entity |
| `@events.on_attack_block` | `fn(player, level, hand, pos, direction)` | left-click on a block |
| `@events.on_damage` | `fn(entity, source, amount)` | before damage; return `False` to cancel |
| `@events.after_damage` | `fn(entity, source, base_amount, taken, blocked)` | after damage was applied |
| `@events.before_death` | `fn(entity, source, amount)` | return `False` to keep it alive |
| `@events.on_death` | `fn(entity, source)` | any living entity died |
| `@events.on_kill` | `fn(level, killer, victim, source)` | an entity killed another |
| `@events.on_chat` | `fn(player, message: str)` | a chat message was sent |
| `@events.allow_chat` | `fn(player, message: str)` | return `False` to block the message |

`source` is a `DamageSource`: `source.getMsgId()` (`"fall"`, `"player"`, `"lava"`…), `source.getEntity()`
(the attacker or `None`).

### `events.listen(event, fn=None)`

Subscribe to **any** Fabric API event. The handler receives exactly the arguments of the event's Java
listener interface, and its return value is converted to the Java return type.

```python
import java
EntitySleepEvents = java.type("net.fabricmc.fabric.api.entity.event.v1.EntitySleepEvents")

@events.listen(EntitySleepEvents.START_SLEEPING)
def slept(entity, bed_pos):
    ...

# or without decorator
events.listen(EntitySleepEvents.STOP_SLEEPING, lambda entity, pos: None)
```

Fabric's events are documented in the Fabric API javadoc; their listener method signatures are what your
function receives.

---

## registry

New items and blocks must be declared **while the game starts** (at the top level of `main.py`). Their
hooks hot-reload. Item/block textures: `pymods/<mod>/assets/<mod>/textures/item/<id>.png` and
`.../textures/block/<id>.png`.

### `registry.item(...)`

```python
registry.item(id, *, name=None, stack_size=None, durability=None, rarity=None, fireproof=False,
              food=None, tool=None, material="iron", attack_damage=None, attack_speed=None,
              tab="ingredients", texture=None, model=True, tooltip=None, properties=None) -> ItemHandle
```

| Argument | |
|---|---|
| `id` | `"ruby"` (your namespace is added) or `"mymod:ruby"` |
| `name` | English display name; default from the id (`ruby_sword` → "Ruby Sword") |
| `stack_size` | max stack (default 64) |
| `durability` | makes it damageable |
| `rarity` | `"common"`, `"uncommon"`, `"rare"`, `"epic"` (name colour) |
| `fireproof` | survives fire/lava as an item entity |
| `food` | `registry.food(...)` |
| `tool` | `"sword"`, `"pickaxe"`, `"axe"`, `"shovel"`, `"hoe"` |
| `material` | tool tier: `"wood"`, `"stone"`, `"copper"`, `"iron"`, `"gold"`, `"diamond"`, `"netherite"` |
| `attack_damage`, `attack_speed` | override the tool defaults (sword: 3 and -2.4, like vanilla) |
| `tab` | creative tab: `"ingredients"`, `"food_and_drinks"`, `"combat"`, `"tools_and_utilities"`, `"building_blocks"`, `"colored_blocks"`, `"natural_blocks"`, `"functional_blocks"`, `"redstone_blocks"`, `"spawn_eggs"`, `"op_blocks"`, a `creative_tab(...)`, or `None`. Tools and food pick a sensible tab automatically. |
| `texture` | texture id for the generated model, e.g. `"minecraft:item/emerald"` (default `"<mod>:item/<id>"`) |
| `model` | `False` = don't generate a model (you ship `assets/<mod>/items/<id>.json` yourself) |
| `tooltip` | a string or list of strings (colour codes allowed) |
| `properties` | `fn(Item.Properties) -> Item.Properties` for anything else (e.g. `lambda p: p.equippable(...)`) |

**`ItemHandle`**: `.id` (`"mymod:ruby"`), `.item` (the Java `Item`), `.stack(count=1)` → `ItemStack`, plus the
hook decorators below.

### Item hooks

| Decorator | Signature | Return |
|---|---|---|
| `@item.on_use` | `fn(level, player, hand)` | `SUCCESS` / `CONSUME` / `PASS` / `FAIL` |
| `@item.on_use_on_block` | `fn(context)` — `UseOnContext`: `getLevel()`, `getClickedPos()`, `getClickedFace()`, `getPlayer()`, `getItemInHand()` | interaction result |
| `@item.on_use_on_entity` | `fn(stack, player, target, hand)` | interaction result |
| `@item.on_hit` | `fn(stack, target, attacker)` | — |
| `@item.on_mine` | `fn(stack, level, state, pos, miner)` | — |
| `@item.on_inventory_tick` | `fn(stack, level, entity, slot)` (server side, every tick) | — |
| `@item.on_eaten` | `fn(stack, level, entity)` (after finishing eating/drinking) | — |
| `@item.on_crafted` | `fn(stack, player)` | — |
| `@item.tooltip` | `fn(stack)` | `str` or list of `str` / `Component` |
| `@item.glint` | `fn(stack)` | `True` for the enchanted shimmer |

Returning `None` from any hook means "vanilla behaviour".

### `registry.block(...)`

```python
registry.block(id, *, name=None, strength=1.5, resistance=None, sound="stone", light=0, color=None,
               tool="pickaxe", tool_tier=None, requires_tool=False, friction=None, speed=None,
               jump=None, no_collision=False, transparent=False, random_ticks=False, drops="self",
               drop_count=1, texture=None, model=True, item=True, tab="building_blocks",
               properties=None, item_properties=None) -> BlockHandle
```

| Argument | |
|---|---|
| `strength` | hardness: dirt 0.5, stone 1.5, iron block 5, obsidian 50, `-1` unbreakable |
| `resistance` | blast resistance (default = `strength`) |
| `sound` | a `SoundType` name: `"stone"`, `"wood"`, `"metal"`, `"glass"`, `"grass"`, `"gravel"`, `"sand"`, `"wool"`, `"slime_block"`, `"amethyst"`, … |
| `light` | 0–15 |
| `color` | map colour, a `MapColor` name such as `"color_red"`, `"stone"`, `"wood"` |
| `tool` | `"pickaxe"`, `"axe"`, `"shovel"`, `"hoe"` or `None` — the tool that mines it fast (adds the mineable tag) |
| `tool_tier` | `"stone"`, `"iron"`, `"diamond"` — minimum tier (use with `requires_tool=True`) |
| `requires_tool` | only drops when mined with the correct tool |
| `friction` / `speed` / `jump` | ice is `friction=0.98`, soul sand `speed=0.4`, honey `jump=0.5` |
| `no_collision` | entities pass through (use with `on_entity_inside`) |
| `transparent` | doesn't hide the faces of neighbours |
| `random_ticks` | receives random ticks (also enabled automatically by an `on_random_tick` hook) |
| `drops` | `"self"`, another item id (ore style: Silk Touch gives the block, Fortune works), or `None` |
| `drop_count` | `int` or `(min, max)` when `drops` is another item |
| `texture` | texture id, or `{"end": ..., "side": ...}` (pillar) or `{"up":..,"down":..,"north":..,"south":..,"east":..,"west":..}` |
| `item` | `False` = no block item |
| `tab` | creative tab of the block item |
| `properties` / `item_properties` | functions receiving the Java `Properties` objects for anything else |

**`BlockHandle`**: `.id`, `.block` (Java `Block`), `.item` (its `BlockItem` or `None`), `.state()` (default
`BlockState`), `.stack(count=1)`, plus the hooks below.

### Block hooks

| Decorator | Signature | Notes |
|---|---|---|
| `@block.on_use` | `fn(state, level, pos, player, hit)` | right-click with an empty hand → interaction result |
| `@block.on_use_with_item` | `fn(stack, state, level, pos, player, hand, hit)` | right-click holding an item |
| `@block.on_punch` | `fn(state, level, pos, player)` | left-click |
| `@block.on_step` | `fn(level, pos, state, entity)` | an entity walks on it (any entity: check the type) |
| `@block.on_fall` | `fn(level, state, pos, entity, distance)` | landed on it; return `True` to cancel fall damage |
| `@block.on_entity_inside` | `fn(state, level, pos, entity)` | entity inside the block space |
| `@block.on_place` | `fn(level, pos, state, placer, stack)` | placed by an entity |
| `@block.on_break` | `fn(level, pos, state, player)` | a player is breaking it |
| `@block.on_explode` | `fn(level, pos, explosion)` | destroyed by an explosion |
| `@block.on_random_tick` | `fn(state, level, pos, random)` | like crop growth |
| `@block.on_scheduled_tick` | `fn(state, level, pos, random)` | after `level.scheduleTick(pos, block.block, delay)` |
| `@block.on_animate_tick` | `fn(state, level, pos, random)` | client side, for particles |
| `@block.on_neighbor_change` | `fn(state, level, pos, neighbor_block)` | |
| `@block.on_projectile_hit` | `fn(level, state, hit, projectile)` | |
| `@block.redstone_power` | `fn(state, level, pos, direction)` → 0–15 | makes the block a redstone source |

### Food

```python
registry.food(nutrition=4, saturation=0.3, *, always_edible=False, effects=(), eat_seconds=1.6, drink=False)
registry.effect(id, seconds=10, amplifier=0, chance=1.0)
```

A steak is `nutrition=8, saturation=0.8`. `effects` is a list of `registry.effect(...)`; effect ids are
`"speed"`, `"regeneration"`, `"night_vision"`… (`minecraft:` optional). `drink=True` uses the drinking
animation.

### Creative tabs

```python
TAB = registry.creative_tab("rubies", title="Ruby Gear", icon="ruby")
registry.item("ruby", tab=TAB)
```

`registry.get("mymod:ruby")` returns the handle of any item/block declared by a Python mod
(`KeyError` if none) — handy for optional cross-mod content.

---

## recipes

All functions return the recipe id. Ingredients: an id, a tag (`"#minecraft:planks"`), a handle, or a list
of alternatives (`["minecraft:coal", "minecraft:charcoal"]`). The default recipe id is the result's name
(plus `_from_smelting` etc.); pass `id="..."` to choose your own. Recipes hot-reload.

| | |
|---|---|
| `recipes.shaped(result, pattern, key=None, *, count=1, id=None, category="misc", group=None, **symbols)` | `pattern`: up to 3 strings; symbols as keywords `R="ruby"` or `key={"R": "ruby"}` |
| `recipes.shapeless(result, ingredients, *, count=1, id=None, category="misc", group=None)` | up to 9 ingredients |
| `recipes.smelting(result, ingredient, *, xp=0.1, time=200, id=None, category="misc", count=1, blasting=False, smoking=False, campfire=False)` | furnace; optional blast furnace / smoker / campfire versions |
| `recipes.stonecutting(result, ingredient, *, count=1, id=None)` | |
| `recipes.raw(recipe_id, body)` | any recipe JSON as a dict (smithing, custom types from other mods…) |

`category` for crafting: `"building"`, `"redstone"`, `"equipment"`, `"misc"`; for cooking: `"food"`,
`"blocks"`, `"misc"`.

---

## resources

PyFabric merges everything into two always-enabled packs: shipped files (`pymods/<mod>/assets/...` and
`pymods/<mod>/data/...`, copied as-is) and generated files. A file you ship always wins over a generated one.

| | |
|---|---|
| `resources.lang(key, value, language="en_us")` | add a translation |
| `resources.tag(registry, tag_id, *values)` | add to a tag: `tag("block", "minecraft:mineable/axe", "my_log")`. `registry` is `"block"`, `"item"`, `"entity_type"`, `"fluid"`, … |
| `resources.data(path, content)` | any data-pack file; `path` relative to `data/`, e.g. `"mymod/advancement/x.json"`; `content` is a dict (JSON), `str` or `bytes` |
| `resources.asset(path, content)` | any resource-pack file, relative to `assets/` |
| `resources.item_model(item_id, texture=None, parent="minecraft:item/generated")` | (used by `registry.item`) |
| `resources.block_model(block_id, texture=None, model=None)` | (used by `registry.block`) |
| `resources.block_drops(block_id, item_id=None, count=1, silk_touch=True, fortune=True)` | block loot table |

The generated packs live in `.minecraft/pyfabric/generated/` — look there to see exactly what was produced.

---

## worldgen

```python
worldgen.ore(block, *, deepslate_block=None, size=6, per_chunk=8, min_y=-64, max_y=64,
             spread="uniform", dimension="overworld", replaces=("stone",), id=None)
```

Generates ore veins in **newly generated chunks**. `spread="triangle"` concentrates veins in the middle of
the height range. `replaces`: `"stone"`, `"deepslate"`, `"netherrack"`, `"end_stone"`. `dimension`:
`"overworld"`, `"nether"`, `"end"`. Must be called at startup (new ores after a reload need a restart).

---

## commands

```python
@command(signature, *, permission=0, aliases=())
def handler(ctx, **arguments): ...
```

**Signature** — words are literal (sub-)commands; `<name:type>` required arguments; `[name:type=default]`
optional ones, which must come last. Several commands may share a first word (`"home set"`, `"home tp"`).

| Type | Python value | Example input |
|---|---|---|
| `int`, `int(min,max)` | `int` | `5` |
| `float`, `float(min,max)` | `float` | `2.5` |
| `bool` | `bool` | `true` |
| `word` (default) | `str` | `hello` |
| `string` | `str` | `"two words"` |
| `text` | `str` (rest of the line) | `anything at all` |
| `player` / `players` | `ServerPlayer` / list | `Steve`, `@a` |
| `entity` / `entities` | `Entity` / list | `@e[type=pig]` |
| `pos` | `BlockPos` | `~ ~1 ~`, `10 64 -3` |
| `vec3` | `Vec3` | `~ ~ ~` |
| `item` | `ItemInput` (`.createItemStack(count)`) | `diamond_sword` |
| `block` | `BlockState` | `stone`, `oak_log[axis=x]` |

**`permission`**: 0 everyone, 1 moderators, 2 operators (like `/gamemode`), 3 admins, 4 owner.
**`aliases`**: extra names for the first word.

**`ctx`** (`commands.Context`):

| | |
|---|---|
| `ctx.reply(message, broadcast=False)` | feedback to the sender (`broadcast=True` also tells other ops, like vanilla) |
| `ctx.error(message)` | red message |
| `ctx.player` | the player who ran it, or `None` (console, command block) |
| `ctx.require_player()` | the player, or a red "only players" error |
| `ctx.entity`, `ctx.server`, `ctx.level` (= `ctx.world`), `ctx.position` (`Vec3`), `ctx.name` | |
| `ctx.source`, `ctx.raw` | the Java `CommandSourceStack` and `CommandContext` |

`raise CommandError("message")` stops the command with a red message. Return an `int` to set the command
result (for `/execute store`), default 1.

---

## scheduler

20 ticks = 1 second. Tasks run on the server thread and are cancelled by `/pyfabric reload`.
(A dedicated server with nobody online pauses ticking after a minute; tasks wait until it resumes.)

| | |
|---|---|
| `scheduler.after(ticks=None, fn=None, *, seconds=None)` | run `fn(server)` once. As a decorator: `@scheduler.after(seconds=5)` |
| `scheduler.every(ticks=None, fn=None, *, seconds=None, delay=None)` | repeat. As a decorator the function gets a `.task` attribute; called with `fn=` it returns the `Task` |
| `task.cancel()` | stop a task |
| `scheduler.tasks()` | active tasks |
| `scheduler.current_tick()` | ticks counted since start |

---

## players

| | |
|---|---|
| `players.online()` | list of online `ServerPlayer`s |
| `players.get(name)` | online player by name or `None` |
| `players.name(entity)` | display name as `str` |
| `players.tell(player, message)` | chat message to one player |
| `players.actionbar(player, message)` | text above the hotbar |
| `players.title(player, title, subtitle=None, fade_in=10, stay=60, fade_out=20)` | big title (ticks) |
| `players.broadcast(message)` | chat message to everyone |
| `players.give(player, item, count=1)` | give items (an id or an `ItemStack`); drops the rest if full |
| `players.held(player)` | `ItemStack` in the main hand |
| `players.heal(entity, amount=None)` | heal by `amount` half-hearts, or fully |
| `players.feed(player, food=20, saturation=5.0)` | |
| `players.effect(entity, effect_id, seconds=10, amplifier=0, particles=True)` | potion effect |
| `players.clear_effects(entity)` | |
| `players.teleport(entity, x, y=None, z=None, level=None)` | to coordinates, a `BlockPos` or another entity; optionally another dimension |
| `players.set_flying(player, allowed=True)` | creative-style flight |
| `players.gamemode(player, mode)` | `"survival"`, `"creative"`, `"adventure"`, `"spectator"` |
| `players.is_op(player)` | |
| `players.looking_at(player, distance=5.0)` | `BlockPos` the player looks at, or `None` |
| `players.server()` | same as `pyfabric.server()` |

Everything on the Java `ServerPlayer` is available too: `player.getHealth()`, `player.getInventory()`,
`player.blockPosition()`, `player.isShiftKeyDown()`, `player.getUUID()`, …

---

## world

| | |
|---|---|
| `world.set_block(level, pos, block)` | block id, handle, `Block` or `BlockState` |
| `world.get_block(level, pos)` | block id at a position, e.g. `"minecraft:stone"` |
| `world.break_block(level, pos, drop=True, breaker=None)` | |
| `world.spawn(level, entity_type, pos)` | spawn e.g. `"minecraft:zombie"`; returns the entity |
| `world.drop_item(level, pos, item, count=1)` | item entity |
| `world.sound(level, pos, sound_id, volume=1.0, pitch=1.0, category="blocks")` | `sound_id` like `"minecraft:block.note_block.bell"` |
| `world.particles(level, particle_id, pos, count=8, spread=0.5, speed=0.0)` | simple particles like `"minecraft:heart"`, `"minecraft:flame"` |
| `world.explode(level, pos, power=3.0, fire=False, breaks_blocks=True, source=None)` | TNT is 4 |
| `world.lightning(level, pos, visual_only=False)` | |
| `world.entities_near(level, pos, radius, entity_class=None)` | living entities in range; pass a class such as `mc.Player` to filter |
| `world.run_command(command, as_player=None)` | run a vanilla command as the console or a player |
| `world.time_of_day(level)` | 0–23999 |
| `world.is_night(level)` | |
| `world.dimension(level)` | `"minecraft:overworld"`, … |

Running a command *from inside another command* (including `/pyfabric run`) queues it until the outer
command finishes — that's how Minecraft's command system works.

---

## storage

| | |
|---|---|
| `storage.config(defaults=None, name=None)` | loads `config/pymods/<mod>.json`, adds missing defaults and saves. Returns a dict-like `Store` |
| `storage.world_data(name=None)` | dict saved in `<world>/pyfabric/<mod>.json`, written automatically when the world saves. Only while a world is running (call it inside handlers) |
| `store.save()` | write now |
| `storage.save_all()` | save every world store now |

Values must be JSON compatible.

---

## text

```python
from pyfabric import text
from pyfabric.text import as_component, plain, translatable
```

| | |
|---|---|
| `text(*parts, color=None, bold=False, italic=False, underline=False, strikethrough=False, obfuscated=False)` | build a `Component` from strings and components. `color`: a name (`"gold"`, `"dark_aqua"`, …) or `"#ff8800"` |
| `as_component(x)` | strings → `text(x)`, components unchanged |
| `plain(component)` | `Component` → `str` |
| `translatable(key, *args)` | a translated message |

Strings anywhere in PyFabric understand `&` colour codes: `&0`–`&9`, `&a`–`&f` colours, `&l` bold,
`&o` italic, `&n` underline, `&m` strikethrough, `&k` obfuscated, `&r` reset.

---

## mc

Shortcuts to Minecraft classes (`mc.Items`, `mc.Blocks`, `mc.ItemStack`, `mc.BlockPos`, `mc.Vec3`, `mc.AABB`,
`mc.Direction`, `mc.Component`, `mc.ChatFormatting`, `mc.EntityType`, `mc.EntityTypes` (the constants:
`mc.EntityTypes.PIG`), `mc.Entity`, `mc.LivingEntity`, `mc.Player`, `mc.ServerPlayer`, `mc.Level`,
`mc.ServerLevel`, `mc.MobEffects`, `mc.MobEffectInstance`, `mc.SoundEvents`, `mc.SoundSource`,
`mc.ParticleTypes`, `mc.GameType`, `mc.EquipmentSlot`, `mc.InteractionHand`, `mc.InteractionResult`,
`mc.Identifier`, `mc.ResourceKey`, `mc.BuiltInRegistries`, `mc.Registries`, `mc.SoundType`, `mc.MapColor`,
`mc.DataComponents`, `mc.TagKey`, `mc.BlockTags`, `mc.ItemTags`, …) and lookups:

| | |
|---|---|
| `mc.item(id)` / `mc.block(id)` / `mc.state(id)` | Java `Item` / `Block` / default `BlockState` |
| `mc.stack(id, count=1)` | `ItemStack` |
| `mc.entity_type(id)`, `mc.effect(id)`, `mc.sound(id)`, `mc.particle(id)` | registry lookups (`KeyError` if unknown) |
| `mc.id_of(obj)` | id string of an `Item`, `Block`, `EntityType`, `ItemStack`, `BlockState` or `Entity` |
| `mc.ident("ns:path")` | `Identifier` |
| `mc.pos(x, y=None, z=None)` | `BlockPos` from numbers, a tuple, a `Vec3` or an entity |
| `mc.tag_key(registry, tag_id)` | `TagKey`, e.g. `mc.tag_key("block", "minecraft:logs")` |
| `mc.has_tag(obj, tag)` | `mc.has_tag(state, "minecraft:logs")`, works for block states, item stacks, items, blocks and entities. Tags load with the world: use it in handlers, not at the top level of `main.py` |
| `mc.is_(obj, x)` | Java's `obj.is(x)` (`is` is a Python keyword) |

---

## client

Only importable on the client — use it from `client.py`.

| | |
|---|---|
| `@client.on_key(description, key, category="misc")` | `fn(minecraft)` when the key is pressed. `key`: `"H"`, `"7"` or a name like `"key.keyboard.f6"`. Rebindable in Options → Controls. New keys need a restart. |
| `@client.hud` | `fn(graphics, minecraft)` every frame |
| `@client.on_tick` | `fn(minecraft)` every client tick |
| `client.draw_text(graphics, text, x, y, color=0xFFFFFF, shadow=True)` | |
| `client.fill(graphics, x1, y1, x2, y2, color=0x80000000)` | ARGB rectangle |
| `client.text_width(text)` | pixels |
| `client.tell(message)` / `client.actionbar(message)` | local-only messages |
| `client.minecraft()` | the `Minecraft` instance: `.player`, `.level`, `.options`, `.getFps()`, … |

`graphics` is Minecraft's `GuiGraphicsExtractor` — all its drawing methods are available directly.

---

## Hot reload rules

`/pyfabric reload`:

1. switches off every event handler, hook, command and scheduled task of Python mods,
2. forgets all `pymods.*` Python modules and runs every mod's `main.py` (and `client.py` on clients) again,
3. rebuilds the generated packs and reloads data (like `/reload`) so recipes, loot tables and tags update,
4. re-sends the command list to players.

Handlers that your new code registers again are switched back on (with the new code); ones it no longer
registers stay off. **Restart** the game for: new items/blocks/creative tabs/ores/key bindings, and
texture/model changes (or press `F3`+`T` on the client).

Module-level state (dicts, counters) starts fresh on reload — keep anything that must survive in
`storage.world_data()`.
