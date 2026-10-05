"""Announcer - timed and repeating tasks.

Shows: scheduler.every / scheduler.after, cancelling tasks, titles, a config file whose
interval is read at load time (/pyfabric reload picks up edits).
"""
from pyfabric import CommandError, command, players, scheduler, storage

cfg = storage.config({
    "interval_seconds": 300,
    "prefix": "&6[Tip]&r ",
    "messages": [
        "Sneak while mining an ore to mine the whole vein.",
        "Rubies can be smelted from ruby ore - check the Ruby Gear creative tab.",
        "Type /homes to list your saved homes.",
    ],
})

_index = 0


@scheduler.every(seconds=cfg["interval_seconds"])
def announce(server):
    global _index
    if not cfg["messages"] or not players.online():
        return
    players.broadcast(cfg["prefix"] + cfg["messages"][_index % len(cfg["messages"])])
    _index += 1


_countdown = None


@command("countdown <seconds:int(1,600)> [label:text=Go!]", permission=2)
def countdown(ctx, seconds, label):
    """Big on-screen countdown for everyone: /countdown 10 Race starts!"""
    global _countdown
    if _countdown is not None and not _countdown.cancelled:
        raise CommandError("A countdown is already running (/countdown_stop)")
    remaining = [seconds]

    def tick(server):
        global _countdown
        n = remaining[0]
        for p in players.online():
            if n > 0:
                players.title(p, f"&e{n}", fade_in=0, stay=25, fade_out=5)
            else:
                players.title(p, f"&a{label}", fade_in=0, stay=40, fade_out=10)
        if n <= 0:
            _countdown.cancel()
        remaining[0] -= 1

    _countdown = scheduler.every(seconds=1, fn=tick, delay=1)
    ctx.reply(f"Countdown of {seconds}s started")


@command("countdown_stop", permission=2)
def countdown_stop(ctx):
    if _countdown is None or _countdown.cancelled:
        raise CommandError("No countdown running")
    _countdown.cancel()
    ctx.reply("Countdown stopped")
