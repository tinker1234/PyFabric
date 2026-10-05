"""Crafting, smelting and stonecutting recipes, written as Python.

Items can be given as ids ('minecraft:diamond'), short ids of your own mod ('ruby'), item handles
returned by ``registry.item``, a tag ('#minecraft:planks') or a list of alternatives.

    recipes.shaped("ruby_block", ["RRR", "RRR", "RRR"], R="ruby")
    recipes.shapeless("ruby", ["ruby_block"], count=9)
    recipes.smelting("ruby", "ruby_ore", xp=1.0, blasting=True)
"""
from . import _core, resources

_used = {}


@_core.on_reset
def _reset():
    _used.clear()


def _id(x):
    s = x if hasattr(x, "id") else str(x)
    if isinstance(s, str) and s.startswith("#"):
        return s if ":" in s else "#minecraft:" + s[1:]
    return _core.resolve(s)


def _ingredient(x):
    if isinstance(x, (list, tuple)):
        return [_id(i) for i in x]
    return _id(x)


def _result(item, count):
    r = {"id": _id(item)}
    if count != 1:
        r["count"] = int(count)
    return r


def _save(recipe_id, result_item, suffix, body):
    owner = _core.owner()
    if recipe_id is None:
        recipe_id = _id(result_item).split(":", 1)[1] + suffix
    rid = _core.namespaced(recipe_id, owner)
    n = _used.get(rid, 0)
    _used[rid] = n + 1
    if n:
        rid = f"{rid}_{n + 1}"
    ns, path = rid.split(":", 1)
    resources.data(f"{ns}/recipe/{path}.json", body)
    return rid


def shaped(result, pattern, key=None, *, count=1, id=None, category="misc", group=None, **symbols):
    """Shaped crafting. ``pattern`` is up to 3 strings; symbols map to items via ``key`` or keywords."""
    key = dict(key or {}, **symbols)
    body = {"type": "minecraft:crafting_shaped", "category": category,
            "key": {k: _ingredient(v) for k, v in key.items()},
            "pattern": list(pattern), "result": _result(result, count)}
    if group:
        body["group"] = group
    return _save(id, result, "", body)


def shapeless(result, ingredients, *, count=1, id=None, category="misc", group=None):
    """Shapeless crafting: up to 9 ingredients in any arrangement."""
    body = {"type": "minecraft:crafting_shapeless", "category": category,
            "ingredients": [_ingredient(i) for i in ingredients], "result": _result(result, count)}
    if group:
        body["group"] = group
    return _save(id, result, "", body)


def _cooking(kind, result, ingredient, xp, time, id, category, count):
    body = {"type": f"minecraft:{kind}", "category": category, "cookingtime": int(time),
            "experience": float(xp), "ingredient": _ingredient(ingredient), "result": _result(result, count)}
    return _save(id, result, f"_from_{kind}", body)


def smelting(result, ingredient, *, xp=0.1, time=200, id=None, category="misc", count=1,
             blasting=False, smoking=False, campfire=False):
    """Furnace recipe. blasting/smoking/campfire=True also add those variants (at vanilla speeds)."""
    ids = [_cooking("smelting", result, ingredient, xp, time, id, category, count)]
    if blasting:
        ids.append(_cooking("blasting", result, ingredient, xp, time // 2, None if id is None else id + "_blasting", category, count))
    if smoking:
        ids.append(_cooking("smoking", result, ingredient, xp, time // 2, None if id is None else id + "_smoking", "food", count))
    if campfire:
        ids.append(_cooking("campfire_cooking", result, ingredient, xp, time * 3, None if id is None else id + "_campfire", "food", count))
    return ids


def stonecutting(result, ingredient, *, count=1, id=None):
    body = {"type": "minecraft:stonecutting", "ingredient": _ingredient(ingredient), "result": _result(result, count)}
    return _save(id, result, "_from_stonecutting", body)


def raw(recipe_id, body):
    """Any recipe JSON you like (e.g. smithing), as a dict."""
    rid = _core.namespaced(recipe_id)
    ns, path = rid.split(":", 1)
    resources.data(f"{ns}/recipe/{path}.json", body)
    return rid
