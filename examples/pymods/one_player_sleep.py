"""One Player Sleep - a complete mod in a single file (pymods/one_player_sleep.py).

When any one player sleeps for three seconds, the night is skipped for everyone.
"""
import java

from pyfabric import events, players, scheduler, world

EntitySleepEvents = java.type("net.fabricmc.fabric.api.entity.event.v1.EntitySleepEvents")
ServerPlayer = java.type("net.minecraft.server.level.ServerPlayer")


@events.listen(EntitySleepEvents.START_SLEEPING)
def on_sleep(entity, bed_pos):
    if not isinstance(entity, ServerPlayer):
        return

    def skip_night(server):
        if entity.isSleeping() and world.is_night(entity.level()):
            world.run_command("time set day")
            world.run_command("weather clear")
            players.broadcast(f"&e{players.name(entity)} slept - good morning everyone!")

    scheduler.after(seconds=3, fn=skip_night)
