"""Saving data as JSON: per-mod config files and per-world save data.

    cfg = storage.config({"greeting": "Welcome!", "max_homes": 3})
    print(cfg["greeting"])            # edit config/pymods/<mod>.json to change it

    data = storage.world_data()       # inside handlers, while a world is running
    data.setdefault("deaths", {})
    data["deaths"][name] = data["deaths"].get(name, 0) + 1   # saved automatically with the world

Values must be JSON compatible (dict, list, str, int, float, bool, None).
"""
import json
from pathlib import Path

import java

from . import _core

LevelResource = java.type("net.minecraft.world.level.storage.LevelResource")
ServerLifecycleEvents = java.type("net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents")

_world_stores = {}   # (owner, name) -> Store


class Store(dict):
    """A dict that knows where it is saved. Call .save() to write it now."""

    def __init__(self, path, initial=None):
        super().__init__(initial or {})
        self.path = Path(path)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self, indent=2, ensure_ascii=False), "utf-8")
        tmp.replace(self.path)

    @classmethod
    def load(cls, path):
        p = Path(path)
        data = {}
        if p.exists():
            try:
                data = json.loads(p.read_text("utf-8"))
            except ValueError as e:
                _core.Bridge.log("pyfabric", "error", f"Corrupt JSON in {p}: {e}; starting empty")
        return cls(p, data)


def config(defaults=None, name=None):
    """Load ``config/pymods/<mod>.json``, filling in (and saving) any missing default keys."""
    owner = name or _core.owner()
    store = Store.load(Path(str(_core.Bridge.configDir())) / "pymods" / f"{owner}.json")
    changed = not store.path.exists()
    for k, v in (defaults or {}).items():
        if k not in store:
            store[k] = v
            changed = True
    if changed:
        store.save()
    return store


def world_data(name=None):
    """Data saved inside the current world folder (``<world>/pyfabric/<mod>.json``)."""
    owner = _core.owner()
    key = (owner, name or owner)
    store = _world_stores.get(key)
    if store is not None:
        return store
    server = _core.Bridge.server()
    if server is None:
        raise RuntimeError("world_data() needs a running world - call it inside an event or command handler")
    root = Path(str(server.getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize()))
    store = Store.load(root / "pyfabric" / f"{key[1]}.json")
    _world_stores[key] = store
    return store


def save_all():
    for store in list(_world_stores.values()):
        try:
            store.save()
        except _core.ERRORS as e:
            _core.Bridge.log("pyfabric", "error", f"Could not save {store.path}: {e}")


def _after_save(server, flush, force):
    save_all()


def _stopped(server):
    save_all()
    _world_stores.clear()


_core.Bridge.listen(ServerLifecycleEvents.AFTER_SAVE, "pyfabric|core|storage-save", "pyfabric", _after_save)
_core.Bridge.listen(ServerLifecycleEvents.SERVER_STOPPED, "pyfabric|core|storage-stop", "pyfabric", _stopped)
