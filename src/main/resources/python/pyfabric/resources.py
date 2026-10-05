"""Assets (textures, models, translations) and data (recipes, loot tables, tags) for Python mods.

Two sources are merged into PyFabric's always-enabled packs on every (re)load:

* Files you ship: ``pymods/<mod>/assets/...`` and ``pymods/<mod>/data/...`` are copied as they are
  (same layout as any resource pack / data pack).
* Files generated from Python: item/block models, translations, block loot tables and the recipes and
  tags you declare with this module. A file you ship always wins over a generated one.

    resources.lang("item.mymod.ruby", "Ruby")
    resources.tag("item", "minecraft:piglin_loved", "mymod:ruby")
    resources.data("mymod/advancement/found_ruby.json", {...})
"""
import json
import shutil
from pathlib import Path

from . import _core

_assets = {}   # path relative to the pack root ("assets/ns/...") -> dict | str | bytes
_data = {}     # path relative to the pack root ("data/ns/...") -> dict | str | bytes
_lang = {}     # lang code -> {key: text}
_tags = {}     # "data/<ns>/tags/<registry>/<path>.json" -> list of values


def _reset():
    _assets.clear()
    _data.clear()
    _lang.clear()
    _tags.clear()


_core.on_reset(_reset)


# ---- declaring content -------------------------------------------------------------------------------------

def asset(path, content):
    """Add a file to the resource pack. ``path`` is relative to ``assets/``, e.g. 'mymod/models/item/x.json'."""
    _assets["assets/" + path.lstrip("/")] = content


def data(path, content):
    """Add a file to the data pack. ``path`` is relative to ``data/``, e.g. 'mymod/recipe/x.json'."""
    _data["data/" + path.lstrip("/")] = content


def lang(key, value, language="en_us"):
    """Add a translation, e.g. lang('item.mymod.ruby', 'Ruby')."""
    _lang.setdefault(language, {})[key] = value


def tag(registry, tag_id, *values):
    """Add entries to a tag. registry is 'block', 'item', 'entity_type', ...

        tag("block", "minecraft:mineable/pickaxe", "mymod:ruby_block")
    """
    ns, path = _core.namespaced(tag_id).split(":", 1)
    key = f"data/{ns}/tags/{registry}/{path}.json"
    lst = _tags.setdefault(key, [])
    for v in values:
        v = str(v) if not hasattr(v, "id") else v.id
        if v.startswith("#"):
            v = v if ":" in v else "#minecraft:" + v[1:]
        else:
            v = _core.resolve(v)
        if v not in lst:
            lst.append(v)


# ---- model helpers used by the registry module ---------------------------------------------------------------

def item_model(item_id, texture=None, parent="minecraft:item/generated"):
    ns, path = item_id.split(":", 1)
    tex = texture or f"{ns}:item/{path}"
    asset(f"{ns}/models/item/{path}.json", {"parent": parent, "textures": {"layer0": tex}})
    asset(f"{ns}/items/{path}.json", {"model": {"type": "minecraft:model", "model": f"{ns}:item/{path}"}})


def block_model(block_id, texture=None, model=None):
    """Simple cube block: same texture on all sides (or a dict of faces for cube / cube_column)."""
    ns, path = block_id.split(":", 1)
    if model is None:
        if isinstance(texture, dict):
            if set(texture) <= {"end", "side"}:
                model = {"parent": "minecraft:block/cube_column", "textures": texture}
            else:
                tex = dict(texture)
                tex.setdefault("particle", next(iter(texture.values())))
                model = {"parent": "minecraft:block/cube", "textures": tex}
        else:
            model = {"parent": "minecraft:block/cube_all", "textures": {"all": texture or f"{ns}:block/{path}"}}
    asset(f"{ns}/models/block/{path}.json", model)
    asset(f"{ns}/blockstates/{path}.json", {"variants": {"": {"model": f"{ns}:block/{path}"}}})
    asset(f"{ns}/items/{path}.json", {"model": {"type": "minecraft:model", "model": f"{ns}:block/{path}"}})


def block_drops(block_id, item_id=None, count=1, silk_touch=True, fortune=True):
    """Loot table for a block.

    * ``block_drops("mymod:ruby_block")`` - drops itself.
    * ``block_drops("mymod:ruby_ore", "mymod:ruby", (1, 3))`` - drops 1-3 rubies, itself with Silk Touch,
      more with Fortune (like vanilla ores).
    """
    ns, path = block_id.split(":", 1)
    if item_id is None or item_id == block_id:
        pool = {"rolls": 1, "entries": [{"type": "minecraft:item", "name": block_id}],
                "condition": {"type": "minecraft:survives_explosion"}}
    else:
        lo, hi = (count, count) if isinstance(count, int) else count
        modifiers = []
        if (lo, hi) != (1, 1):
            modifiers.append({"type": "minecraft:set_count",
                              "count": lo if lo == hi else {"type": "minecraft:uniform", "min": lo, "max": hi}})
        if fortune:
            modifiers.append({"type": "minecraft:apply_bonus", "enchantment": "minecraft:fortune",
                              "formula": "minecraft:ore_drops"})
        modifiers.append({"type": "minecraft:explosion_decay"})
        drop = {"type": "minecraft:item", "name": item_id, "modifier": modifiers}
        if silk_touch:
            entry = {"type": "minecraft:alternatives", "children": [
                {"type": "minecraft:item", "condition": "minecraft:tool/can_silk_touch", "name": block_id}, drop]}
        else:
            entry = drop
        pool = {"rolls": 1, "entries": [entry]}
    data(f"{ns}/loot_table/blocks/{path}.json",
         {"type": "minecraft:block", "pools": [pool], "random_sequence": f"{ns}:blocks/{path}"})


# ---- writing the packs --------------------------------------------------------------------------------------

def _encode(content):
    if isinstance(content, (bytes, bytearray)):
        return bytes(content)
    if isinstance(content, str):
        return content.encode("utf-8")
    return json.dumps(content, indent=2).encode("utf-8")


def _wipe(root):
    for sub in ("assets", "data"):
        p = root / sub
        if p.exists():
            shutil.rmtree(p)


def _copy_tree(src, dst):
    for f in src.rglob("*"):
        if f.is_file():
            target = dst / f.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, target)


def write_packs(mods):
    """Rebuild both generated packs. Called by the loader after all mods ran."""
    res_root = Path(str(_core.Bridge.generatedDir("resources")))
    data_root = Path(str(_core.Bridge.generatedDir("data")))
    _wipe(res_root)
    _wipe(data_root)

    # 1. Files shipped by mods.
    for m in mods:
        if m.state != "loaded" or not m.is_package:
            continue
        if (m.path / "assets").is_dir():
            _copy_tree(m.path / "assets", res_root / "assets")
        if (m.path / "data").is_dir():
            _copy_tree(m.path / "data", data_root / "data")

    # 2. Generated files, never overwriting shipped ones.
    for root, files in ((res_root, _assets), (data_root, _data)):
        for rel, content in files.items():
            target = root / rel
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(_encode(content))

    # 3. Translations merge with shipped lang files (shipped keys win).
    for language, entries in _lang.items():
        by_ns = {}
        for key, value in entries.items():
            parts = key.split(".")
            ns = parts[1] if len(parts) > 2 else "minecraft"
            by_ns.setdefault(ns, {})[key] = value
        for ns, entries_ns in by_ns.items():
            target = res_root / "assets" / ns / "lang" / f"{language}.json"
            existing = json.loads(target.read_text("utf-8")) if target.exists() else {}
            merged = {**entries_ns, **existing}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(merged, indent=2, ensure_ascii=False), "utf-8")

    # 4. Tags merge with shipped tag files.
    for rel, values in _tags.items():
        target = data_root / rel
        existing = json.loads(target.read_text("utf-8")) if target.exists() else {"values": []}
        for v in values:
            if v not in existing["values"]:
                existing["values"].append(v)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(existing, indent=2), "utf-8")
