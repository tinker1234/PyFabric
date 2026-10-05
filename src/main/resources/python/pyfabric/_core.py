"""Internal state shared by the pyfabric modules. Not part of the public API."""
import sys
import java
import polyglot

#: Java exceptions reach Python as polyglot.ForeignException, which is NOT a subclass of Exception.
JavaException = polyglot.ForeignException
#: Catch this tuple to handle both Python and Java errors.
ERRORS = (Exception, JavaException)

Bridge = java.type("dev.pyfabric.Bridge")
EventSlots = java.type("dev.pyfabric.EventSlots")
Hooks = java.type("dev.pyfabric.Hooks")
System = java.type("java.lang.System")


class ModInfo:
    """Metadata and load state of one Python mod (a folder or a single .py file in /pymods)."""

    def __init__(self, mod_id, path, is_package, meta):
        self.id = mod_id
        self.path = path                  # pathlib.Path of the folder or the .py file
        self.is_package = is_package
        self.name = meta.get("name", mod_id.replace("_", " ").title())
        self.version = str(meta.get("version", "1.0.0"))
        self.description = meta.get("description", "")
        self.authors = meta.get("authors", [])
        self.load_after = meta.get("load_after", [])
        self.enabled = meta.get("enabled", True)
        self.state = "pending"            # pending | loaded | failed | disabled
        self.error = None
        self.has_client = is_package and (path / "client.py").exists()

    def __repr__(self):
        return f"<pymod {self.id} {self.version} {self.state}>"


mods = {}            # id -> ModInfo, in load order
current = None       # ModInfo whose code is being imported right now
phase = "init"       # "init" while the game starts (registries open), then "running"
_reset_hooks = []    # functions that clear pyfabric state before a hot reload


def on_reset(fn):
    _reset_hooks.append(fn)
    return fn


def owner(default="pyfabric"):
    """Mod id of the Python code calling into pyfabric (found by walking the call stack)."""
    f = sys._getframe(1)
    while f is not None:
        name = f.f_globals.get("__name__", "")
        if name.startswith("pymods."):
            return name.split(".")[1]
        f = f.f_back
    return current.id if current is not None else default


def namespaced(path, namespace=None):
    """'ruby' -> 'mymod:ruby' (the calling mod's namespace); 'minecraft:stone' stays as is."""
    path = str(path)
    if ":" in path:
        return path
    return f"{namespace or owner()}:{path}"


declared = set()     # ids of items/blocks declared by Python mods (rebuilt on reload)


def resolve(id_like, namespace=None):
    """Turn what a modder wrote into a full id.

    'minecraft:stone' -> unchanged; 'ruby' -> 'mymod:ruby' if the calling mod declared it,
    otherwise 'minecraft:ruby' (so 'stick' and 'diamond' mean the vanilla items).
    Item/block handles (anything with an ``id``) are accepted too.
    """
    if hasattr(id_like, "id") and isinstance(getattr(id_like, "id"), str):
        return id_like.id
    s = str(id_like)
    if ":" in s:
        return s
    mine = f"{namespace or owner()}:{s}"
    return mine if mine in declared else f"minecraft:{s}"


def describe_error(e):
    """(one-line summary, full report) for a Python or Java exception being handled right now."""
    import traceback
    if isinstance(e, JavaException):
        # GraalPy gives Java exceptions no Python traceback; the Java stack still names the Python functions.
        first = str(e).splitlines()[0] if str(e) else type(e).__name__
        lines = [f"Java exception: {first}"]
        try:
            for el in e.getStackTrace():
                s = str(el)
                if "com.oracle." in s or "org.graalvm" in s:
                    break                    # reached the Python interpreter: the rest is not useful
                lines.append("    at " + s.replace("knot//", ""))
                if len(lines) > 12:
                    break
            lines.append("    (thrown by a Java method called from Python; see the function named above)")
        except BaseException:
            pass
        return first, "\n".join(lines)
    return f"{type(e).__name__}: {e}", traceback.format_exc().rstrip()


def report(owner, where, e):
    """Log an exception (rate limited) and tell online operators about it."""
    summary, details = describe_error(e)
    Bridge.reportError(owner, where, summary, details)


def guard(owner, where, fn):
    """Wrap fn so that errors are reported (with a proper Python traceback) and None is returned instead."""
    def guarded(*args):
        try:
            return fn(*args)
        except ERRORS as e:
            report(owner, where, e)
            return None
    guarded.__name__ = getattr(fn, "__name__", "guarded")
    guarded.__wrapped__ = fn
    return guarded


def fn_name(fn):
    return getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))


def identity(obj):
    return System.identityHashCode(obj)

