"""Radio HUD - internet radio with a now-playing display. Client only (no main.py).

* `/radio play <url>` (built into PyFabric) starts any Icecast / Shoutcast / MP3 stream.
* Press R to stop the radio, or to start your favourite station again.
* The current song is shown in the top-right corner.

Put your favourite stream in config/pymods/radio_hud.json ("station"), or just use /radio play once:
R then resumes the last station you played.

Shows: the pyfabric.radio API, radio events, a config file, HUD drawing aligned to the right edge.
"""
from pyfabric import client, radio, storage

cfg = storage.config({"station": "", "show_hud": True})


@client.on_key("Start/stop radio", "R")
def toggle(mc):
    if radio.is_playing():
        radio.stop()
        client.actionbar("Radio off")
        return
    try:
        radio.play(cfg["station"] or None)          # None = the last station played
    except ValueError:
        client.tell("&eNo station yet - use &f/radio play <stream url>&e, "
                    "or set \"station\" in config/pymods/radio_hud.json")


@radio.on_state
def state_changed(state, message):
    if state == "FAILED":
        client.tell(f"&cRadio HUD: the station failed ({message})")


@client.hud
def draw(g, mc):
    if not cfg["show_hud"] or not radio.is_playing():
        return
    if radio.state() == "PLAYING":
        text = "♪ " + (radio.now_playing() or radio.station() or "Live radio")
    else:
        text = "♪ " + radio.state().capitalize() + "..."
    if len(text) > 60:
        text = text[:57] + "..."
    width = client.text_width(text)
    right = g.guiWidth() - 4
    client.fill(g, right - width - 6, 2, right, 15, 0x90000000)
    client.draw_text(g, text, right - width - 3, 5, color=0x55FFFF)
