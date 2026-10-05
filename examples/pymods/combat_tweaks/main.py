"""Combat Tweaks - small rule changes through events.

Shows: cancelling damage (return False), reacting after damage, kill events, random loot,
titles and broadcasts, per-player state kept in a plain Python dict.
"""
import random

import java

from pyfabric import events, mc, players, world

Enemy = java.type("net.minecraft.world.entity.monster.Enemy")   # interface implemented by hostile mobs

streaks = {}          # player uuid -> kills since last death (in memory; resets on restart)
BONUS_LOOT = [("minecraft:emerald", 0.05), ("minecraft:gold_nugget", 0.25), ("minecraft:experience_bottle", 0.03)]


@events.on_damage
def feather_falling(entity, source, amount):
    """Holding a feather in the off hand cancels fall damage. Returning False cancels the damage."""
    if source.getMsgId() == "fall" and entity.getOffhandItem().getItem() == mc.Items.FEATHER:
        return False
    return None           # None = no opinion, let the damage happen


@events.after_damage
def lifesteal(entity, source, base_amount, taken, blocked):
    """Hits with a golden sword heal the attacker by a third of the damage dealt."""
    attacker = source.getEntity()
    if isinstance(attacker, mc.Player) and taken > 0 and attacker.getMainHandItem().getItem() == mc.Items.GOLDEN_SWORD:
        players.heal(attacker, taken / 3)


@events.on_kill
def killed(level, killer, victim, source):
    if isinstance(killer, mc.ServerPlayer):
        # Bonus loot from hostile mobs
        if isinstance(victim, Enemy):
            for item, chance in BONUS_LOOT:
                if random.random() < chance:
                    world.drop_item(level, victim.blockPosition(), item)
        # Kill streaks
        key = str(killer.getUUID())
        streaks[key] = streaks.get(key, 0) + 1
        n = streaks[key]
        if n in (5, 10, 25, 50, 100):
            players.title(killer, f"&6{n} kill streak!", "&eKeep going", stay=40)
            players.broadcast(f"&6{players.name(killer)} is on a {n} kill streak!")


@events.on_death
def reset_streak(entity, source):
    if isinstance(entity, mc.ServerPlayer):
        lost = streaks.pop(str(entity.getUUID()), 0)
        if lost >= 5:
            players.broadcast(f"&c{players.name(entity)}'s {lost} kill streak has ended")
