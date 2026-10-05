"""Run code later or repeatedly, measured in server ticks (20 ticks = 1 second).

    @scheduler.every(seconds=60)
    def announce(server):
        players.broadcast("A minute has passed")

    scheduler.after(40, lambda server: print("two seconds later"))

Tasks run on the server thread, so they may safely touch the world. All tasks are cancelled on reload.
"""
import java
from . import _core

_tasks = []
_tick = 0


class Task:
    def __init__(self, fn, delay, period, owner):
        self.fn = fn
        self.next = _tick + max(1, int(delay))
        self.period = period
        self.owner = owner
        self.cancelled = False
        self.runs = 0

    def cancel(self):
        """Stop this task."""
        self.cancelled = True

    def __repr__(self):
        return f"<Task {getattr(self.fn, '__name__', self.fn)} every={self.period} next={self.next}>"


def _ticks(ticks, seconds):
    if seconds is not None:
        return int(round(seconds * 20))
    if ticks is None:
        raise ValueError("Give ticks=... or seconds=...")
    return int(ticks)


def after(ticks=None, fn=None, *, seconds=None):
    """Run fn(server) once after a delay. Works as a decorator too: @after(seconds=5)."""
    delay = _ticks(ticks, seconds)

    def schedule(f):
        t = Task(f, delay, None, _core.owner())
        _tasks.append(t)
        return t

    return schedule if fn is None else schedule(fn)


def every(ticks=None, fn=None, *, seconds=None, delay=None):
    """Run fn(server) repeatedly. Works as a decorator: @every(seconds=10). Returns the Task."""
    period = max(1, _ticks(ticks, seconds))

    def schedule(f):
        t = Task(f, period if delay is None else delay, period, _core.owner())
        _tasks.append(t)
        if fn is None:          # used as a decorator: keep the function, expose the task
            f.task = t
            return f
        return t

    return schedule if fn is None else schedule(fn)


def tasks():
    return [t for t in _tasks if not t.cancelled]


def current_tick():
    """Ticks since the server started (counted by pyfabric)."""
    return _tick


def _run(server):
    global _tick
    _tick += 1
    if not _tasks:
        return
    due = [t for t in _tasks if t.next <= _tick and not t.cancelled]
    for t in due:
        t.runs += 1
        try:
            t.fn(server)
        except _core.ERRORS as e:
            _core.report(t.owner, f"scheduled task {_core.fn_name(t.fn)}()", e)
        if t.period is None:
            t.cancelled = True
        else:
            t.next = _tick + t.period
    _tasks[:] = [t for t in _tasks if not t.cancelled]


@_core.on_reset
def _reset():
    _tasks.clear()


def _install():
    ServerTickEvents = java.type("net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents")
    _core.Bridge.listen(ServerTickEvents.END_SERVER_TICK, "pyfabric|core|scheduler", "pyfabric", _run)


_install()
