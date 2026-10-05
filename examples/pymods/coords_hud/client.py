"""Coords HUD - a client-only mod (this folder has client.py but no main.py).

Client-only mods work on any server, even vanilla ones, because nothing is registered.

Shows: key bindings (rebindable in Options > Controls), drawing on the HUD every frame,
client ticks, reading the local player and world.
"""
from pyfabric import client

state = {"visible": True, "fps_samples": []}


@client.on_key("Toggle coordinates HUD", "H")
def toggle(mc):
    state["visible"] = not state["visible"]
    client.actionbar(f"Coordinates HUD {'shown' if state['visible'] else 'hidden'}")


@client.hud
def draw(g, mc):
    player = mc.player
    if not state["visible"] or player is None or mc.level is None:
        return
    pos = player.blockPosition()
    facing = str(player.getDirection().getName())
    biome = str(mc.level.getBiome(pos).unwrapKey().map(lambda k: k.identifier().getPath()).orElse("?"))
    lines = [
        f"&fXYZ: &e{pos.getX()} {pos.getY()} {pos.getZ()}",
        f"&fFacing: &e{facing}",
        f"&fBiome: &a{biome.replace('_', ' ')}",
        f"&fFPS: &b{mc.getFps()}",
    ]
    width = max(client.text_width(line.replace('&f', '').replace('&e', '').replace('&a', '').replace('&b', ''))
                for line in lines)
    client.fill(g, 2, 2, 8 + width, 6 + 10 * len(lines), 0x90000000)
    for i, line in enumerate(lines):
        client.draw_text(g, line, 5, 5 + 10 * i)
