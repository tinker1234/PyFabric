"""Libraries for Python mods: drop Java jars and pure-Python packages into a lib folder and use them.

Two places are scanned (on startup and on every ``/pyfabric reload``):

* ``pymods/lib/``          shared by all mods
* ``pymods/<mod>/lib/``    for one mod (still visible to all mods - there is one Python interpreter)

What you can put there:

=========================  =====================================================================
``something.jar``          Java library. Use its classes with ``java.type("com.example.Foo")``
                           (or ``libs.java("com.example.Foo")``). Sub-folders are scanned too.
``package/`` or ``mod.py``  pure-Python package or module: ``import package``
``name-1.0-py3-none-any.whl``  pure-Python wheel from PyPI: ``import name`` (no unpacking needed)
``something.zip``          zipped Python packages
=========================  =====================================================================

Python packages that contain compiled native code (numpy, pyyaml's C speedups, ...) can't load in the
embedded interpreter; wheels like that are skipped with a warning. Java jars can't be *removed* while the
game runs - deleting one takes effect after a restart.

    from pyfabric import libs
    Gson = libs.java("com.google.gson.Gson")
    libs.loaded()          # what was found
"""
import sys
from pathlib import Path

import java as _java

from . import _core

_jars = []            # absolute paths of jars added to the Java class path (can't be removed)
_python_paths = []    # entries this module added to sys.path
_skipped = []         # (path, reason)


def lib_dirs():
    """All lib folders: pymods/lib, pymods/_lib (older name) and each mod's lib/."""
    root = Path(str(_core.Bridge.gameDir())) / "pymods"
    dirs = [root / "lib", root / "_lib"]
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and not entry.name.startswith((".", "_")) and entry.name != "lib":
                if (entry / "lib").is_dir():
                    dirs.append(entry / "lib")
    return [d for d in dirs if d.is_dir()]


def _native_wheel(name):
    """True for wheels built for a specific platform/interpreter (they contain compiled code)."""
    parts = name[:-4].split("-")
    return len(parts) >= 5 and parts[-1] != "any"


def _add_python_path(path):
    p = str(path)
    if p not in sys.path:
        sys.path.append(p)
        _python_paths.append(p)


def scan():
    """(Re)scan the lib folders. Called by the loader before mods run."""
    _skipped.clear()
    (Path(str(_core.Bridge.gameDir())) / "pymods" / "lib").mkdir(parents=True, exist_ok=True)
    new_jars = 0
    for d in lib_dirs():
        _add_python_path(d)                                   # folders and .py modules
        for f in sorted(d.rglob("*")):
            if not f.is_file() or "__pycache__" in f.parts:
                continue
            suffix = f.suffix.lower()
            if suffix == ".jar":
                path = str(f.resolve())
                if path not in _jars:
                    try:
                        _java.add_to_classpath(path)
                        _jars.append(path)
                        new_jars += 1
                    except _core.ERRORS as e:
                        _skipped.append((path, f"could not add to the Java class path: {e}"))
            elif suffix == ".whl" and f.parent == d:
                if _native_wheel(f.name):
                    _skipped.append((str(f), "contains compiled native code (only pure-Python '-none-any.whl' wheels work)"))
                else:
                    _add_python_path(f.resolve())
            elif suffix == ".zip" and f.parent == d:
                _add_python_path(f.resolve())
    for path, reason in _skipped:
        _core.Bridge.log("PyFabric", "warn", f"Library skipped: {Path(path).name}: {reason}")
    if new_jars or _python_paths:
        _core.Bridge.log("PyFabric", "info", f"Libraries: {len(_jars)} jar(s) on the Java class path, "
                                             f"{len(_python_paths)} Python path(s)")


def java(class_name):
    """A Java class from Minecraft, a mod or a jar in a lib folder - same as java.type(class_name),
    with a clearer error when it's missing."""
    try:
        return _java.type(class_name)
    except _core.ERRORS:
        raise ImportError(f"Java class '{class_name}' not found. Is its .jar in pymods/lib/? "
                          f"({len(_jars)} jar(s) loaded)") from None


def loaded():
    """What was found: {'jars': [...], 'python_paths': [...], 'skipped': [(path, reason)]}."""
    return {"jars": list(_jars), "python_paths": list(_python_paths), "skipped": list(_skipped)}
