"""Magic Wands - items that do things when you right-click.

Shows: item use hooks, cooldowns, raycasts, spawning projectiles, lightning, teleporting,
area effects, particles and sounds, durability, and calling plain Java classes from Python.
"""
import java

from pyfabric import mc, players, recipes, registry, world

SmallFireball = java.type("net.minecraft.world.entity.projectile.hurtingprojectile.SmallFireball")

TAB = registry.creative_tab("wands", title="Magic Wands", icon="fire_wand")

fire_wand = registry.item("fire_wand", durability=64, rarity="uncommon", tab=TAB,
                          tooltip="Right-click: shoot a fireball")
lightning_staff = registry.item("lightning_staff", durability=32, rarity="rare", tab=TAB,
                                tooltip="Right-click: call lightning where you look")
blink_wand = registry.item("blink_wand", durability=48, rarity="rare", tab=TAB,
                           tooltip="Right-click: teleport up to 12 blocks forward")
healing_staff = registry.item("healing_staff", durability=24, rarity="epic", tab=TAB,
                              tooltip="Right-click: heal everyone within 6 blocks")


def cast(player, hand, cooldown_ticks):
    """Shared bookkeeping for every wand: cooldown, durability, arm swing."""
    stack = player.getItemInHand(hand)
    player.getCooldowns().addCooldown(stack, cooldown_ticks)
    stack.hurtAndBreak(1, player, hand.asEquipmentSlot())


@fire_wand.on_use
def shoot_fireball(level, player, hand):
    if level.isClientSide():
        return mc.SUCCESS
    look = player.getLookAngle()
    fireball = SmallFireball(level, player, look.scale(1.5))
    fireball.setPos(player.getX() + look.x, player.getEyeY() - 0.1, player.getZ() + look.z)
    level.addFreshEntity(fireball)
    world.sound(level, player, "minecraft:item.firecharge.use")
    cast(player, hand, 10)
    return mc.SUCCESS


@lightning_staff.on_use
def smite(level, player, hand):
    if level.isClientSide():
        return mc.SUCCESS
    target = players.looking_at(player, distance=64)
    if target is None:
        players.actionbar(player, "&7Nothing to strike...")
        return mc.FAIL
    world.lightning(level, target.above())
    cast(player, hand, 40)
    return mc.SUCCESS


@blink_wand.on_use
def blink(level, player, hand):
    if level.isClientSide():
        return mc.SUCCESS
    # Walk along the view direction until something solid is in the way.
    eye, look = player.getEyePosition(), player.getLookAngle()
    best = None
    for step in range(1, 25):                       # half-block steps, up to 12 blocks
        point = eye.add(look.scale(step * 0.5))
        feet = mc.BlockPos.containing(point.x, point.y - 1.6, point.z)
        if not level.getBlockState(feet).isAir() or not level.getBlockState(feet.above()).isAir():
            break
        best = point
    if best is None:
        return mc.FAIL
    world.particles(level, "minecraft:portal", player, count=30, spread=0.6)
    players.teleport(player, best.x, best.y - 1.6, best.z)
    world.particles(level, "minecraft:portal", player, count=30, spread=0.6)
    world.sound(level, player, "minecraft:entity.enderman.teleport")
    player.resetFallDistance()
    cast(player, hand, 20)
    return mc.SUCCESS


@healing_staff.on_use
def heal_area(level, player, hand):
    if level.isClientSide():
        return mc.SUCCESS
    healed = 0
    for entity in world.entities_near(level, player.position(), 6, mc.Player):
        players.heal(entity, 8)
        players.effect(entity, "regeneration", seconds=5)
        world.particles(level, "minecraft:heart", entity, count=5)
        healed += 1
    players.actionbar(player, f"&aHealed {healed} player(s)")
    world.sound(level, player, "minecraft:block.beacon.power_select", pitch=1.6)
    cast(player, hand, 100)
    return mc.SUCCESS


# Wands are crafted from a stick and a "core" item.
for wand, core in ((fire_wand, "minecraft:blaze_powder"), (lightning_staff, "minecraft:copper_ingot"),
                   (blink_wand, "minecraft:ender_pearl"), (healing_staff, "minecraft:golden_apple")):
    recipes.shaped(wand, ["  C", " S ", "S  "], C=core, S="minecraft:stick", category="equipment")
