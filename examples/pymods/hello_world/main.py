"""Hello World - the smallest useful PyFabric mod.

* logs a line when the game loads
* greets every player who joins
* adds /hello [name]
"""
from pyfabric import command, events, log, players

log("Hello from Python!")


@events.on_player_join
def greet(player):
    # '&6' is gold, '&e' yellow - the classic Minecraft colour codes work in any message.
    players.tell(player, f"&6Welcome to the server, &e{players.name(player)}&6!")


@command("hello [name:word]")
def hello(ctx, name=None):
    """/hello          -> Hello, <your name>!
       /hello Alex     -> Hello, Alex!"""
    ctx.reply(f"Hello, {name or ctx.name}!")
