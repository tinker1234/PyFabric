"""Death Tracker - persistent statistics stored in the world save.

Shows: death events, per-world JSON storage, respawn events, leaderboard commands.
"""
from pyfabric import command, events, mc, players, storage, world


def stats():
    # {"<uuid>": {"name": "Steve", "deaths": 3, "last": {"x":..,"y":..,"z":..,"dim":..,"cause":..}}}
    return storage.world_data().setdefault("players", {})


@events.on_death
def died(entity, source):
    if not isinstance(entity, mc.ServerPlayer):
        return
    rec = stats().setdefault(str(entity.getUUID()), {"name": players.name(entity), "deaths": 0})
    rec["name"] = players.name(entity)
    rec["deaths"] += 1
    pos = entity.blockPosition()
    rec["last"] = {"x": pos.getX(), "y": pos.getY(), "z": pos.getZ(),
                   "dim": world.dimension(entity.level()), "cause": str(source.getMsgId())}


@events.on_player_respawn
def tell_location(old_player, new_player, alive):
    if alive:                      # coming back from the End, not a death
        return
    rec = stats().get(str(new_player.getUUID()))
    if rec and "last" in rec:
        last = rec["last"]
        players.tell(new_player, f"&7You died at &f{last['x']} {last['y']} {last['z']}&7 "
                                 f"({last['dim'].split(':')[1]}). Deaths so far: &c{rec['deaths']}")


@command("deaths [target:player]")
def deaths(ctx, target=None):
    target = target or ctx.require_player()
    rec = stats().get(str(target.getUUID()))
    count = rec["deaths"] if rec else 0
    ctx.reply(f"{players.name(target)} has died &c{count}&r time{'s' if count != 1 else ''}")


@command("deathtop")
def deathtop(ctx):
    ranking = sorted(stats().values(), key=lambda r: r["deaths"], reverse=True)[:10]
    if not ranking:
        ctx.reply("Nobody has died yet. Impressive.")
        return
    ctx.reply("&6--- Most deaths ---")
    for i, rec in enumerate(ranking, 1):
        ctx.reply(f"&e{i}. &f{rec['name']} &7- &c{rec['deaths']}")
