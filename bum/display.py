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

def text_in_rect(image, text, font, rect, line_spacing=1.1):
    canvas = ImageDraw.Draw(image, 'RGBA')

    width = rect[2] - rect[0]
    height = rect[3] - rect[1]

    # Given a rectangle, reflow and scale text to fit, centred
    while font.size > 0:
        space_width = font.getsize(" ")[0]
        line_height = int(font.size * line_spacing)
        max_lines = math.floor(height / line_height)
        lines = []

        # Determine if text can fit at current scale.
        words = text.split(" ")

        while len(lines) < max_lines and len(words) > 0:
            line = []

            while len(words) > 0 and font.getsize(" ".join(line + [words[0]]))[0] <= width:
                line.append(words.pop(0))

            lines.append(" ".join(line))

        if(len(lines)) <= max_lines and len(words) == 0:
            # Solution is found, render the text.
            y = int(rect[1] + (height / 2) - (len(lines) * line_height / 2) - (line_height - font.size) / 2)

            bounds = [rect[2], y, rect[0], y + len(lines) * line_height]

            for line in lines:
                line_width = font.getsize(line)[0]
                x = int(rect[0] + (width / 2) - (line_width / 2))
                bounds[0] = min(bounds[0], x)
                bounds[2] = max(bounds[2], x + line_width)
                canvas.text((x, y), line, font=font)
                y += line_height

            return tuple(bounds)

        font = ImageFont.truetype(font.path, font.size - 1)

def draw_progress_bar(image, progress, max_progress, rect, colour):
    canvas = ImageDraw.Draw(image, 'RGBA')

    unfilled_opacity = 0.5  # Factor to scale down colour/opacity of unfilled bar.

    # Calculate bar widths.
    rect = tuple(rect)  # Space which bar occupies.
    full_width = rect[3] - rect[0]
    bar_width = int((progress / max_progress) * full_width)
    progress_rect = (rect[0], rect[1], rect[0] + bar_width, rect[3])

    # Knock back unfilled part of bar.
    unfilled_colour = tuple(int(c * unfilled_opacity) for c in colour)

    # Draw bars.
    canvas.rectangle(rect, unfilled_colour)
    canvas.rectangle(progress_rect, colour)

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


class DisplayPIL(Display):
    """Base class for PIL-based image displays."""
    def __init__(self, args=None):
        global Image, ImageDraw, ImageFilter, ImageFont, ConnectionIII

        Display.__init__(self, args)

        from fonts.ttf import RobotoMedium as UserFont
        from PIL import ImageTk, Image, ImageDraw, ImageFilter, ImageFont

        self._downscale = 2
        self._font = ImageFont.truetype(UserFont, 42 * self._downscale)
        self._font_small = ImageFont.truetype(UserFont, 20 * self._downscale)
        self._font_medium = ImageFont.truetype(UserFont, 25 * self._downscale)

        self._image = Image.new('RGBA', (self._size * self._downscale, self._size * self._downscale), (0, 0, 0))
        self._overlay = Image.new('RGBA', (self._size * self._downscale, self._size * self._downscale))
        self._draw = ImageDraw.Draw(self._overlay, 'RGBA')
        self._draw.fontmode = '1'
        self._output_image = None
        self._last_change = time.time()
        self._blur = args.blur_album_art

    def update_album_art(self, input_file):
        Display.update_album_art(self, input_file)
        new = Image.open(input_file).resize((self._size * self._downscale, self._size * self._downscale))
        if self._blur:
            new = new.convert('RGBA').filter(ImageFilter.GaussianBlur(radius=5*self._downscale))
        self._image.paste(new, (0, 0))
        self._last_change = time.time()

    def redraw(self):
        # Initial setup
        self._draw.rectangle((0, 0, self._size * self._downscale, self._size * self._downscale), (0, 0, 0, 40))
        margin = 5
        width = self._size * self._downscale

        # Song progress bar
        progress = self._progress
        max_progress = 1.0
        colour = (225, 225, 225, 225)
        rect = (5, 220, 235, 235)
        scaled_rect = (v * self._downscale for v in rect)
        draw_progress_bar(self._overlay, progress, max_progress, scaled_rect, colour)

        # Volume bar
        volume = self._volume
        max_volume = 100
        colour = (225, 225, 225, 165)
        rect = (5, 185, 205, 190)
        scaled_rect = (v * self._downscale for v in rect)
        draw_progress_bar(self._overlay, volume, max_volume, scaled_rect, colour)

        # Artist
        artist = self._artist

        if ";" in artist:
            artist = artist.replace(";", ", ") # Swap out weird semicolons for commas

        box = text_in_rect(self._overlay, artist, self._font_medium, (margin, 5 * self._downscale, width - margin, 35 * self._downscale))

        # Album
        text_in_rect(self._overlay, self._album, self._font_small, (50 * self._downscale, box[3], width - (50 * self._downscale), 70 * self._downscale))

        # Song title
        text_in_rect(self._overlay, self._title, self._font, (margin, 95 * self._downscale, width - margin, 170 * self._downscale))

        # Overlay control icons
        image_dir = os.getcwd() + "/images/"
        controls = Image.new('RGBA', (self._size * self._downscale, self._size * self._downscale))

        if self._state == "play":
            controls_img = Image.open(image_dir + "controls-pause.png")
        else:
            controls_img = Image.open(image_dir + "controls-play.png")

        controls.paste(controls_img, (0, 0))

        # Render image
        image_2x = Image.alpha_composite(self._image, self._overlay)
        image_2x = Image.alpha_composite(image_2x, controls)
        image_1x = image_2x.resize((int(width / self._downscale), int(width / self._downscale)), resample=Image.LANCZOS)
        self._output_image = image_1x

    def add_args(argparse):
        Display.add_args(argparse)

        argparse.add_argument("--blur-album-art",
                              help="Apply blur effect to album art.",
                              action='store_true')


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
