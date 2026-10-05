"""Generates the original 16x16 pixel-art textures used by the example mods (run once; output is committed)."""
from pathlib import Path
from PIL import Image
import random

ROOT = Path(__file__).resolve().parent.parent / "examples" / "pymods"

def save(img, mod, kind, name):
    p = ROOT / mod / "assets" / mod / "textures" / kind / f"{name}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)

def from_map(rows, palette):
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                img.putpixel((x, y), palette[ch])
    return img

RUBY = {"o": (60, 0, 10, 255), "d": (130, 10, 30, 255), "m": (200, 25, 50, 255), "l": (240, 80, 100, 255), "w": (255, 200, 210, 255)}

gem = [
    "................",
    "................",
    "................",
    ".....oooooo.....",
    "....omwlllmo....",
    "...omlwllmmdo...",
    "..ommllllmmddo..",
    "..oddmmmmmmddo..",
    "...oddmmmmddo...",
    "....oddmmddo....",
    ".....oddddo.....",
    "......oddo......",
    ".......oo.......",
    "................",
    "................",
    "................",
]
save(from_map(gem, RUBY), "ruby_gear", "item", "ruby")

# ruby block: bevelled tiles
rng = random.Random(7)
blk = Image.new("RGBA", (16, 16))
for y in range(16):
    for x in range(16):
        edge = x in (0, 15) or y in (0, 15)
        hi = x in (1,) or y in (1,)
        lo = x in (14,) or y in (14,)
        base = (110, 8, 25) if edge else (235, 90, 110) if hi else (140, 15, 35) if lo else (190, 25, 50)
        j = rng.randint(-12, 12) if not edge else 0
        blk.putpixel((x, y), (max(0, min(255, base[0] + j)), max(0, base[1] + j // 3), max(0, base[2] + j // 2), 255))
for (x, y) in [(4, 4), (5, 4), (4, 5), (10, 9), (11, 9), (10, 10)]:
    blk.putpixel((x, y), (255, 190, 200, 255))
save(blk, "ruby_gear", "block", "ruby_block")

# ruby ore: stone noise + gem specks
ore = Image.new("RGBA", (16, 16))
for y in range(16):
    for x in range(16):
        v = 118 + rng.randint(-18, 18)
        ore.putpixel((x, y), (v, v, v, 255))
for cx, cy in [(3, 3), (10, 5), (5, 11), (12, 12)]:
    for dx, dy, c in [(0, 0, RUBY["m"]), (1, 0, RUBY["l"]), (0, 1, RUBY["d"]), (1, 1, RUBY["m"]), (-1, 0, RUBY["o"]), (0, -1, RUBY["o"])]:
        if 0 <= cx + dx < 16 and 0 <= cy + dy < 16:
            ore.putpixel((cx + dx, cy + dy), c)
save(ore, "ruby_gear", "block", "ruby_ore")

apple = [
    "................",
    "........g.......",
    ".......bgg......",
    ".......b........",
    "....oooboooo....",
    "...omlwmmmmdo...",
    "..omlwlmmmmddo..",
    "..omllmmmmmddo..",
    "..ommmmmmmmddo..",
    "..ommmmmmmdddo..",
    "..oddmmmmmdddo..",
    "...oddmmmdddo...",
    "....oddddddo....",
    ".....oo..oo.....",
    "................",
    "................",
]
save(from_map(apple, {**RUBY, "g": (70, 160, 50, 255), "b": (90, 60, 30, 255)}), "ruby_gear", "item", "ruby_apple")

STICK = {"s": (110, 75, 40, 255), "t": (70, 45, 20, 255)}
sword = [
    "..............oo",
    ".............olo",
    "............olmo",
    "...........olmo.",
    "..........olmo..",
    ".........olmo...",
    "........olmo....",
    ".......olmo.....",
    "..oo..olmo......",
    "..odoolmo.......",
    "...oddmo........",
    "....oddo........",
    "...ostodo.......",
    "..ost..odo......",
    ".ost....oo......",
    ".oo.............",
]
save(from_map(sword, {**RUBY, **STICK}), "ruby_gear", "item", "ruby_sword")

pick = [
    "................",
    "....ooooooo.....",
    "...olllmmmdo....",
    "....ooooosmdo...",
    "........ost.do..",
    ".......ost..odo.",
    "......ost....odo",
    ".....ost.....odo",
    "....ost.......o.",
    "...ost..........",
    "..ost...........",
    ".ost............",
    "ost.............",
    "oo..............",
    "................",
    "................",
]
save(from_map(pick, {**RUBY, **STICK}), "ruby_gear", "item", "ruby_pickaxe")

# magic wands: stick + coloured orb
def wand(orb, glow):
    rows = [
        "................",
        "...........gg...",
        "..........gooog.",
        "..........ooooo.",
        ".........gooooog",
        "..........ooooo.",
        ".........stoog..",
        "........st..g...",
        ".......st.......",
        "......st........",
        ".....st.........",
        "....st..........",
        "...st...........",
        "..st............",
        ".st.............",
        "................",
    ]
    return from_map(rows, {**STICK, "o": orb, "g": glow})

for name, orb, glow in [("fire_wand", (255, 120, 20, 255), (255, 220, 80, 200)),
                        ("lightning_staff", (120, 200, 255, 255), (230, 250, 255, 200)),
                        ("blink_wand", (170, 60, 220, 255), (230, 170, 255, 200)),
                        ("healing_staff", (80, 220, 110, 255), (200, 255, 210, 200))]:
    save(wand(orb, glow), "magic_wands", "item", name)

# fun blocks
def pad(top, accent, pattern):
    img = Image.new("RGBA", (16, 16))
    for y in range(16):
        for x in range(16):
            c = accent if pattern(x, y) else top
            j = rng.randint(-8, 8)
            img.putpixel((x, y), (max(0, min(255, c[0] + j)), max(0, min(255, c[1] + j)), max(0, min(255, c[2] + j)), 255))
    return img

save(pad((60, 170, 60), (140, 240, 120), lambda x, y: (x - 7.5) ** 2 + (y - 7.5) ** 2 < 14 or x in (0, 15) or y in (0, 15)), "fun_blocks", "block", "bounce_pad")
save(pad((40, 40, 60), (90, 200, 255), lambda x, y: (y - x) % 6 in (0, 1)), "fun_blocks", "block", "speed_path")
save(pad((235, 235, 235), (230, 40, 50), lambda x, y: (6 <= x <= 9 and 2 <= y <= 13) or (6 <= y <= 9 and 2 <= x <= 13)), "fun_blocks", "block", "healing_pad")
save(pad((90, 90, 95), (200, 30, 30), lambda x, y: (x - 7.5) ** 2 + (y - 7.5) ** 2 < 6), "fun_blocks", "block", "landmine")
save(pad((150, 110, 60), (240, 200, 70), lambda x, y: (x - 7.5) ** 2 + (y - 7.5) ** 2 < 10 and not (x - 7.5) ** 2 + (y - 7.5) ** 2 < 3), "fun_blocks", "block", "doorbell")
print("textures written to", ROOT)
