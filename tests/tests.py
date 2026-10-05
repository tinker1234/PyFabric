"""Integration tests for the example mods, driven by fake players (see testkit.py).

Setup: copy examples/pymods/* into run/pymods/ and tests/testkit.py + tests/tests.py into run/,
start `./gradlew runServer`, then type in the server console, waiting a few seconds between stages:

    pyfabric run import tests; tests.run(tests.stage1)
    pyfabric run tests.run(tests.stage2)
    ... stage3 .. stage7 (wait ~5 s before stage6) ...
    pyfabric run tests.summary()
"""
import java

import testkit as t
from pyfabric import mc, players, world, storage

_t = java.type
InteractionHand = mc.InteractionHand
BlockHitResult = _t("net.minecraft.world.phys.BlockHitResult")
ServerMessageEvents = _t("net.fabricmc.fabric.api.message.v1.ServerMessageEvents")
PlayerChatMessage = _t("net.minecraft.network.chat.PlayerChatMessage")
UseBlockCallback = _t("net.fabricmc.fabric.api.event.player.UseBlockCallback")

results = []
state = {}


def run(stage):
    """Run a stage on the next server tick (outside any command, so nested commands execute immediately)."""
    from pyfabric import scheduler

    def go(server):
        try:
            stage()
        except BaseException:
            import traceback
            print("STAGE CRASHED:", traceback.format_exc())
    scheduler.after(1, go)


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def summary():
    passed = sum(1 for r in results if r[1])
    print(f"=== {passed}/{len(results)} checks passed ===")
    for name, ok, detail in results:
        if not ok:
            print("  failed:", name, detail)


def level():
    return t.server().overworld()


def ground():
    lv = level()
    for cx in range(-2, 3):
        for cz in range(-2, 3):
            lv.getChunk(cx, cz)          # make sure the test area is generated
    return lv.getHeight(_t("net.minecraft.world.level.levelgen.Heightmap$Types").MOTION_BLOCKING, 0, 0)


def hold(p, item, count=1, hand=None):
    p.setItemInHand(hand or InteractionHand.MAIN_HAND, mc.stack(item, count))


def use_item(p, item):
    hold(p, item)
    return p.gameMode.useItem(p, p.level(), p.getMainHandItem(), InteractionHand.MAIN_HAND)


def items_near(pos, radius=3):
    ItemEntity = _t("net.minecraft.world.entity.item.ItemEntity")
    out = {}
    for e in world.entities_near(level(), pos, radius, ItemEntity):
        st = e.getItem()
        k = mc.id_of(st.getItem())
        out[k] = out.get(k, 0) + st.getCount()
    return out


def clear_items():
    world.run_command("kill @e[type=item]")


# ------------------------------------------------------------------------------------------------------------
def stage1():
    """Join, commands, homes, mobs, interop command."""
    y = ground()
    p = t.join("Steve", x=0.5, y=y, z=0.5)
    alex = t.join("Alex", x=3.5, y=y, z=0.5)
    state["y"] = y
    m = t.msgs("Steve")
    check("hello_world greeting on join", any("Welcome to the server, Steve" in x for x in m), m[-3:])
    check("/hello", "Hello, Steve!" in t.cmd("Steve", "hello"))
    check("/hello Alex", "Hello, Alex!" in t.cmd("Steve", "hello Alex"))
    p.setHealth(5.0)
    out = t.cmd("Steve", "heal")
    check("/heal restores health", p.getHealth() == p.getMaxHealth(), (out, p.getHealth()))
    out = t.cmd("Steve", "fly")
    check("/fly toggles mayfly", p.getAbilities().mayfly, out)
    out = t.cmd("Steve", "sethome base")
    check("/sethome", any("Home 'base' set" in x for x in out), out)
    p.teleportTo(50.5, float(y), 50.5)
    out = t.cmd("Steve", "home base")
    check("/home teleports back", abs(p.getX() - 0.5) < 0.01 and abs(p.getZ() - 0.5) < 0.01, (out, p.getX(), p.getZ()))
    check("/homes lists", any("base" in x for x in t.cmd("Steve", "homes")))
    check("/home missing -> error", any("No home called" in x for x in t.cmd("Steve", "home nowhere")))
    out = t.cmd("Steve", "sm pig 3")
    pigs = [e for e in world.entities_near(level(), p.position(), 4) if e.getType() == mc.EntityTypes.PIG]
    check("/sm alias spawns 3 pigs", len(pigs) == 3, (out, len(pigs)))
    check("java_interop names pigs", all(e.hasCustomName() for e in pigs), [str(e.getName().getString()) for e in pigs])
    check("/spawnmob bad type -> CommandError", any("Unknown mob" in x for x in t.cmd("Steve", "spawnmob notamob")))
    check("raw brigadier /square", "7 squared is 49" in t.cmd("Steve", "square 7"))
    check("/deaths shows 0", any("died 0 times" in x for x in t.cmd("Steve", "deaths")))
    out = t.cmd("Steve", "near 10")
    check("/near finds Alex", any("Alex" in x for x in out), out)
    for e in pigs:
        e.discard()


def stage2():
    """Items: wands, ruby gear."""
    p = t.players["Steve"]
    lv = level()
    y = state["y"]
    p.teleportTo(0.5, float(y), 0.5)
    t.msgs("Steve")
    p.setXRot(0.0)
    p.setYRot(0.0)
    before = len([e for e in world.entities_near(lv, p.position(), 6) if "Fireball" in str(e.getClass().getSimpleName())])
    r = use_item(p, "magic_wands:fire_wand")
    after = [e for e in lv.getEntities(None, mc.AABB.ofSize(p.position(), 10.0, 10.0, 10.0)) if "Fireball" in str(e.getClass().getSimpleName())]
    check("fire wand shoots a fireball", len(after) > before, (str(r), len(after)))
    check("fire wand goes on cooldown", p.getCooldowns().isOnCooldown(p.getMainHandItem()))
    check("fire wand loses durability", p.getMainHandItem().getDamageValue() == 1, p.getMainHandItem().getDamageValue())
    for e in after:
        e.discard()

    p.setHealth(10.0)
    t.msgs("Steve")
    use_item(p, "magic_wands:healing_staff")
    m = t.msgs("Steve")
    check("healing staff heals + actionbar", p.getHealth() > 10.0 and any("Healed" in x for x in m), (p.getHealth(), m))

    x0 = p.getX()
    p.setYRot(-90.0)      # look east (+x)
    p.setXRot(0.0)
    use_item(p, "magic_wands:blink_wand")
    check("blink wand teleports forward", p.getX() > x0 + 5, (x0, p.getX()))

    p.setXRot(90.0)       # look straight down
    target = players.looking_at(p, 64)
    r = use_item(p, "magic_wands:lightning_staff")
    bolts = [e for e in lv.getEntities(None, mc.AABB.ofSize(p.position(), 30.0, 30.0, 30.0)) if e.getType() == mc.EntityTypes.LIGHTNING_BOLT]
    check("lightning staff summons lightning", len(bolts) >= 1, (len(bolts), str(r)[:20], str(target), str(p.position()), t.msgs("Steve")[-2:]))

    # ruby sword sets targets on fire
    pig = world.spawn(lv, "minecraft:pig", p.blockPosition().east(2))
    hold(p, "ruby_gear:ruby_sword")
    p.attack(pig)
    check("ruby sword ignites target", pig.getRemainingFireTicks() > 0, pig.getRemainingFireTicks())
    pig.discard()

    # ruby apple: food with effects + glint + eaten hook
    stack = mc.stack("ruby_gear:ruby_apple")
    check("ruby apple has glint", stack.hasFoil())
    p.getFoodData().setFoodLevel(5)
    stack.finishUsingItem(lv, p)
    effects = [str(e.getEffect().unwrapKey().get().identifier()) for e in p.getActiveEffects()]
    check("ruby apple gives regen + fire resistance", "minecraft:regeneration" in effects and "minecraft:fire_resistance" in effects, effects)
    check("ruby apple restores food", p.getFoodData().getFoodLevel() > 5, p.getFoodData().getFoodLevel())

    tip = mc.item("ruby_gear:ruby_sword").hooks.callRaw("tooltip", mc.stack("ruby_gear:ruby_sword"))
    check("tooltip hook returns lines", tip is not None and "Burns" in str(tip[0]), str(tip))
    check("ruby rarity is uncommon", str(mc.stack("ruby_gear:ruby").getRarity()) == "UNCOMMON", str(mc.stack("ruby_gear:ruby").getRarity()))


def stage3():
    """Blocks: ruby ore drops, fun blocks, timber, veins."""
    p = t.players["Steve"]
    lv = level()
    y = state["y"]
    p.teleportTo(0.5, float(y), 0.5)
    p.setGameMode(mc.GameType.SURVIVAL)
    clear_items()
    base = mc.BlockPos(10, y, 10)

    # ruby ore with an iron pickaxe -> rubies
    world.set_block(lv, base, "ruby_gear:ruby_ore")
    hold(p, "minecraft:iron_pickaxe")
    ok = p.gameMode.destroyBlock(base)
    drops = items_near(base)
    check("ruby ore drops rubies with iron pickaxe", ok and drops.get("ruby_gear:ruby", 0) >= 1, (ok, drops))
    clear_items()
    world.set_block(lv, base, "ruby_gear:ruby_ore")
    hold(p, "minecraft:wooden_pickaxe")
    p.gameMode.destroyBlock(base)
    check("ruby ore drops nothing with wooden pickaxe (tool tier)", not items_near(base), items_near(base))
    world.set_block(lv, base, "ruby_gear:ruby_block")
    hold(p, "minecraft:iron_pickaxe")
    p.gameMode.destroyBlock(base)
    check("ruby block drops itself", items_near(base).get("ruby_gear:ruby_block") == 1, items_near(base))
    clear_items()
    check("ruby block is in beacon base tag", mc.has_tag(mc.state("ruby_gear:ruby_block"), "minecraft:beacon_base_blocks"))
    check("ruby is piglin_loved", mc.has_tag(mc.stack("ruby_gear:ruby"), "minecraft:piglin_loved"))
    check("ruby ore mineable with pickaxe tag", mc.has_tag(mc.state("ruby_gear:ruby_ore"), "minecraft:mineable/pickaxe"))

    # bounce pad (fall hook)
    world.set_block(lv, base, "fun_blocks:bounce_pad")
    st = lv.getBlockState(base)
    st.getBlock().fallOn(lv, st, base, p, 5.0)
    check("bounce pad launches", p.getDeltaMovement().y > 1.0, p.getDeltaMovement().y)
    p.setDeltaMovement(0.0, 0.0, 0.0)

    # pulse block redstone + light
    world.set_block(lv, base, "fun_blocks:pulse_block")
    st = lv.getBlockState(base)
    check("pulse block emits redstone 15", st.getSignal(lv, base, mc.Direction.NORTH) == 15, st.getSignal(lv, base, mc.Direction.NORTH))
    check("pulse block light level 10", st.getLightEmission() == 10, st.getLightEmission())

    # doorbell
    world.set_block(lv, base, "fun_blocks:doorbell")
    t.msgs("Alex")
    st = lv.getBlockState(base)
    r = st.useWithoutItem(lv, p, BlockHitResult.miss(mc.Vec3(10.5, y + 0.5, 10.5), mc.Direction.UP, base))
    m = t.msgs("Alex")
    check("doorbell notifies nearby players", any("rang the doorbell" in x for x in m), (str(r), m))

    # landmine: arm now, explode in stage4
    world.set_block(lv, base.offset(20, 0, 0), "fun_blocks:landmine")
    mpos = base.offset(20, 0, 0)
    zombie = world.spawn(lv, "minecraft:zombie", mpos.above())
    st = lv.getBlockState(mpos)
    st.getBlock().stepOn(lv, mpos, st, zombie)
    check("landmine schedules a tick", lv.getBlockTicks().hasScheduledTick(mpos, st.getBlock()))
    state["mine"] = mpos

    # timber: a 6 log tree
    tree = mc.BlockPos(-10, y, -10)
    for i in range(6):
        world.set_block(lv, tree.above(i), "minecraft:oak_log")
    world.set_block(lv, tree.above(5).east(), "minecraft:oak_log")
    hold(p, "minecraft:diamond_axe")
    p.gameMode.destroyBlock(tree)
    left = sum(1 for i in range(6) if world.get_block(lv, tree.above(i)) == "minecraft:oak_log")
    check("timber fells the whole tree", left == 0 and world.get_block(lv, tree.above(5).east()) != "minecraft:oak_log", left)
    check("axe took durability per log", p.getMainHandItem().getDamageValue() >= 6, p.getMainHandItem().getDamageValue())

    # vein miner
    vein = mc.BlockPos(-10, y, 10)
    for d in [(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0)]:
        world.set_block(lv, vein.offset(*d), "minecraft:iron_ore")
    hold(p, "minecraft:iron_pickaxe")
    p.setShiftKeyDown(False)
    p.gameMode.destroyBlock(vein)
    check("no vein mining without sneaking", world.get_block(lv, vein.east()) == "minecraft:iron_ore")
    p.setShiftKeyDown(True)
    p.gameMode.destroyBlock(vein.east())
    remaining = sum(1 for d in [(2, 0, 0), (2, 1, 0)] if world.get_block(lv, vein.offset(*d)) == "minecraft:iron_ore")
    check("sneak vein mining mines the vein", remaining == 0, remaining)
    p.setShiftKeyDown(False)
    clear_items()


def stage4():
    """After a short wait: landmine exploded; chat; combat; deaths."""
    lv = level()
    p = t.players["Steve"]
    alex = t.players["Alex"]
    check("landmine exploded and is gone", world.get_block(lv, state["mine"]) == "minecraft:air", world.get_block(lv, state["mine"]))

    # chat filter
    t.msgs("Steve")
    ok = ServerMessageEvents.ALLOW_CHAT_MESSAGE.invoker().allowChatMessage(PlayerChatMessage.unsigned(p.getUUID(), "this is griefing!"), p, None)
    check("chat filter blocks bad words", ok is False and any("friendly" in x for x in t.msgs("Steve")), ok)
    ok = ServerMessageEvents.ALLOW_CHAT_MESSAGE.invoker().allowChatMessage(PlayerChatMessage.unsigned(p.getUUID(), "hello all"), p, None)
    check("chat filter allows normal text", ok is True, ok)
    t.msgs("Alex")
    ServerMessageEvents.CHAT_MESSAGE.invoker().onChatMessage(PlayerChatMessage.unsigned(p.getUUID(), "hey @Alex look"), p, None)
    check("@mention pings Alex", any("mentioned you" in x for x in t.msgs("Alex")))
    ServerMessageEvents.CHAT_MESSAGE.invoker().onChatMessage(PlayerChatMessage.unsigned(p.getUUID(), "How do I get home?"), p, None)
    state["faq_pending"] = True

    # feather falling
    p.setHealth(20.0)
    hold(p, "minecraft:feather", hand=InteractionHand.OFF_HAND)
    p.hurtServer(lv, lv.damageSources().fall(), 6.0)
    check("feather in offhand cancels fall damage", p.getHealth() == 20.0, p.getHealth())
    p.setItemInHand(InteractionHand.OFF_HAND, mc.ItemStack.EMPTY)
    p.hurtServer(lv, lv.damageSources().fall(), 6.0)
    check("without feather fall damage applies", p.getHealth() < 20.0, p.getHealth())

    # lifesteal with golden sword
    p.setHealth(10.0)
    hold(p, "minecraft:golden_sword")
    z = world.spawn(lv, "minecraft:zombie", p.blockPosition().east(2))
    p.attack(z)
    check("golden sword lifesteal heals attacker", p.getHealth() > 10.0, p.getHealth())
    z.discard()

    # kill streak of 5
    t.msgs("Steve")
    for i in range(5):
        z = world.spawn(lv, "minecraft:zombie", p.blockPosition().east(2))
        z.hurtServer(lv, lv.damageSources().playerAttack(p), 1000.0)
    m = t.msgs("Steve")
    check("kill streak title after 5 kills", any("5 kill streak" in x for x in m), m[-4:])

    # death tracking
    alex.hurtServer(lv, lv.damageSources().generic(), 1000.0)
    out = t.cmd("Steve", "deaths Alex")
    check("death tracker counts Alex's death", any("died 1 time" in x for x in out), out)
    out = t.cmd("Steve", "deathtop")
    check("/deathtop lists Alex", any("Alex" in x for x in out), out)


def stage5():
    """FAQ answer arrived; countdown & treasure hunt start."""
    m = t.msgs("Steve")
    check("FAQ auto-answer broadcast (1 tick later)", any("[FAQ]" in x and "/sethome" in x for x in m), m[-3:])
    out = t.cmd("Steve", "countdown 2 Go go go")
    check("/countdown starts", any("Countdown of 2s started" in x for x in out), out)
    out = t.cmd("Steve", "hunt start 20")
    check("/hunt start broadcasts", any("treasure chest has been hidden" in x for x in out), out)
    import pymods.treasure_hunt.main as th
    check("treasure chest placed", th.hunt is not None and world.get_block(level(), th.hunt.pos) == "minecraft:chest",
          None if th.hunt is None else str(th.hunt.pos))
    chest = level().getBlockEntity(th.hunt.pos)
    filled = sum(1 for i in range(27) if not chest.getItem(i).isEmpty())
    check("treasure chest filled with loot", filled == 6, filled)


def stage6():
    """After ~4 s: countdown titles, hunt hints, open chest."""
    m = t.msgs("Steve")
    titles = [x for x in m if x.startswith("[title]")]
    check("countdown showed titles 2,1,Go", any("2" in x for x in titles) and any("Go go go" in x for x in titles), titles)
    check("treasure hint on actionbar", any(x.startswith("[bar] Treasure:") for x in m), [x for x in m if "bar" in x][:2])
    import pymods.treasure_hunt.main as th
    p = t.players["Steve"]
    pos = th.hunt.pos
    UseBlockCallback.EVENT.invoker().interact(p, level(), InteractionHand.MAIN_HAND,
                                              BlockHitResult(mc.Vec3(pos.getX() + 0.5, pos.getY() + 0.5, pos.getZ() + 0.5), mc.Direction.UP, pos, False))
    m = t.msgs("Steve")
    check("finding the chest wins the hunt", th.hunt is None and any("found the treasure" in x for x in m), m[-2:])


def stage7():
    """Persistence: world data file + config files."""
    from pathlib import Path
    world.run_command("save-all")
    root = Path(str(t.server().getWorldPath(_t("net.minecraft.world.level.storage.LevelResource").ROOT).toAbsolutePath().normalize()))
    f = root / "pyfabric" / "server_utils.json"
    check("homes saved in world folder", f.exists() and "base" in f.read_text(), str(f))
    f2 = root / "pyfabric" / "death_tracker.json"
    check("deaths saved in world folder", f2.exists() and "Alex" in f2.read_text(), str(f2))
    cfgdir = Path(str(_t("dev.pyfabric.Bridge").configDir())) / "pymods"
    check("config files created", all((cfgdir / f"{n}.json").exists() for n in ("timber", "chat_tools", "announcer")),
          sorted(x.name for x in cfgdir.glob("*.json")))
