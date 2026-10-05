"""Everyday helpers for changing the world (server side).

    world.set_block(level, pos, "minecraft:gold_block")
    world.spawn(level, "minecraft:zombie", pos)
    world.sound(level, pos, "minecraft:entity.experience_orb.pickup")
    world.particles(level, "minecraft:heart", pos, count=10)
    world.run_command("time set day")
"""
import java

from . import _core, mc

_t = java.type
Explosion = mc.ExplosionInteraction


def _xyz(where):
    """(x, y, z) floats from a Vec3, an entity (its feet), a BlockPos (its centre) or an (x, y, z) tuple."""
    if isinstance(where, mc.Entity):
        v = where.position()
        return v.x, v.y, v.z
    if isinstance(where, mc.Vec3):
        return where.x, where.y, where.z
    if isinstance(where, (tuple, list)):
        return float(where[0]), float(where[1]), float(where[2])
    bp = mc.pos(where)
    return bp.getX() + 0.5, bp.getY() + 0.5, bp.getZ() + 0.5


def set_block(level, pos, block):
    """Place a block (id, Block, handle or BlockState)."""
    state = block if hasattr(block, "getBlock") and hasattr(block, "isAir") else mc.state(block) \
        if isinstance(block, str) else mc.block(block).defaultBlockState()
    return level.setBlockAndUpdate(mc.pos(pos), state)


def get_block(level, pos):
    """Block id at a position, e.g. 'minecraft:stone'."""
    return mc.id_of(level.getBlockState(mc.pos(pos)).getBlock())


def break_block(level, pos, drop=True, breaker=None):
    return level.destroyBlock(mc.pos(pos), bool(drop), breaker, 512)


def spawn(level, entity_type, pos):
    """Spawn an entity ('minecraft:pig') at a BlockPos / (x, y, z). Returns it."""
    et = mc.entity_type(entity_type) if isinstance(entity_type, str) else entity_type
    return et.spawn(level, mc.pos(pos), mc.EntitySpawnReason.COMMAND)


def drop_item(level, pos, item, count=1):
    """Drop an item stack into the world."""
    ItemEntity = _t("net.minecraft.world.entity.item.ItemEntity")
    p = mc.pos(pos)
    entity = ItemEntity(level, p.getX() + 0.5, p.getY() + 0.5, p.getZ() + 0.5, mc.stack(item, count))
    level.addFreshEntity(entity)
    return entity


def sound(level, pos, sound_id, volume=1.0, pitch=1.0, category="blocks"):
    """Play a sound everyone nearby hears. sound_id like 'minecraft:block.note_block.bell'."""
    x, y, z = _xyz(pos)
    level.playSound(None, float(x), float(y), float(z), mc.sound(sound_id),
                    getattr(mc.SoundSource, category.upper()), float(volume), float(pitch))


def particles(level, particle_id, pos, count=8, spread=0.5, speed=0.0):
    """Spawn simple particles ('minecraft:flame', 'minecraft:heart', ...) visible to nearby players."""
    x, y, z = _xyz(pos)
    if isinstance(pos, mc.Entity):
        y += pos.getBbHeight() / 2          # around the body, not the feet
    s = float(spread)
    return level.sendParticles(mc.particle(particle_id), float(x), float(y), float(z), int(count), s, s, s, float(speed))


def explode(level, pos, power=3.0, fire=False, breaks_blocks=True, source=None):
    """Create an explosion (TNT is power 4)."""
    x, y, z = _xyz(pos)
    interaction = Explosion.TNT if breaks_blocks else Explosion.NONE
    level.explode(source, float(x), float(y), float(z), float(power), bool(fire), interaction)


def lightning(level, pos, visual_only=False):
    bolt = mc.EntityTypes.LIGHTNING_BOLT.create(level, mc.EntitySpawnReason.COMMAND)
    p = mc.pos(pos)
    bolt.snapTo(p.getX() + 0.5, float(p.getY()), p.getZ() + 0.5)
    bolt.setVisualOnly(bool(visual_only))
    level.addFreshEntity(bolt)
    return bolt


def entities_near(level, pos, radius, entity_class=None):
    """Living entities within ``radius`` blocks of a position."""
    center = mc.Vec3(*_xyz(pos))
    box = mc.AABB.ofSize(center, radius * 2.0, radius * 2.0, radius * 2.0)
    cls = entity_class or mc.LivingEntity
    return list(level.getEntitiesOfClass(getattr(cls, "class", cls), box))


def run_command(command, as_player=None):
    """Run a command as the server console (or as a player). Leading '/' optional."""
    server = _core.Bridge.server()
    if server is None:
        raise RuntimeError("The server is not running")
    source = server.createCommandSourceStack() if as_player is None else as_player.createCommandSourceStack()
    server.getCommands().performPrefixedCommand(source, command.lstrip("/"))


def time_of_day(level):
    """0-23999 (0 = sunrise, 6000 = noon, 13000 = night)."""
    return int(level.getDefaultClockTime() % 24000)


def is_night(level):
    return bool(level.isDarkOutside())


def dimension(level):
    """'minecraft:overworld', 'minecraft:the_nether', ..."""
    return str(level.dimension().identifier())
