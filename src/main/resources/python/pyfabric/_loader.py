"""Finds, orders, loads and hot-reloads Python mods. Called from Java (PythonHost)."""
import contextlib
import importlib
import io
import json
import re
import sys
import traceback
from pathlib import Path

import pyfabric
from . import _core, resources, commands, libs

_ID = re.compile(r"^[a-z0-9_]+$")


def _log(level, msg, owner="PyFabric"):
    _core.Bridge.log(owner, level, msg)


def _discover():
    root = Path(str(_core.Bridge.gameDir())) / "pymods"
    root.mkdir(exist_ok=True)
    found = {}
    for entry in sorted(root.iterdir()):
        is_pkg = entry.is_dir()
        name = entry.name if is_pkg else entry.stem
        if name.startswith((".", "_")) or name in ("__pycache__", "lib"):
            continue
        if is_pkg:
            if not (entry / "main.py").exists() and not (entry / "client.py").exists():
                continue
        elif entry.suffix != ".py":
            continue
        if not _ID.match(name):
            _log("warn", f"Skipping pymods/{entry.name}: mod ids may only use a-z, 0-9 and _")
            continue
        meta = {}
        meta_file = entry / "pymod.json" if is_pkg else None
        if meta_file is not None and meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text("utf-8"))
            except ValueError as e:
                _log("error", f"Bad pymod.json in {entry}: {e}")
        found[name] = _core.ModInfo(name, entry, is_pkg, meta)

    # Order: respect "load_after", otherwise alphabetical.
    ordered, visiting = {}, set()

    def visit(mid):
        if mid in ordered or mid not in found:
            return
        if mid in visiting:
            _log("warn", f"Circular load_after involving {mid}")
            return
        visiting.add(mid)
        for dep in found[mid].load_after:
            visit(dep)
        visiting.discard(mid)
        ordered[mid] = found[mid]

    for mid in found:
        visit(mid)
    return ordered


def _run_entry(entry):
    for m in _core.mods.values():
        if not m.enabled:
            m.state = "disabled"
            continue
        if m.state == "failed":
            continue
        missing = [d for d in m.load_after if d in _core.mods and _core.mods[d].state == "failed"]
        if missing:
            m.state, m.error = "failed", f"depends on failed mod(s): {', '.join(missing)}"
            continue
        if entry == "client":
            if not m.has_client:
                continue
            module = f"pymods.{m.id}.client"
        elif m.is_package:
            if not (m.path / "main.py").exists():
                m.state = "loaded"
                continue
            module = f"pymods.{m.id}.main"
        else:
            module = f"pymods.{m.id}"
        _core.current = m
        try:
            importlib.import_module(module)
            m.state = "loaded"
        except (*_core.ERRORS, SystemExit) as e:
            m.state = "failed"
            summary, details = _core.describe_error(e)
            m.error = details
            _log("error", f"Python mod '{m.id}' failed to load ({entry}): {summary}\n{details}", m.id)
        finally:
            _core.current = None


def load_main():
    libs.scan()
    _core.phase = "init"
    _core.mods = _discover()
    if not _core.mods:
        _log("info", "No Python mods found in pymods/ - see the PyFabric docs to write one")
    _run_entry("main")
    resources.write_packs(_core.mods.values())
    _core.phase = "running"
    ok = sum(1 for m in _core.mods.values() if m.state == "loaded")
    _log("info", f"Loaded {ok}/{len(_core.mods)} Python mod(s): {', '.join(_core.mods) or '-'}")


def load_client():
    _run_entry("client")
    resources.write_packs(_core.mods.values())


def reload():
    """Hot reload: rerun every mod's code, swapping in new event handlers, hooks, commands and data."""
    _core.EventSlots.deactivateAll()
    _core.Hooks.clearAll()
    for fn in _core._reset_hooks:
        fn()
    for name in list(sys.modules):
        if name == "pymods" or name.startswith("pymods."):
            del sys.modules[name]
    importlib.invalidate_caches()

    libs.scan()
    _core.mods = _discover()
    _core.phase = "reload"
    try:
        _run_entry("main")
        if _core.Bridge.isClient():
            _run_entry("client")
    finally:
        _core.phase = "running"
    resources.write_packs(_core.mods.values())
    commands.resync()
    _core.Bridge.reloadData()

    failed = [m.id for m in _core.mods.values() if m.state == "failed"]
    msg = f"Reloaded {len(_core.mods) - len(failed)} Python mod(s)"
    if failed:
        msg += f", {len(failed)} failed: {', '.join(failed)} (see log)"
    _log("info", msg)
    return msg


def _error_summary(text):
    lines = (text or "?").strip().splitlines()
    if lines and lines[0].startswith("Java exception:"):
        return lines[0]
    return lines[-1] if lines else "?"


def status_lines():
    lines = [f"PyFabric {pyfabric.__version__} - Python {sys.version.split()[0]} - {len(_core.mods)} mod(s), "
             f"{_core.EventSlots.activeCount()} event handler(s)"]
    for m in _core.mods.values():
        if m.state == "failed":
            lines.append(f" [FAILED] {m.id}: {_error_summary(m.error)}")
        else:
            desc = f" - {m.description}" if m.description else ""
            lines.append(f" [{m.state}] {m.id} {m.version}{desc}")
    return lines


_repl_globals = None


def run_snippet(code, source):
    """/pyfabric run <code>: evaluate Python in-game. Returns printed output and/or the value."""
    global _repl_globals
    if _repl_globals is None:
        _repl_globals = {"__name__": "pyfabric_console"}
        exec("from pyfabric import *\nfrom pyfabric.mc import *\nimport java", _repl_globals)
    g = _repl_globals
    g["source"] = source
    g["player"] = source.getPlayer()
    g["server"] = source.getServer()
    g["level"] = source.getLevel()
    out = io.StringIO()
    try:
        compiled, is_expr = compile(code, "<pyfabric run>", "eval"), True
    except SyntaxError:
        compiled, is_expr = None, False
    try:
        with contextlib.redirect_stdout(out):
            if is_expr:
                value = eval(compiled, g)
                if value is not None:
                    print(repr(value) if isinstance(value, str) else value)
            else:
                exec(compile(code, "<pyfabric run>", "exec"), g)
    except (*_core.ERRORS, SystemExit):
        out.write(traceback.format_exc(limit=3))
    text = out.getvalue().rstrip()
    return text if len(text) <= 1500 else text[:1500] + " ..."
