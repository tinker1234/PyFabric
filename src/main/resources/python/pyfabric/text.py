"""Building chat text (Minecraft ``Component`` objects) from Python strings.

    text("Hello ", text("world", color="gold", bold=True), "!")
    text("&aGreen &lbold&r normal")        # '&' colour codes work too
"""
from .mc import Component, ChatFormatting

_COLOR_CODES = {c: ChatFormatting.getByCode(c) for c in "0123456789abcdefklmnor"}


def _is_component(x):
    return not isinstance(x, (str, int, float, bool)) and hasattr(x, "getString") and hasattr(x, "getStyle")


def _legacy(s):
    """Parse '&a', '&l' ... formatting codes."""
    if "&" not in s:
        return Component.literal(s)
    out = Component.empty()
    styles = []
    buf = []

    def flush():
        if buf:
            part = Component.literal("".join(buf))
            for st in styles:
                part = part.withStyle(st)
            out.append(part)
            buf.clear()

    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "&" and i + 1 < len(s) and s[i + 1].lower() in _COLOR_CODES:
            flush()
            fmt = _COLOR_CODES[s[i + 1].lower()]
            if fmt == ChatFormatting.RESET:
                styles.clear()
            elif s[i + 1].lower() in "0123456789abcdef":
                styles[:] = [fmt]        # a colour resets previous formats, like vanilla
            else:
                styles.append(fmt)
            i += 2
            continue
        buf.append(ch)
        i += 1
    flush()
    return out


def text(*parts, color=None, bold=False, italic=False, underline=False, strikethrough=False, obfuscated=False):
    """Make a Component from strings / Components, with optional styling.

    color: a name like "gold", "red", "dark_aqua", "#ff8800" hex, or a ChatFormatting value.
    """
    if len(parts) == 1 and _is_component(parts[0]):
        comp = parts[0].copy()
    else:
        comp = Component.empty()
        for p in parts:
            comp.append(p if _is_component(p) else _legacy(str(p)))
    if color is not None:
        if isinstance(color, str) and color.startswith("#"):
            TextColor = __import__("java").type("net.minecraft.network.chat.TextColor")
            comp = comp.withColor(TextColor.parseColor(color).getOrThrow().getValue())
        else:
            if isinstance(color, str):
                try:
                    fmt = ChatFormatting.valueOf(color.upper())
                except BaseException:
                    raise ValueError(f"Unknown colour '{color}'") from None
            else:
                fmt = color
            comp = comp.withStyle(fmt)
    for flag, fmt in ((bold, ChatFormatting.BOLD), (italic, ChatFormatting.ITALIC),
                      (underline, ChatFormatting.UNDERLINE), (strikethrough, ChatFormatting.STRIKETHROUGH),
                      (obfuscated, ChatFormatting.OBFUSCATED)):
        if flag:
            comp = comp.withStyle(fmt)
    return comp


def as_component(x):
    """Strings become text(...); Components pass through."""
    return x if _is_component(x) else text(str(x))


def plain(component):
    """Component -> plain Python string."""
    return str(component.getString())


def translatable(key, *args):
    return Component.translatable(key, *[as_component(a) if not isinstance(a, (int, float)) else a for a in args])
