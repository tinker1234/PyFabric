"""Chat commands with typed arguments, from a one-line signature.

    @command("heal [target:player]", permission=2)
    def heal(ctx, target=None):
        target = target or ctx.player
        target.setHealth(target.getMaxHealth())
        ctx.reply(f"Healed {target.getName().getString()}")

Signature syntax: words are literal sub-commands, ``<name:type>`` is a required argument and
``[name:type=default]`` an optional one (optional ones must come last).

Argument types:
    int, int(min,max), float, float(min,max), bool,
    word (one word), string ("quoted" allowed), text (rest of the line),
    player, players, entity, entities, pos (block position), vec3 (exact position),
    item (an item id, gives an ItemStack-ready ItemInput), block (a block state)

The handler gets a ``ctx`` (see ``Context``) and each argument as a keyword argument.
Raise ``CommandError("message")`` to show a red error to the sender.
"""
import java
import re

from . import _core
from .text import as_component

_t = java.type
Commands = _t("net.minecraft.commands.Commands")
IntegerArgumentType = _t("com.mojang.brigadier.arguments.IntegerArgumentType")
DoubleArgumentType = _t("com.mojang.brigadier.arguments.DoubleArgumentType")
BoolArgumentType = _t("com.mojang.brigadier.arguments.BoolArgumentType")
StringArgumentType = _t("com.mojang.brigadier.arguments.StringArgumentType")
EntityArgument = _t("net.minecraft.commands.arguments.EntityArgument")
BlockPosArgument = _t("net.minecraft.commands.arguments.coordinates.BlockPosArgument")
Vec3Argument = _t("net.minecraft.commands.arguments.coordinates.Vec3Argument")
ItemArgument = _t("net.minecraft.commands.arguments.item.ItemArgument")
BlockStateArgument = _t("net.minecraft.commands.arguments.blocks.BlockStateArgument")
CommandRegistrationCallback = _t("net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback")

_PERMISSIONS = [Commands.LEVEL_ALL, Commands.LEVEL_MODERATORS, Commands.LEVEL_GAMEMASTERS,
                Commands.LEVEL_ADMINS, Commands.LEVEL_OWNERS]

_commands = []            # registered specs, rebuilt on every (re)load
_installed_roots = set()  # root literals currently in the live dispatcher


class CommandError(Exception):
    """Raise inside a command to send a red error message to whoever ran it."""


class Context:
    """What a command handler receives."""

    def __init__(self, java_ctx):
        self.raw = java_ctx                      # brigadier CommandContext
        self.source = java_ctx.getSource()       # CommandSourceStack

    @property
    def player(self):
        """The player who ran the command, or None (console / command block)."""
        return self.source.getPlayer()

    @property
    def entity(self):
        return self.source.getEntity()

    @property
    def server(self):
        return self.source.getServer()

    @property
    def level(self):
        return self.source.getLevel()

    world = level

    @property
    def position(self):
        """Vec3 the command was run at."""
        return self.source.getPosition()

    @property
    def name(self):
        return str(self.source.getTextName())

    def reply(self, message, broadcast=False):
        """Send feedback to the sender (str or Component)."""
        msg = as_component(message)
        self.source.sendSuccess(lambda: msg, bool(broadcast))

    def error(self, message):
        """Send a red error message to the sender."""
        self.source.sendFailure(as_component(message))

    def require_player(self):
        p = self.player
        if p is None:
            raise CommandError("This command can only be used by a player")
        return p


# ---- argument types -----------------------------------------------------------------------------------------

_TYPES = {
    "int": (lambda b, a: IntegerArgumentType.integer(*[int(x) for x in a]),
            lambda c, n: int(IntegerArgumentType.getInteger(c, n))),
    "float": (lambda b, a: DoubleArgumentType.doubleArg(*[float(x) for x in a]),
              lambda c, n: float(DoubleArgumentType.getDouble(c, n))),
    "bool": (lambda b, a: BoolArgumentType.bool(), lambda c, n: bool(BoolArgumentType.getBool(c, n))),
    "word": (lambda b, a: StringArgumentType.word(), lambda c, n: str(StringArgumentType.getString(c, n))),
    "string": (lambda b, a: StringArgumentType.string(), lambda c, n: str(StringArgumentType.getString(c, n))),
    "text": (lambda b, a: StringArgumentType.greedyString(), lambda c, n: str(StringArgumentType.getString(c, n))),
    "player": (lambda b, a: EntityArgument.player(), lambda c, n: EntityArgument.getPlayer(c, n)),
    "players": (lambda b, a: EntityArgument.players(), lambda c, n: list(EntityArgument.getPlayers(c, n))),
    "entity": (lambda b, a: EntityArgument.entity(), lambda c, n: EntityArgument.getEntity(c, n)),
    "entities": (lambda b, a: EntityArgument.entities(), lambda c, n: list(EntityArgument.getEntities(c, n))),
    "pos": (lambda b, a: BlockPosArgument.blockPos(), lambda c, n: BlockPosArgument.getBlockPos(c, n)),
    "vec3": (lambda b, a: Vec3Argument.vec3(), lambda c, n: Vec3Argument.getVec3(c, n)),
    "item": (lambda b, a: ItemArgument.item(b), lambda c, n: ItemArgument.getItem(c, n)),
    "block": (lambda b, a: BlockStateArgument.block(b), lambda c, n: BlockStateArgument.getBlock(c, n).getState()),
}
_TYPES["double"] = _TYPES["float"]
_TYPES["greedy"] = _TYPES["text"]

_ARG = re.compile(r"^[<\[](\w+)(?::(\w+)(?:\(([^)]*)\))?)?(?:=(.*))?[>\]]$")


class _Part:
    def __init__(self, token):
        self.literal = None
        self.optional = token.startswith("[")
        if token[0] in "<[":
            m = _ARG.match(token)
            if not m:
                raise ValueError(f"Bad command argument '{token}'")
            self.name, self.type, args, default = m.groups()
            self.type = self.type or "word"
            if self.type not in _TYPES:
                raise ValueError(f"Unknown argument type '{self.type}' (known: {', '.join(sorted(_TYPES))})")
            self.args = [x.strip() for x in args.split(",")] if args else []
            self.default = _parse_default(default) if default is not None else None
        else:
            self.literal = token
            self.optional = False


def _parse_default(s):
    for cast in (int, float):
        try:
            return cast(s)
        except ValueError:
            pass
    if s in ("true", "false", "True", "False"):
        return s.lower() == "true"
    return s.strip("\"'")


class _Spec:
    def __init__(self, signature, fn, permission, owner):
        self.signature = signature
        self.parts = [_Part(t) for t in signature.split()]
        if not self.parts or self.parts[0].literal is None:
            raise ValueError("A command must start with its name, e.g. 'heal <target:player>'")
        seen_optional = False
        for p in self.parts:
            if p.optional:
                seen_optional = True
            elif seen_optional:
                raise ValueError(f"In '{signature}': required parts can't follow optional ones")
        self.root = self.parts[0].literal
        self.fn = fn
        self.permission = permission
        self.owner = owner

    def run(self, java_ctx):
        ctx = Context(java_ctx)
        present = {str(n.getNode().getName()) for n in java_ctx.getNodes()}
        kwargs = {}
        for p in self.parts:
            if p.literal is not None:
                continue
            if p.name in present:
                kwargs[p.name] = _TYPES[p.type][1](java_ctx, p.name)
            else:
                kwargs[p.name] = p.default
        try:
            result = self.fn(ctx, **kwargs)
        except CommandError as e:
            ctx.error(str(e))
            return 0
        except _core.JavaException as e:
            if "CommandSyntaxException" in str(e.getClass().getName()):
                raise                                   # let Minecraft show the usual red usage error
            self._failed(ctx, e)
            return 0
        except Exception as e:
            self._failed(ctx, e)
            return 0
        return int(result) if isinstance(result, (int, bool)) else 1

    def _failed(self, ctx, e):
        summary, _ = _core.describe_error(e)
        _core.report(self.owner, f"command /{self.signature}", e)
        ctx.error(f"Error in /{self.root}: {summary}")

    def build(self, build_ctx):
        command = _core.Bridge.command(self.owner, self.root, self.run)
        nodes = []
        for p in self.parts:
            if p.literal is not None:
                nodes.append(Commands.literal(p.literal))
            else:
                nodes.append(Commands.argument(p.name, _TYPES[p.type][0](build_ctx, p.args)))
        last = len(nodes) - 1
        for i, node in enumerate(nodes):
            if i == last or self.parts[i + 1].optional:
                node.executes(command)
        for i in range(last, 0, -1):
            nodes[i - 1].then(nodes[i])
        root = nodes[0]
        if self.permission:
            root.requires(Commands.hasPermission(_PERMISSIONS[min(int(self.permission), 4)]))
        return root


def command(signature, *, permission=0, aliases=()):
    """Decorator registering a command. permission: 0 everyone, 2 operators (cheats), 4 owner only."""
    owner = _core.owner()

    def decorator(fn):
        specs = [_Spec(signature, fn, permission, owner)]
        for alias in aliases:
            rest = signature.split(None, 1)
            specs.append(_Spec(alias + (" " + rest[1] if len(rest) > 1 else ""), fn, permission, owner))
        _commands.extend(specs)
        if _core.phase == "running":
            _install_live(specs)
        return fn

    return decorator


# ---- wiring into Minecraft -----------------------------------------------------------------------------------

def _register_all(dispatcher, build_ctx, selection):
    _installed_roots.clear()
    for spec in _commands:
        try:
            dispatcher.register(spec.build(build_ctx))
            _installed_roots.add(spec.root)
        except _core.ERRORS:
            import traceback
            _core.Bridge.log(spec.owner, "error", f"Could not register /{spec.signature}:\n{traceback.format_exc()}")


def _install_live(specs):
    server = _core.Bridge.server()
    if server is None:
        return
    # Needs a CommandBuildContext for item/block arguments: rebuild everything via a data reload instead.
    if any(p.type in ("item", "block") for s in specs for p in s.parts if p.literal is None):
        return
    dispatcher = server.getCommands().getDispatcher()
    for spec in specs:
        dispatcher.register(spec.build(None))
        _installed_roots.add(spec.root)
    _core.Bridge.resendCommands()


def resync():
    """After a hot reload: drop the old Python commands from the live server and add the new ones."""
    server = _core.Bridge.server()
    if server is None:
        return
    dispatcher = server.getCommands().getDispatcher()
    for root in list(_installed_roots):
        _core.Bridge.removeCommand(dispatcher, root)
    _installed_roots.clear()


@_core.on_reset
def _reset():
    _commands.clear()


_core.Bridge.listen(CommandRegistrationCallback.EVENT, "pyfabric|core|commands", "pyfabric", _register_all)
