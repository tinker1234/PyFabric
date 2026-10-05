"""Client-side helpers: key bindings, HUD overlays and client ticks. Import only from ``client.py``.

    from pyfabric import client

    @client.on_key("Show coordinates", "H")
    def toggle(mc):
        ...

    @client.hud
    def draw(g, mc):
        client.draw_text(g, "Hello HUD", 4, 4, color=0xFFAA00)
"""
import java

from . import _core
from .text import as_component

if not _core.Bridge.isClient():
    raise ImportError("pyfabric.client can only be used on the client (put this code in client.py)")

_t = java.type
Minecraft = _t("net.minecraft.client.Minecraft")
KeyMapping = _t("net.minecraft.client.KeyMapping")
KeyCategory = _t("net.minecraft.client.KeyMapping$Category")
InputConstants = _t("com.mojang.blaze3d.platform.InputConstants")
KeyMappingHelper = _t("net.fabricmc.fabric.api.client.keymapping.v1.KeyMappingHelper")
ClientTickEvents = _t("net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents")
HudElementRegistry = _t("net.fabricmc.fabric.api.client.rendering.v1.hud.HudElementRegistry")
Identifier = _t("net.minecraft.resources.Identifier")

_keys = {}          # translation name -> KeyMapping (registered once, survive reloads)
_key_handlers = {}  # translation name -> fn(minecraft)
_hud = []           # (owner, fn(graphics, minecraft))
_tick = []          # (owner, fn(minecraft))


@_core.on_reset
def _reset():
    _key_handlers.clear()
    _hud.clear()
    _tick.clear()


def minecraft():
    """The Minecraft client instance (``.player``, ``.level``, ``.options``, ...)."""
    return Minecraft.getInstance()


def on_key(description, key, category="misc"):
    """Decorator: run fn(minecraft) whenever the key is pressed. Players can rebind it in Controls.

    key: a letter/digit ('H', '7'), or a GLFW name like 'key.keyboard.f6'.
    category: 'misc', 'gameplay', 'inventory', 'movement', 'multiplayer', 'creative'.
    """
    owner = _core.owner()
    name = f"key.{owner}.{description.lower().replace(' ', '_')}"

    def decorator(fn):
        if name not in _keys:
            code = key if key.startswith("key.") else f"key.keyboard.{key.lower()}"
            mapping = KeyMapping(name, InputConstants.getKey(code).getValue(), getattr(KeyCategory, category.upper()))
            _keys[name] = KeyMappingHelper.registerKeyMapping(mapping)
            from . import resources
            resources.lang(name, description)
        _key_handlers[name] = fn
        return fn

    return decorator


def hud(fn):
    """Decorator: fn(graphics, minecraft) is called every frame to draw on the HUD."""
    _hud.append((_core.owner(), fn))
    return fn


def on_tick(fn):
    """Decorator: fn(minecraft) every client tick (20/s), also in menus."""
    _tick.append((_core.owner(), fn))
    return fn


def _argb(color, alpha=0xFF):
    color = int(color)
    if color <= 0xFFFFFF:
        color |= alpha << 24
    return color - (1 << 32) if color >= 1 << 31 else color   # Java int is signed


def draw_text(graphics, text, x, y, color=0xFFFFFF, shadow=True):
    """Draw a string or Component on the HUD."""
    graphics.text(minecraft().font, as_component(text), int(x), int(y), _argb(color), bool(shadow))


def fill(graphics, x1, y1, x2, y2, color=0x80000000):
    """Filled rectangle (ARGB colour, e.g. 0x80000000 = half transparent black)."""
    graphics.fill(int(x1), int(y1), int(x2), int(y2), _argb(color))


def text_width(text):
    return int(minecraft().font.width(as_component(text)))


def tell(message):
    """Show a chat message to the local player only."""
    player = minecraft().player
    if player is not None:
        player.sendSystemMessage(as_component(message))


def actionbar(message):
    """Show a message above the hotbar (local player only)."""
    player = minecraft().player
    if player is not None:
        player.sendOverlayMessage(as_component(message))


def _call(owner, where, fn, *args):
    try:
        fn(*args)
    except _core.ERRORS as e:
        _core.report(owner, f"{where} -> {_core.fn_name(fn)}()", e)


def _client_tick(mc):
    for name, fn in list(_key_handlers.items()):
        mapping = _keys.get(name)
        while mapping is not None and mapping.consumeClick():
            _call(name.split(".")[1], f"key handler {name}", fn, mc)
    for owner, fn in list(_tick):
        _call(owner, "client tick", fn, mc)


def _draw_hud(graphics, delta):
    if not _hud:
        return
    mc = minecraft()
    for owner, fn in list(_hud):
        _call(owner, "HUD renderer", fn, graphics, mc)       # errors are rate limited


_core.Bridge.listen(ClientTickEvents.END_CLIENT_TICK, "pyfabric|core|client-tick", "pyfabric", _client_tick)
HudElementRegistry.addLast(Identifier.fromNamespaceAndPath("pyfabric", "python_hud"), _draw_hud)
