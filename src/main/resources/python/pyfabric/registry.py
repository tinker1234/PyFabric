"""Adding new items, blocks and creative tabs.

    ruby = registry.item("ruby", rarity="rare")
    ruby_block = registry.block("ruby_block", strength=5, sound="metal", tool="pickaxe")

    @ruby.on_use
    def use(level, player, hand):
        ...
        return mc.SUCCESS

New items/blocks must be declared while the game starts (in ``main.py`` at import time). Their
*behaviour* (hooks such as ``on_use``) is hot-reloadable with ``/pyfabric reload``.

Textures: put PNGs at ``pymods/<mod>/assets/<mod>/textures/item/<id>.png`` (items) or
``.../textures/block/<id>.png`` (blocks), or reuse a vanilla one with ``texture="minecraft:item/emerald"``.
Models, item definitions, translations and block loot tables are generated for you.
"""
import java

from . import _core, mc, resources

_t = java.type
ItemProperties = _t("net.minecraft.world.item.Item$Properties")
BlockProperties = _t("net.minecraft.world.level.block.state.BlockBehaviour$Properties")
Rarity = _t("net.minecraft.world.item.Rarity")
ToolMaterial = _t("net.minecraft.world.item.ToolMaterial")
FoodPropertiesBuilder = _t("net.minecraft.world.food.FoodProperties$Builder")
Consumables = _t("net.minecraft.world.item.component.Consumables")
ApplyEffects = _t("net.minecraft.world.item.consume_effects.ApplyStatusEffectsConsumeEffect")
CreativeModeTabs = _t("net.minecraft.world.item.CreativeModeTabs")
CreativeModeTabEvents = _t("net.fabricmc.fabric.api.creativetab.v1.CreativeModeTabEvents")
FabricCreativeModeTab = _t("net.fabricmc.fabric.api.creativetab.v1.FabricCreativeModeTab")

_declared = {}        # id -> handle, rebuilt on every (re)load
_vanilla_tabs = {}    # tab name -> [item ids]
_custom_tabs = {}     # id -> CreativeTab (registered once, kept across reloads)
_tab_listeners = set()


@_core.on_reset
def _reset():
    _declared.clear()
    _core.declared.clear()
    for items in _vanilla_tabs.values():
        items.clear()
    for tab in _custom_tabs.values():
        tab.items.clear()


def declared_ids():
    return set(_declared)


def get(id):
    """Handle of an item/block declared by a Python mod ('mymod:ruby')."""
    return _declared[_core.namespaced(id)]


def _title(path):
    return path.replace("_", " ").title()


def _hook(name, doc):
    def decorator_factory(self):
        def decorator(fn):
            owner = _core.owner()
            self._java.hooks.set(name, _core.guard(owner, f"{self.id} hook {name} -> {_core.fn_name(fn)}()", fn), owner)
            return fn
        return decorator
    decorator_factory.__doc__ = doc
    return property(decorator_factory)


# ==== food ================================================================================================

def effect(id, seconds=10, amplifier=0, chance=1.0):
    """A potion effect for food: effect('speed', seconds=30, amplifier=1)."""
    return {"id": id, "seconds": seconds, "amplifier": amplifier, "chance": chance}


def food(nutrition=4, saturation=0.3, *, always_edible=False, effects=(), eat_seconds=1.6, drink=False):
    """Food properties for ``registry.item(..., food=food(...))``.

    nutrition: hunger points restored (a steak is 8); saturation: modifier (steak is 0.8).
    """
    return {"nutrition": nutrition, "saturation": saturation, "always_edible": always_edible,
            "effects": list(effects), "eat_seconds": eat_seconds, "drink": drink}


def _apply_food(props, f):
    b = FoodPropertiesBuilder().nutrition(int(f["nutrition"])).saturationModifier(float(f["saturation"]))
    if f.get("always_edible"):
        b = b.alwaysEdible()
    consumable = (Consumables.defaultDrink() if f.get("drink") else Consumables.defaultFood())
    consumable = consumable.consumeSeconds(float(f.get("eat_seconds", 1.6)))
    for e in f.get("effects", ()):
        e = e if isinstance(e, dict) else effect(*e)
        instance = mc.MobEffectInstance(mc.effect(e["id"]), int(e["seconds"] * 20), int(e["amplifier"]))
        consumable = consumable.onConsume(ApplyEffects(instance, float(e["chance"])))
    return props.food(b.build(), consumable.build())


# ==== items ===============================================================================================

_TOOL_DEFAULTS = {  # attack damage bonus, attack speed (like vanilla iron tools)
    "sword": (3.0, -2.4), "pickaxe": (1.0, -2.8), "axe": (6.0, -3.1), "shovel": (1.5, -3.0), "hoe": (0.0, -1.0),
}


class ItemHandle:
    """A Python-made item. ``.item`` is the Java Item, ``.id`` its 'namespace:path' id."""

    def __init__(self, id, java_item):
        self.id = id
        self.item = java_item
        self._java = java_item

    def stack(self, count=1):
        """A new ItemStack of this item."""
        return mc.ItemStack(self.item, int(count))

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"<item {self.id}>"

    on_use = _hook("use", "@on_use: fn(level, player, hand) - right click in the air. Return mc.SUCCESS / mc.PASS / mc.FAIL.")
    on_use_on_block = _hook("use_on_block", "@on_use_on_block: fn(context) - right click on a block (UseOnContext: getLevel(), getClickedPos(), getPlayer()...).")
    on_use_on_entity = _hook("use_on_entity", "@on_use_on_entity: fn(stack, player, target, hand) - right click on a mob.")
    on_hit = _hook("hit_entity", "@on_hit: fn(stack, target, attacker) - hit a mob with this item.")
    on_mine = _hook("mine_block", "@on_mine: fn(stack, level, state, pos, miner) - a block was mined with this item.")
    on_inventory_tick = _hook("inventory_tick", "@on_inventory_tick: fn(stack, level, entity, slot) - every tick while in an inventory (server side).")
    on_eaten = _hook("finish_using", "@on_eaten: fn(stack, level, entity) - finished eating/drinking/using.")
    on_crafted = _hook("crafted", "@on_crafted: fn(stack, player) - the item was crafted.")
    tooltip = _hook("tooltip", "@tooltip: fn(stack) -> str | [str | Component] - extra tooltip lines.")
    glint = _hook("glint", "@glint: fn(stack) -> bool - show the enchantment shimmer.")


def item(id, *, name=None, stack_size=None, durability=None, rarity=None, fireproof=False, food=None,
         tool=None, material="iron", attack_damage=None, attack_speed=None, tab="ingredients",
         texture=None, model=True, tooltip=None, properties=None):
    """Declare a new item.

    id          'ruby' (your mod's namespace is added) or 'mymod:ruby'
    name        display name (default: from the id, 'ruby_sword' -> 'Ruby Sword')
    stack_size  max stack size (default 64, or 1 for tools / items with durability)
    durability  makes the item damageable with this many uses
    rarity      'common' | 'uncommon' | 'rare' | 'epic' (name colour)
    fireproof   survives fire and lava like netherite
    food        registry.food(...) to make it edible
    tool        'sword' | 'pickaxe' | 'axe' | 'shovel' | 'hoe' with material='wood'|'stone'|'iron'|'gold'|'diamond'|'netherite'
    tab         creative tab: 'ingredients', 'food_and_drinks', 'combat', 'tools_and_utilities', ... a
                registry.creative_tab(...) or None
    texture     texture id for the generated model (default '<mod>:item/<id>')
    model       False to skip generating a model (when you ship your own)
    tooltip     a string or list of strings shown under the name
    properties  fn(Item.Properties) -> Item.Properties for anything not covered here
    """
    full = _core.namespaced(id)
    ns, path = full.split(":", 1)
    reloading = bool(_core.Bridge.exists("item", full))     # hot reload: item already exists, reuse it
    props = ItemProperties()
    if tool and reloading:
        if tab == "ingredients":
            tab = "combat" if tool == "sword" else "tools_and_utilities"
    elif tool:
        mat = getattr(ToolMaterial, material.upper())
        dmg, spd = _TOOL_DEFAULTS[tool]
        dmg = dmg if attack_damage is None else attack_damage
        spd = spd if attack_speed is None else attack_speed
        props = getattr(props, tool)(mat, float(dmg), float(spd))
        if tab == "ingredients":
            tab = "combat" if tool == "sword" else "tools_and_utilities"
    if stack_size is not None:
        props = props.stacksTo(int(stack_size))
    if durability is not None:
        props = props.durability(int(durability))
    if rarity:
        props = props.rarity(Rarity.valueOf(rarity.upper()))
    if fireproof:
        props = props.fireResistant()
    if food is not None:
        if not reloading:
            props = _apply_food(props, food)
        if tab == "ingredients":
            tab = "food_and_drinks"
    if properties is not None and not reloading:
        props = properties(props)

    handle = ItemHandle(full, _core.Bridge.registerItem(full, props))
    _declared[full] = handle
    _core.declared.add(full)

    resources.lang(f"item.{ns}.{path}", name or _title(path))
    if model:
        resources.item_model(full, texture, "minecraft:item/handheld" if tool else "minecraft:item/generated")
    if tooltip is not None:
        lines = [tooltip] if isinstance(tooltip, str) else list(tooltip)
        handle.tooltip(lambda stack: lines)
    _add_to_tab(tab, full)
    return handle


# ==== blocks ==============================================================================================

class BlockHandle:
    """A Python-made block. ``.block`` is the Java Block, ``.item`` its BlockItem (or None)."""

    def __init__(self, id, java_block, java_item):
        self.id = id
        self.block = java_block
        self.item = java_item
        self._java = java_block

    def state(self):
        """Default BlockState (for level.setBlockAndUpdate)."""
        return self.block.defaultBlockState()

    def stack(self, count=1):
        return mc.ItemStack(self.item, int(count))

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"<block {self.id}>"

    on_use = _hook("use", "@on_use: fn(state, level, pos, player, hit) - right click with an empty hand. Return mc.SUCCESS / mc.PASS.")
    on_use_with_item = _hook("use_with_item", "@on_use_with_item: fn(stack, state, level, pos, player, hand, hit) - right click holding an item.")
    on_punch = _hook("punched", "@on_punch: fn(state, level, pos, player) - left click.")
    on_step = _hook("stepped_on", "@on_step: fn(level, pos, state, entity) - an entity walks on the block.")
    on_fall = _hook("fallen_on", "@on_fall: fn(level, state, pos, entity, distance) - landed on it. Return True to cancel fall damage.")
    on_entity_inside = _hook("entity_inside", "@on_entity_inside: fn(state, level, pos, entity) - an entity is inside (use with no_collision=True).")
    on_place = _hook("placed", "@on_place: fn(level, pos, state, placer, stack) - placed by an entity.")
    on_break = _hook("broken", "@on_break: fn(level, pos, state, player) - a player is breaking it.")
    on_explode = _hook("exploded", "@on_explode: fn(level, pos, explosion) - destroyed by an explosion.")
    on_random_tick = _hook("random_tick", "@on_random_tick: fn(state, level, pos, random) - random ticks (like crop growth).")
    on_scheduled_tick = _hook("scheduled_tick", "@on_scheduled_tick: fn(state, level, pos, random) - after level.scheduleTick(pos, block, delay).")
    on_animate_tick = _hook("animate_tick", "@on_animate_tick: fn(state, level, pos, random) - client side, for particles.")
    on_neighbor_change = _hook("neighbor_changed", "@on_neighbor_change: fn(state, level, pos, neighbor_block) - a neighbouring block changed.")
    on_projectile_hit = _hook("projectile_hit", "@on_projectile_hit: fn(level, state, hit, projectile).")
    redstone_power = _hook("redstone_power", "@redstone_power: fn(state, level, pos, direction) -> 0..15 - emit redstone power.")


_TIER_TAGS = {"stone": "minecraft:needs_stone_tool", "iron": "minecraft:needs_iron_tool",
              "diamond": "minecraft:needs_diamond_tool"}


def block(id, *, name=None, strength=1.5, resistance=None, sound="stone", light=0, color=None,
          tool="pickaxe", tool_tier=None, requires_tool=False, friction=None, speed=None, jump=None,
          no_collision=False, transparent=False, random_ticks=False, drops="self", drop_count=1,
          texture=None, model=True, item=True, tab="building_blocks", properties=None, item_properties=None):
    """Declare a new block (and its item).

    strength      hardness (stone 1.5, iron block 5, obsidian 50); -1 = unbreakable
    resistance    blast resistance (default = strength)
    sound         'stone' | 'wood' | 'metal' | 'glass' | 'grass' | 'sand' | 'wool' | 'amethyst' | ... (SoundType names)
    light         light level 0-15
    tool          'pickaxe' | 'axe' | 'shovel' | 'hoe' | None - which tool mines it fast
    tool_tier     'stone' | 'iron' | 'diamond' - minimum tool tier (with requires_tool=True)
    requires_tool only drops when mined with the right tool (like stone and ores)
    friction / speed / jump   ice is friction=0.98, soul sand speed=0.4, honey jump=0.5
    no_collision  entities walk through it (use with on_entity_inside)
    drops         'self', an item id (e.g. 'mymod:ruby' for ores) or None
    drop_count    int or (min, max) when ``drops`` is another item
    texture       texture id, or a dict like {'end': ..., 'side': ...} (column) / {'up','down','north',...}
    tab           creative tab for the block item
    properties    fn(BlockBehaviour.Properties) -> Properties for anything not covered here
    """
    full = _core.namespaced(id)
    ns, path = full.split(":", 1)
    p = BlockProperties.of()
    if _core.Bridge.exists("block", full):        # hot reload: reuse the existing block
        pass
    elif strength is not None:
        p = p.strength(float(strength), float(strength if resistance is None else resistance))
    if sound:
        p = p.sound(getattr(mc.SoundType, sound.upper()))
    if light:
        p = p.lightLevel(_core.Bridge.constantLight(int(light)))
    if color:
        p = p.mapColor(getattr(mc.MapColor, color.upper()))
    if requires_tool:
        p = p.requiresCorrectToolForDrops()
    if friction is not None:
        p = p.friction(float(friction))
    if speed is not None:
        p = p.speedFactor(float(speed))
    if jump is not None:
        p = p.jumpFactor(float(jump))
    if no_collision:
        p = p.noCollision()
    if transparent:
        p = p.noOcclusion()
    if random_ticks:
        p = p.randomTicks()
    if drops is None:
        p = p.noLootTable()
    if properties is not None and not _core.Bridge.exists("block", full):
        p = properties(p)

    java_block = _core.Bridge.registerBlock(full, p)
    java_item = None
    if item:
        ip = ItemProperties()
        if item_properties is not None:
            ip = item_properties(ip)
        java_item = _core.Bridge.registerBlockItem(full, java_block, ip)

    handle = BlockHandle(full, java_block, java_item)
    _declared[full] = handle
    _core.declared.add(full)

    resources.lang(f"block.{ns}.{path}", name or _title(path))
    if model:
        resources.block_model(full, texture)
    if drops == "self":
        resources.block_drops(full)
    elif drops:
        resources.block_drops(full, _core.resolve(drops, ns), drop_count)
    if tool:
        resources.tag("block", f"minecraft:mineable/{tool}", full)
    if tool_tier:
        resources.tag("block", _TIER_TAGS[tool_tier], full)
    if item:
        _add_to_tab(tab, full)
    return handle


# ==== creative tabs ========================================================================================

class CreativeTab:
    def __init__(self, id, title, icon):
        self.id = id
        self.title = title
        self.icon = icon
        self.items = []

    def __repr__(self):
        return f"<creative tab {self.id}: {len(self.items)} items>"


def creative_tab(id, *, title=None, icon=None):
    """A new creative inventory tab. Pass it as ``tab=`` to item()/block(). ``icon`` is an item id."""
    full = _core.namespaced(id)
    if full in _custom_tabs:                  # hot reload: keep the registered tab
        tab = _custom_tabs[full]
        tab.icon = icon or tab.icon
        return tab
    tab = CreativeTab(full, title or _title(full.split(":", 1)[1]), icon)

    def make_icon():
        try:
            return mc.stack(_core.resolve(tab.icon, tab.id.split(":")[0]) if tab.icon else (tab.items[0] if tab.items else "minecraft:book"))
        except _core.ERRORS:
            return mc.stack("minecraft:barrier")

    def display(params, output):
        for item_id in tab.items:
            output.accept(mc.item(item_id))

    built = (FabricCreativeModeTab.builder()
             .title(mc.Component.literal(tab.title))
             .icon(make_icon)
             .displayItems(display)
             .build())
    mc.Registry.register(mc.BuiltInRegistries.CREATIVE_MODE_TAB, mc.Identifier.parse(full), built)
    _custom_tabs[full] = tab
    return tab


def _add_to_tab(tab, item_id):
    if tab is None:
        return
    if isinstance(tab, CreativeTab):
        if item_id not in tab.items:
            tab.items.append(item_id)
        return
    name = str(tab).lower()
    items = _vanilla_tabs.setdefault(name, [])
    if item_id not in items:
        items.append(item_id)
    if name in _tab_listeners:
        return
    key = getattr(CreativeModeTabs, name.upper(), None)
    if key is None:
        raise ValueError(f"Unknown creative tab '{tab}'")

    def add_items(output):
        for i in items:
            output.accept(mc.item(i))

    _core.Bridge.listen(CreativeModeTabEvents.modifyOutputEvent(key), f"pyfabric|core|tab|{name}", "pyfabric", add_items)
    _tab_listeners.add(name)
