"""Ruby Gear - a complete "new material" content mod.

Shows: items, blocks, an ore that drops gems and generates in the world, a sword and pickaxe,
food with potion effects, crafting/smelting recipes, a creative tab, tags and item hooks.

Textures live in assets/ruby_gear/textures/{item,block}/<name>.png - models, translations and
loot tables are generated automatically from the declarations below.
"""
from pyfabric import mc, players, recipes, registry, resources, world, worldgen

# A creative tab of our own. Everything with tab=TAB shows up in it.
TAB = registry.creative_tab("rubies", title="Ruby Gear", icon="ruby")

# ---- items -----------------------------------------------------------------------------------------------
ruby = registry.item("ruby", rarity="uncommon", tab=TAB)

ruby_sword = registry.item("ruby_sword", tool="sword", material="diamond", attack_damage=4, tab=TAB,
                           tooltip="Burns whatever it hits")
ruby_pickaxe = registry.item("ruby_pickaxe", tool="pickaxe", material="diamond", tab=TAB,
                             tooltip=["Mines a bit faster than diamond", "&7(it doesn't, it's just pretty)"])

ruby_apple = registry.item("ruby_apple", rarity="rare", tab=TAB, food=registry.food(
    nutrition=6, saturation=1.0, always_edible=True,
    effects=[registry.effect("regeneration", seconds=8, amplifier=1),
             registry.effect("fire_resistance", seconds=60)]))

# ---- blocks ----------------------------------------------------------------------------------------------
ruby_block = registry.block("ruby_block", strength=5, sound="metal", color="color_red",
                            tool="pickaxe", tool_tier="iron", requires_tool=True, tab=TAB)

ruby_ore = registry.block("ruby_ore", strength=3, sound="stone", tool="pickaxe", tool_tier="iron",
                          requires_tool=True, drops="ruby", drop_count=(1, 2), tab=TAB)

# Generate ruby ore underground in the overworld (new chunks only).
worldgen.ore("ruby_ore", size=5, per_chunk=6, min_y=-48, max_y=24, spread="triangle")

# ---- behaviour -------------------------------------------------------------------------------------------
@ruby_sword.on_hit
def ignite(stack, target, attacker):
    target.igniteForSeconds(4.0)


@ruby_apple.glint
def shiny(stack):
    return True                           # enchanted-looking shimmer


@ruby_apple.on_eaten
def ate(stack, level, entity):
    if not level.isClientSide():
        world.particles(level, "minecraft:heart", entity, count=6)


@ruby_block.on_use
def ring(state, level, pos, player, hit):
    """Right-click a ruby block: it chimes."""
    if not level.isClientSide():
        world.sound(level, pos, "minecraft:block.amethyst_block.chime", volume=1.0, pitch=0.8)
    return mc.SUCCESS


# ---- recipes ----------------------------------------------------------------------------------------------
recipes.shaped("ruby_block", ["RRR", "RRR", "RRR"], R="ruby")
recipes.shapeless("ruby", ["ruby_block"], count=9)
recipes.smelting("ruby", "ruby_ore", xp=1.0, blasting=True)
recipes.shaped("ruby_sword", [" R ", " R ", " S "], R="ruby", S="minecraft:stick", category="equipment")
recipes.shaped("ruby_pickaxe", ["RRR", " S ", " S "], R="ruby", S="minecraft:stick", category="equipment")
recipes.shaped("ruby_apple", ["RRR", "RAR", "RRR"], R="ruby", A="minecraft:apple")

# ---- tags --------------------------------------------------------------------------------------------------
resources.tag("item", "minecraft:piglin_loved", "ruby", "ruby_block")      # piglins go crazy for rubies
resources.tag("block", "minecraft:beacon_base_blocks", "ruby_block")        # works as a beacon base
