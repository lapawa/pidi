"""
Get song info.
"""
import time
import shutil
import select
from pkg_resources import iter_entry_points

import mpd
import untangle
from base64 import decodebytes
from .fifo import FIFO

from . import brainz
from . import util


def get_client_types():
    """Enumerate the pidi.plugin.client entry point and return installed client types."""
    client_types = {
        'mpd': ClientMPD,
        'ssnc': ClientShairportSync
    }

    for entry_point in iter_entry_points("pidi.plugin.client"):
        try:
            plugin = entry_point.load()
            client_types[plugin.option_name] = plugin
        except (ModuleNotFoundError, ImportError) as err:
            print("Error loading client plugin {entry_point}: {err}".format(
                entry_point=entry_point,
                err=err
            ))

    return client_types


class ClientShairportSync():
    def __init__(self, args):
        self.title = ""
        self.artist = ""
        self.album = ""
        self.time = 100
        self.state = ""
        self.volume = 0
        self.random = 0
        self.repeat = 0
        self.shuffle = 0
        self.album_art = ""
        self.pending_art = False

        self._update_pending = False

        self.fifo = FIFO(args.pipe, eol="</item>", skip_create=True)

    def add_args(argparse):  # pylint: disable=no-self-argument
        argparse.add_argument("--pipe",
                    help="Pipe file for shairport sync metadata.",
                    default="/tmp/shairport-sync-metadata")

    def status(self):
        return {
            "random": self.random,
            "repeat": self.repeat,
            "state": self.state,
            "volume": self.volume,
            "shuffle": self.shuffle
        }

    def currentsong(self):
        self._update_pending = False
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "time": self.time
        }

    def get_art(self, cache_dir, size):
        """Get the album art."""
        if self.album_art == "":
            util.bytes_to_file(util.default_album_art(), cache_dir / "current.jpg")
            return
    
        util.bytes_to_file(self.album_art, cache_dir / "current.jpg")

        self.pending_art = False

    def update_pending(self):
        attempts = 0
        while True:
            data = self.fifo.read()
            if data is None or len(data) == 0:
                attempts += 1
                if attempts > 100:
                    return
            else:
                self._parse_data(data)
                self._update_pending = True
    
        return self._update_pending

    def _parse_data(self, data):
        try:
            data = untangle.parse(data)
        except:
            print("ClientShairportSync: failed to parse XML")
            return

        dtype = bytes.fromhex(data.item.type.cdata).decode("ascii")
        dcode = bytes.fromhex(data.item.code.cdata).decode("ascii")
        
        data = getattr(data.item, "data", None)

        if data is not None:
            encoding = data["encoding"]
            data = data.cdata
            if encoding == "base64":
                data = decodebytes(data.encode("ascii"))

        if (dtype, dcode) == ("ssnc", "PICT"):
            self.pending_art = True
            self.album_art = data

        if (dtype, dcode) == ("core", "asal"):  # Album
            self.album = data.decode("utf-8")

        if (dtype, dcode) == ("core", "asar"):  # Artist
            self.artist = data.decode("utf-8")

        if (dtype, dcode) == ("core", "minm"):  # Song Name / Item
            self.title = data.decode("utf-8")

        if (dtype, dcode) == ("ssnc", "prsm"):
            self.state = "play"

        if (dtype, dcode) == ("ssnc", "pend"):
            self.state = "stop"

        print(dtype, dcode)


class ClientMPD():
    """Client for MPD and MPD-like (such as Mopidy) music back-ends."""
    def __init__(self, args=None):
        """Initialize mpd."""
        self._client = mpd.MPDClient()

        try:
            self._client.connect(args.server, args.port)

        except ConnectionRefusedError:
            raise RuntimeError("error: Connection refused to mpd/mopidy.")

        self._client.send_idle('player')

    def add_args(argparse):  # pylint: disable=no-self-argument
        """Expand argparse instance with client-specific args."""
        argparse.add_argument("--port",
                    help="Use a custom mpd port.",
                    default=6600)

        argparse.add_argument("--server",
                    help="Use a remote server instead of localhost.",
                    default="localhost")

    def currentsong(self):
        """Return current song details."""
        self._client.noidle()
        result = self._client.currentsong()  # pylint: disable=no-member
        self._client.send_idle('player')
        return result

    def status(self):
        """Return current status details."""
        self._client.noidle()
        result = self._client.status()  # pylint: disable=no-member
        self._client.send_idle('player')
        return result

    def update_pending(self, timeout=0.1):
        """Determine if anything has changed on the server."""
        result = select.select([self._client], [], [], timeout)[0]
        return self._client in result

    def get_art(self, cache_dir, size):
        """Get the album art."""
        song = self.currentsong()
        if len(song) < 2:
            print("album: Nothing currently playing.")
            util.bytes_to_file(util.default_album_art(), cache_dir / "current.jpg")
            return

        artist = song.get('artist')
        title = song.get('title')
        album = song.get('album', title)
        file_name = "{artist}_{album}_{size}.jpg".format(
            artist=artist,
            album=album,
            size=size
        ).replace("/", "")
        file_name = cache_dir / file_name

        if file_name.is_file():
            shutil.copy(file_name, cache_dir / "current.jpg")
            print("album: Found cached art.")

        else:
            print("album: Downloading album art...")

            brainz.init()
            album_art = brainz.get_cover(song, size)

            if not album_art:
                album_art = util.default_album_art()

            util.bytes_to_file(album_art, cache_dir / file_name)
            util.bytes_to_file(album_art, cache_dir / "current.jpg")

            print("album: Swapped art to {artist}, {title}.".format(
                artist=artist,
                title=title
            ))
