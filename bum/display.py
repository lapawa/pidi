"""
Display Output Classes.
"""
import os
import time
import math
from pkg_resources import iter_entry_points


def get_display_types():
    display_types = {
        'dummy': DisplayDummy,
        'mpv': DisplayMPV,
    }

    for ep in iter_entry_points("bum_plugin_display"):
        try:
            plugin = ep.load()
            display_types[plugin.option_name] = plugin
        except (ModuleNotFoundError, ImportError) as e:
            print(f"Error loading display plugin {ep}: {e}")

    return display_types


class Display():
    def __init__(self, args=None):
        self._size = args.size
        self._title = ''
        self._shuffle = False
        self._repeat = False
        self._state = ''
        self._volume = 0
        self._progress = 0
        self._elapsed = 0

        self._title = ''
        self._album = ''
        self._artist = ''

    def update_album_art(self, input_file):
        pass

    def update_overlay(self, shuffle, repeat, state, volume, progress, elapsed, title, album, artist):
        self._shuffle = shuffle
        self._repeat = repeat
        self._state = state
        self._volume = volume
        self._progress = progress
        self._elapsed = elapsed
        self._title = title
        self._album = album
        self._artist = artist

    def redraw(self):
        pass

    def add_args(argparse):
        pass


class DisplayDummy(Display):
    pass


class DisplayMPV(Display):
    def __init__(self, args):
        global mpv
        import mpv
        Display.__init__(self, args)
        self._player = mpv.MPV(start_event_thread=False)
        self._player["force-window"] = "immediate"
        self._player["keep-open"] = "yes"
        self._player["geometry"] = f"{self._size}x{self._size}"
        self._player["autofit"] = f"{self._size}x{self._size}"
        self._player["title"] = "bum"

    def update_album_art(self, input_file):
        self._art = str(input_file)

    def redraw(self):
        self._player.player(self._art)
