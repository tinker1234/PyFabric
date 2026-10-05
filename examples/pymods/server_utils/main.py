"""Server Utils - a grab-bag of handy commands.

Shows: command signatures with typed / optional arguments, permissions, aliases, CommandError,
targeting other players, running vanilla commands, and saving data per world (homes).
"""
from pyfabric import CommandError, command, mc, players, storage, world

OP = 2   # permission level of operators (same as /gamemode, /tp ...)


@command("heal [target:player]", permission=OP)
def heal(ctx, target=None):
    target = target or ctx.require_player()
    players.heal(target)
    players.feed(target)
    target.clearFire()
    ctx.reply(f"&aHealed {players.name(target)}")


@command("feed [target:player]", permission=OP)
def feed(ctx, target=None):
    target = target or ctx.require_player()
    players.feed(target)
    ctx.reply(f"&aFed {players.name(target)}")


@command("fly [target:player]", permission=OP)
def fly(ctx, target=None):
    target = target or ctx.require_player()
    allowed = not target.getAbilities().mayfly
    players.set_flying(target, allowed)
    ctx.reply(f"Flight {'&aenabled' if allowed else '&cdisabled'}&r for {players.name(target)}")


@command("day", permission=OP)
def day(ctx):
    world.run_command("time set day")
    ctx.reply("&eGood morning!")


@command("night", permission=OP)
def night(ctx):
    world.run_command("time set night")
    ctx.reply("&9Good night!")


@command("spawnmob <type:word> [count:int(1,50)=1]", permission=OP, aliases=["sm"])
def spawnmob(ctx, type, count):
    """/spawnmob zombie 5 - spawns mobs where you stand (or /sm zombie 5)."""
    try:
        entity_type = mc.entity_type(type)
    except KeyError:
        raise CommandError(f"Unknown mob '{type}'")
    pos = mc.pos(ctx.position)
    for _ in range(count):
        world.spawn(ctx.level, entity_type, pos)
    ctx.reply(f"Spawned {count} x {type}")


@command("near [radius:int(1,500)=100]")
def near(ctx, radius):
    """Who is close by?"""
    me = ctx.require_player()
    others = [(p.distanceTo(me), players.name(p)) for p in world.entities_near(ctx.level, me.position(), radius, mc.Player)
              if p != me]
    if not others:
        ctx.reply(f"Nobody within {radius} blocks")
    for dist, name in sorted(others):
        ctx.reply(f" {name}: {dist:.0f} blocks")


# ---- homes, saved inside the world folder ----------------------------------------------------------------------

def homes_of(player):
    data = storage.world_data()                      # a dict persisted in <world>/pyfabric/server_utils.json
    return data.setdefault("homes", {}).setdefault(str(player.getUUID()), {})


@command("sethome [name:word=home]")
def sethome(ctx, name):
    player = ctx.require_player()
    homes = homes_of(player)
    if name not in homes and len(homes) >= 3:
        raise CommandError("You already have 3 homes - /delhome one first")
    homes[name] = {"x": player.getX(), "y": player.getY(), "z": player.getZ(), "dim": world.dimension(ctx.level)}
    ctx.reply(f"&aHome '{name}' set")


@command("home [name:word=home]")
def home(ctx, name):
    player = ctx.require_player()
    h = homes_of(player).get(name)
    if h is None:
        raise CommandError(f"No home called '{name}'. Use /sethome {name}")
    level = next((lv for lv in ctx.server.getAllLevels() if world.dimension(lv) == h["dim"]), ctx.level)
    players.teleport(player, h["x"], h["y"], h["z"], level=level)
    ctx.reply(f"Welcome home ({name})")


@command("delhome <name:word>")
def delhome(ctx, name):
    if homes_of(ctx.require_player()).pop(name, None) is None:
        raise CommandError(f"No home called '{name}'")
    ctx.reply(f"Deleted home '{name}'")


@command("homes")
def homes(ctx):
    names = sorted(homes_of(ctx.require_player()))
    ctx.reply("Your homes: " + (", ".join(names) if names else "none yet - /sethome"))
