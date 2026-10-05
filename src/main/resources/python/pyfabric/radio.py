"""Internet radio: play Icecast / Shoutcast / MP3 streams in the game. Client only - use it from client.py.

    from pyfabric import radio

    radio.play("http://example.com:8000/stream.mp3")
    radio.volume(0.5)               # 0.0 - 1.0, multiplied by Minecraft's Master and Music sliders
    radio.now_playing()             # "Artist - Song", or None

    @radio.on_title
    def changed(title):
        client.tell(f"Now playing: {title}")

Players can also use the built-in /radio command (play / stop / volume / titles).
MP3 streams only (most Icecast and Shoutcast stations); .pls and .m3u links are followed.
AAC, Ogg and HLS (.m3u8) streams are not supported.
"""
import java

from . import _core

if not _core.Bridge.isClient():
    raise ImportError("pyfabric.radio can only be used on the client (put this code in client.py)")

_Radio = java.type("dev.pyfabric.client.radio.RadioClient")
_title_listeners = []   # (owner, fn)
_state_listeners = []


@_core.on_reset
def _reset():
    _title_listeners.clear()
    _state_listeners.clear()


def play(url=None):
    """Start playing a stream URL (stops the current one). Without a URL, replays the last station."""
    url = url or str(_Radio.getLastUrl() or "")
    if not url:
        raise ValueError("No stream URL given and no previous station to resume")
    _Radio.play(url)


def stop():
    _Radio.stop()


def volume(value=None):
    """Get the radio volume, or set it (0.0 - 1.0). Saved between game sessions."""
    if value is None:
        return float(_Radio.getVolume())
    _Radio.setVolume(float(value))


def is_playing():
    """True while connecting, playing or reconnecting."""
    return bool(_Radio.isPlaying())


def state():
    """'CONNECTING', 'PLAYING', 'RECONNECTING', 'STOPPED' or 'FAILED'."""
    return str(_Radio.getState())


def now_playing():
    """Current song title from the stream's metadata, or None."""
    t = _Radio.getTitle()
    return None if t is None else str(t)


def station():
    """Station name (from the icy-name header), or None."""
    s = _Radio.getStation()
    return None if s is None else str(s)


def url():
    return str(_Radio.getUrl() or "")


def show_titles(on=True):
    """Show 'Now playing' above the hotbar when the song changes (on by default)."""
    _Radio.setAnnounceTitles(bool(on))


def on_title(fn):
    """Decorator: fn(title) runs on the client thread when the song changes."""
    _title_listeners.append((_core.owner(), fn))
    return fn


def on_state(fn):
    """Decorator: fn(state, message) when the radio connects, plays, reconnects, stops or fails."""
    _state_listeners.append((_core.owner(), fn))
    return fn


def _dispatch_title(title):
    for owner, fn in list(_title_listeners):
        try:
            fn(str(title))
        except _core.ERRORS as e:
            _core.report(owner, f"radio.on_title -> {_core.fn_name(fn)}()", e)


def _dispatch_state(text):
    st, _, message = str(text).partition(": ")
    for owner, fn in list(_state_listeners):
        try:
            fn(st, message)
        except _core.ERRORS as e:
            _core.report(owner, f"radio.on_state -> {_core.fn_name(fn)}()", e)


_Radio.onTitle(_dispatch_title)
_Radio.onState(_dispatch_state)
