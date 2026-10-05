"""Chat Tools - working with chat messages.

Shows: blocking messages (allow_chat), reacting to messages (on_chat), delaying a reply with
the scheduler so it appears after the player's message, sounds for one player, a config file.
"""
import re

from pyfabric import command, events, players, scheduler, storage, world

cfg = storage.config({
    "blocked_words": ["badword", "griefing"],
    "faq": {
        "how do i get home": "Use /sethome and /home!",
        "what is the seed": "Nice try :)",
    },
})


@events.allow_chat
def filter_chat(player, message):
    """Return False to stop a message from being sent."""
    lowered = message.lower()
    for word in cfg["blocked_words"]:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            players.tell(player, "&cPlease keep the chat friendly.")
            return False
    return True


@events.on_chat
def mentions(player, message):
    """Anyone named with @name gets a ping sound and a highlighted notice."""
    for name in set(re.findall(r"@(\w+)", message)):
        target = players.get(name)
        if target is not None and target != player:
            world.sound(target.level(), target, "minecraft:block.note_block.pling", pitch=1.8, category="players")
            players.actionbar(target, f"&e{players.name(player)} mentioned you")


@events.on_chat
def faq(player, message):
    question = message.lower().strip(" ?!.")
    answer = cfg["faq"].get(question)
    if answer:
        # wait one tick so the answer appears below the question
        scheduler.after(1, lambda server: players.broadcast(f"&b[FAQ] &f{answer}"))


@command("shout <message:text>")
def shout(ctx, message):
    """Everyone sees a title on screen."""
    sender = ctx.name
    for p in players.online():
        players.title(p, f"&c{message}", f"&7- {sender}", stay=50)
    players.broadcast(f"&c&l{sender} shouts:&r {message}")
