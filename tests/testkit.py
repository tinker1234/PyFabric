"""Dev-only test harness: fake connected players for exercising Python mods on a headless server.

Usage from the server console:
    pyfabric run import testkit as t; p = t.join("Steve")
    pyfabric run t.cmd("Steve", "heal")
    pyfabric run t.msgs("Steve")
"""
import java

_t = java.type
GameProfile = _t("com.mojang.authlib.GameProfile")
UUID = _t("java.util.UUID")
CommonListenerCookie = _t("net.minecraft.server.network.CommonListenerCookie")
ServerPlayer = _t("net.minecraft.server.level.ServerPlayer")
Connection = _t("net.minecraft.network.Connection")
PacketFlow = _t("net.minecraft.network.protocol.PacketFlow")
EmbeddedChannel = _t("io.netty.channel.embedded.EmbeddedChannel")
SystemChat = _t("net.minecraft.network.protocol.game.ClientboundSystemChatPacket")
TitleText = _t("net.minecraft.network.protocol.game.ClientboundSetTitleTextPacket")
SubtitleText = _t("net.minecraft.network.protocol.game.ClientboundSetSubtitleTextPacket")
Bridge = _t("dev.pyfabric.Bridge")

players = {}
channels = {}


def server():
    return Bridge.server()


def join(name="Steve", op=True, x=None, y=None, z=None):
    s = server()
    level = s.overworld()
    profile = GameProfile(UUID.randomUUID(), name)
    cookie = CommonListenerCookie.createInitial(profile, False)
    player = ServerPlayer(s, level, profile, cookie.clientInformation())
    conn = Connection(PacketFlow.SERVERBOUND)
    ch = EmbeddedChannel(conn)
    s.getPlayerList().placeNewPlayer(conn, player, cookie)
    if op:
        s.getPlayerList().op(player.nameAndId())
    if x is not None:
        player.teleportTo(float(x), float(y), float(z))
    players[name] = player
    channels[name] = ch
    return player


def leave(name):
    p = players.pop(name)
    server().getPlayerList().remove(p)
    channels.pop(name, None)


def drain(name):
    """All packets sent to the player since the last call."""
    ch = channels[name]
    ch.runPendingTasks()
    out = []
    while True:
        m = ch.readOutbound()
        if m is None:
            break
        out.append(m)
    return out


def msgs(name):
    """Chat / actionbar / title text the player received since the last call."""
    lines = []
    for pk in drain(name):
        if isinstance(pk, SystemChat):
            lines.append(("[bar] " if pk.overlay() else "") + str(pk.content().getString()))
        elif isinstance(pk, TitleText):
            lines.append("[title] " + str(pk.text().getString()))
        elif isinstance(pk, SubtitleText):
            lines.append("[subtitle] " + str(pk.text().getString()))
    return lines


def cmd(name, command):
    p = players[name]
    server().getCommands().performPrefixedCommand(p.createCommandSourceStack(), command)
    return msgs(name)
