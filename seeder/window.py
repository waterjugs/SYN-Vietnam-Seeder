"""The window you get by double-clicking SynSeeder.exe."""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

from . import __version__, crcon, instance, schedule
from .config import Config, app_dir
from .game import Game

log = logging.getLogger(__name__)

HOURS = [f"{h:02d}" for h in range(24)]
MINUTES = [f"{m:02d}" for m in range(0, 60, 5)]

# Images drawn by tools/make_assets.py: 100% scaling in assets/, 200% in assets/2x.
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets"
FONT_FILES = ("Inter-Regular.ttf", "Inter-Bold.ttf")  # in assets/fonts, under the SIL Open Font License

# Night sky warming to dusk, carried down through the window, with amber for first light.
NIGHT = "#0C1823"        # top of the header's sky; the title bar on Windows 11
TWILIGHT = "#151A27"     # window body
SLATE = "#1F2335"        # fields, list backgrounds
EDGE = "#363A52"         # hairlines
HAZE = "#ECE3D0"         # main text
MIST = "#9C98B0"         # secondary text
FIRST_LIGHT = "#F2A443"  # the action to take, and a server that still needs seeding
PADDY = "#86C17A"        # a seeded server
FLARE = "#F27A62"        # errors
INK = "#1A140C"          # text on the amber button
TRACK = "#272B3F"        # empty part of the player meter

PLAYERS_MAX = 100
MARGIN = 24              # left and right of everything under the header, at 100% scaling
SERVER_REFRESH_MS = 30_000  # how often the player count is fetched again while the window is open


def _start_seed_process() -> None:
    program, arguments = schedule.seed_command()
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0  # detached, new group
    subprocess.Popen([program, *arguments.split()], creationflags=flags, close_fds=True)


def _make_dpi_aware() -> None:
    """Draw at the screen's real resolution instead of being stretched (blurry) by Windows.

    System-aware rather than per-monitor: Tk sizes its fonts once, at startup.
    """
    if os.name == "nt":
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass


def _load_fonts() -> None:
    """Let this process use the Inter that ships in assets/fonts, without installing it (Windows).

    Windows doesn't come with Inter. If loading fails, pick_font falls back to Segoe UI.
    """
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    try:
        gdi32 = ctypes.WinDLL("gdi32")  # own copy, own prototype
        gdi32.AddFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
        gdi32.AddFontResourceExW.restype = ctypes.c_int
        for name in FONT_FILES:
            if not gdi32.AddFontResourceExW(str(ASSETS / "fonts" / name), 0x10, None):  # FR_PRIVATE
                log.debug("Couldn't load %s", name)
    except (AttributeError, OSError, ctypes.ArgumentError):
        log.debug("Couldn't load the fonts", exc_info=True)


def _dress_for_windows(root: tk.Tk) -> None:
    """Sharp icons at the screen's scaling, and a dark title bar (Windows 10 1809 and later)
    that Windows 11 also colours like the header's sky.

    Tk can't read the sizes in the .ico, so it would stretch the 16 px icon for the taskbar.
    Only looks: if any of it fails, the window opens as it is.
    """
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    def colorref(colour: str) -> int:
        r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
        return r | g << 8 | b << 16

    try:
        user32, dwmapi = ctypes.WinDLL("user32"), ctypes.WinDLL("dwmapi")  # own copies, own prototypes
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int,
                                      ctypes.c_int, wintypes.UINT]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SendMessageW.restype = wintypes.LPARAM
        dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
        hwnd = user32.GetParent(root.winfo_id())  # Tk's outer window, the one with the title bar

        # ICON_SMALL at SM_CXSMICON, ICON_BIG at SM_CXICON, each read from the .ico at that size
        for which, metric in ((0, 49), (1, 11)):
            size = user32.GetSystemMetrics(metric)
            icon = user32.LoadImageW(None, str(ASSETS / "synseeder.ico"), 1, size, size, 0x10)  # LR_LOADFROMFILE
            if icon:
                user32.SendMessageW(hwnd, 0x80, which, icon)  # WM_SETICON

        def set_attribute(attribute: int, value: int) -> int:
            value = ctypes.c_int(value)
            return dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))

        if set_attribute(20, 1):  # DWMWA_USE_IMMERSIVE_DARK_MODE; Windows 10 before 20H1 calls it 19
            set_attribute(19, 1)
        set_attribute(35, colorref(NIGHT))  # DWMWA_CAPTION_COLOR, Windows 11
        set_attribute(36, colorref(HAZE))   # DWMWA_TEXT_COLOR, Windows 11
    except (AttributeError, OSError, ctypes.ArgumentError):
        log.debug("Couldn't theme the window", exc_info=True)


def _resized(path: Path, factor: float) -> str:
    """The PNG at ``path`` resized by ``factor``, as base64 PNG data for tk.PhotoImage."""
    import cv2
    import numpy as np

    # imdecode copes with non-ASCII paths (the exe unpacks under the user's name); imread doesn't
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    height, width = image.shape[:2]
    size = (max(1, round(width * factor)), max(1, round(height * factor)))
    method = cv2.INTER_AREA if factor < 1 else cv2.INTER_CUBIC
    if image.shape[2] == 4:  # resize with premultiplied alpha so edges don't go dark
        alpha = image[:, :, 3:].astype(np.float32) / 255
        colour = cv2.resize(image[:, :, :3] * alpha, size, interpolation=method)
        alpha = cv2.resize(alpha, size, interpolation=method)[:, :, None].clip(0, 1)
        colour = np.divide(colour, alpha, out=np.zeros_like(colour), where=alpha > 0)
        image = np.dstack([colour, alpha * 255]).round().clip(0, 255).astype(np.uint8)
    else:
        image = cv2.resize(image, size, interpolation=method)
    return base64.b64encode(cv2.imencode(".png", image)[1].tobytes()).decode("ascii")


def pick_font(root: tk.Misc, size: int, *candidates: tuple[str, str]) -> tuple:
    """First installed (family, weight) of the candidates, as a Tk font tuple.

    The bundled Inter comes first, then what Windows 10/11 has; the others keep it close elsewhere.
    """
    installed = set(tkfont.families(root))
    for family, weight in candidates:
        if family in installed:
            return (family, size, weight)
    return ("TkDefaultFont", size, candidates[-1][1])


class SetupWindow:
    def __init__(self, config: Config):
        self.config = config
        _make_dpi_aware()
        _load_fonts()
        self.root = tk.Tk()
        self.root.attributes("-alpha", 0.0)  # hidden until it's placed and themed, so nothing flashes
        self.root.title("SYN Vietnam Seeder")
        self.root.resizable(False, False)
        self.root.configure(background=TWILIGHT)
        # 1.0 at 100% Windows scaling, 1.5 at 150%...; fonts follow by themselves, pixels and images don't.
        scale = self.root.winfo_fpixels("1i") / 96
        self.scale = 1.0 if scale < 1.1 else 2.0 if abs(scale - 2) < 0.05 else scale
        self._images: dict[str, tk.PhotoImage] = {}
        self._fetch: threading.Thread | None = None  # the latest player-count fetch
        self._count: int | None = None  # the player count on show
        self._fonts()
        self._style()
        self._icon()
        px = self.px

        header = self._image("header")
        tk.Label(self.root, image=header, borderwidth=0, highlightthickness=0,
                 background=TWILIGHT).grid(row=0, column=0, sticky="nw")
        self.content_width = header.width() - 2 * px(MARGIN)  # so nothing below is wider than the picture
        body = ttk.Frame(self.root, padding=(px(MARGIN), px(18), px(MARGIN), px(14)))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        # The server, and how far it is from seeded
        ttk.Label(body, text=config.server_name, font=self.font_semibold).grid(row=0, column=0, sticky="w")
        line = ttk.Frame(body)
        line.grid(row=1, column=0, sticky="we", pady=(px(2), px(6)))
        line.columnconfigure(1, weight=1)
        self.count = ttk.Label(line, text="0", font=self.font_count, padding=(0, 0, px(6), 0))
        line.rowconfigure(0, minsize=self.count.winfo_reqheight())  # same height before the count arrives
        self.server = ttk.Label(line, text="Checking the server...", style="Muted.TLabel")
        self.server.grid(row=0, column=1, sticky="sw", pady=(0, self._baseline_lift(self.font_body)))
        self.need = ttk.Label(line, text="", font=self.font_semibold)
        self.need.grid(row=0, column=2, sticky="se", pady=(0, self._baseline_lift(self.font_semibold)))
        self.meter = tk.Canvas(body, width=self.content_width, height=px(32), background=TWILIGHT,
                               highlightthickness=0, borderwidth=0)
        self.meter.grid(row=2, column=0, sticky="w")
        self._draw_meter(None)

        # When and how to seed: a row each, the setting on the left and its control against the right edge
        settings = ttk.Frame(body)
        settings.grid(row=3, column=0, sticky="we", pady=(px(10), 0))
        settings.columnconfigure(0, weight=1)
        for r in (0, 2, 4, 6):  # hairlines above, between and below the rows
            tk.Frame(settings, height=max(1, px(1)), background=EDGE).grid(row=r, column=0, columnspan=2,
                                                                       sticky="we")
        for r in (1, 3, 5):
            settings.rowconfigure(r, minsize=px(46))

        hour, minute = config.start_time.split(":")
        ttk.Label(settings, text="Seed every day at").grid(row=1, column=0, sticky="w")
        when = ttk.Frame(settings)
        when.grid(row=1, column=1, sticky="e")
        self.clock = ttk.Label(when, style="Muted.TLabel")  # the pickers are 24-hour; this says AM or PM
        self.clock.grid(row=0, column=0, padx=(0, px(12)))
        self.hour = ttk.Combobox(when, values=HOURS, width=3, state="readonly", style="Dawn.TCombobox",
                                 font=self.font_body)
        self.hour.set(hour)
        self.hour.grid(row=0, column=1)
        ttk.Label(when, text=":", font=self.font_semibold).grid(row=0, column=2, padx=px(6))
        self.minute = ttk.Combobox(when, values=MINUTES, width=3, state="readonly", style="Dawn.TCombobox",
                                   font=self.font_body)
        self.minute.set(minute if minute in MINUTES else "00")
        self.minute.grid(row=0, column=3)
        for picker in (self.hour, self.minute):
            picker.bind("<<ComboboxSelected>>", lambda _: self._show_clock())
        self._show_clock()

        ttk.Label(settings, text="Game launcher").grid(row=3, column=0, sticky="w")
        self.launcher = tk.StringVar(value=config.launcher)
        chips = ttk.Frame(settings)
        chips.grid(row=3, column=1, sticky="e")
        ttk.Radiobutton(chips, text="Steam", variable=self.launcher, value="steam", style="Chip.TRadiobutton",
                        width=6).grid(row=0, column=0, padx=(0, px(6)))
        ttk.Radiobutton(chips, text="Epic", variable=self.launcher, value="epic", style="Chip.TRadiobutton",
                        width=6).grid(row=0, column=1)

        self.enabled = tk.BooleanVar(value=schedule.is_scheduled())
        ttk.Checkbutton(settings, text="Seed automatically", variable=self.enabled, style="Dawn.TCheckbutton"
                        ).grid(row=5, column=0, columnspan=2, sticky="we")  # the whole row ticks it

        # Actions: three equal buttons across the width
        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, sticky="we", pady=(px(20), 0))
        for c in (0, 2, 4):
            buttons.columnconfigure(c, weight=1, uniform="button")
        for c in (1, 3):
            buttons.columnconfigure(c, minsize=px(8))
        ttk.Button(buttons, text="Save", command=self.save, style="Primary.TButton").grid(
            row=0, column=0, sticky="we")
        ttk.Button(buttons, text="Seed now", command=self.seed_now, style="Dawn.TButton").grid(
            row=0, column=2, sticky="we")
        ttk.Button(buttons, text="Stop seeding", command=self.stop, style="Dawn.TButton").grid(
            row=0, column=4, sticky="we")

        self.status = ttk.Label(body, text="Two\nlines", wraplength=self.content_width - 4, style="Muted.TLabel",
                                justify="center", anchor="center")  # ttk puts 2 px either side of the text
        self.status.grid(row=5, column=0, sticky="nwe", pady=(px(12), 0))
        body.rowconfigure(5, minsize=px(12) + self.status.winfo_reqheight())  # keeps two lines, so nothing jumps
        self.status.config(text=self._schedule_text())

        tk.Frame(body, height=max(1, px(1)), background=EDGE).grid(row=6, column=0, sticky="we",
                                                                   pady=(px(14), px(10)))
        footer = ttk.Frame(body)
        footer.grid(row=7, column=0, sticky="we")
        for c in (0, 2):  # equal sides, so the middle is centred
            footer.columnconfigure(c, weight=1, uniform="side")
        ttk.Label(footer, text=f"v{__version__}", style="Small.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(footer, text="Ctrl+Alt+End stops a run", style="Small.TLabel").grid(row=0, column=1)
        log_link = ttk.Label(footer, text="Open log", style="Link.TLabel", cursor="hand2")
        log_link.grid(row=0, column=2, sticky="e")
        log_link.bind("<Button-1>", lambda _: self.open_log())
        log_link.bind("<Enter>", lambda _: log_link.configure(style="LinkHover.TLabel"))
        log_link.bind("<Leave>", lambda _: log_link.configure(style="Link.TLabel"))

        self._show()
        self._refresh_server()

    # The look

    def px(self, n: float) -> int:
        """Pixels at the screen's scaling for ``n`` pixels at 100%."""
        return round(n * self.scale)

    def _image(self, name: str) -> tk.PhotoImage:
        if name not in self._images:
            if self.scale == 1:
                image = tk.PhotoImage(master=self.root, file=str(ASSETS / f"{name}.png"))
            elif self.scale == 2:
                image = tk.PhotoImage(master=self.root, file=str(ASSETS / "2x" / f"{name}.png"))
            else:
                image = tk.PhotoImage(master=self.root, data=_resized(ASSETS / "2x" / f"{name}.png", self.scale / 2))
            self._images[name] = image
        return self._images[name]

    def _icon(self) -> None:
        # On Windows, _dress_for_windows swaps in the .ico's own size for the screen's scaling.
        self.root.iconphoto(True, *(tk.PhotoImage(master=self.root, file=str(ASSETS / f"icon-{s}.png"))
                                    for s in (48, 32, 16)))

    def _show(self) -> None:
        """Centres the window, themes its title bar, then makes it visible."""
        self.root.update_idletasks()
        width, height = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 3)
        self.root.geometry(f"+{x}+{y}")
        self.root.update_idletasks()  # moves it now, while it's still invisible
        _dress_for_windows(self.root)
        self.root.attributes("-alpha", 1.0)

    def _fonts(self) -> None:
        ui = (("Inter", "normal"), ("Segoe UI", "normal"), ("DejaVu Sans", "normal"))
        bold = (("Inter", "bold"), ("Segoe UI Semibold", "normal"), ("DejaVu Sans", "bold"))
        self.font_body = pick_font(self.root, 10, *ui)
        self.font_small = pick_font(self.root, 9, *ui)
        self.font_semibold = pick_font(self.root, 10, *bold)
        self.font_count = pick_font(self.root, 14, *bold)
        self.font_link = self.font_small + ("underline",)

    def _baseline_lift(self, font: tuple) -> int:
        """How far to raise text in this font, hung from the count line's bottom, to sit on the count's baseline."""
        def descent(f: tuple) -> int:
            return tkfont.Font(root=self.root, font=f).metrics("descent")
        return max(0, descent(self.font_count) - descent(font))

    def _style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")  # the native Windows theme ignores colours
        img, px = self._image, self.px
        style.configure(".", background=TWILIGHT, foreground=HAZE, font=self.font_body,
                        bordercolor=EDGE, lightcolor=TWILIGHT, darkcolor=TWILIGHT, troughcolor=SLATE,
                        focuscolor=EDGE, selectbackground=FIRST_LIGHT, selectforeground=INK)
        style.configure("TLabel", background=TWILIGHT, foreground=HAZE)
        style.configure("Muted.TLabel", foreground=MIST)
        style.configure("Small.TLabel", foreground=MIST, font=self.font_small)
        style.configure("Link.TLabel", foreground=FIRST_LIGHT, font=self.font_link)
        style.configure("LinkHover.TLabel", foreground="#F7C27A", font=self.font_link)

        # Buttons: 9-slice images, so the corners stay round at any width
        for name, prefix, fg in (("Primary", "btn-primary", INK), ("Dawn", "btn", HAZE)):
            style.element_create(f"{name}.border", "image", img(prefix),
                                 ("disabled", img(f"{prefix}-disabled")), ("pressed", img(f"{prefix}-pressed")),
                                 ("active", img(f"{prefix}-hover")), ("focus", img(f"{prefix}-focus")),
                                 border=px(8), padding=0, sticky="nsew")
            style.layout(f"{name}.TButton", [(f"{name}.border", {"sticky": "nsew", "children": [
                ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})])
            style.configure(f"{name}.TButton", foreground=fg, font=self.font_semibold, padding=(px(18), px(6)),
                            anchor="center", width=0)
            style.map(f"{name}.TButton", foreground=[("disabled", MIST)])

        # Steam / Epic as two chips
        style.element_create("Chip.border", "image", img("chip"), ("selected", "focus", img("chip-on-focus")),
                             ("selected", img("chip-on")), ("active", img("chip-hover")),
                             ("focus", img("chip-focus")), border=px(6), padding=0, sticky="nsew")
        style.layout("Chip.TRadiobutton", [("Chip.border", {"sticky": "nsew", "children": [
            ("Radiobutton.padding", {"sticky": "nsew", "children": [("Radiobutton.label", {"sticky": "nsew"})]})]})])
        style.configure("Chip.TRadiobutton", foreground=MIST, padding=(px(12), px(4)), anchor="center")
        style.map("Chip.TRadiobutton", foreground=[("selected", HAZE), ("active", HAZE)])

        # Seed automatically
        style.element_create("Dawn.Checkbutton.indicator", "image", img("check-off"),
                             ("selected", "active", img("check-on-hover")), ("selected", img("check-on")),
                             ("active", img("check-off-hover")), sticky="w")
        style.layout("Dawn.TCheckbutton", [("Checkbutton.padding", {"sticky": "nsew", "children": [
            ("Dawn.Checkbutton.indicator", {"side": "right", "sticky": ""}),  # box at the right, label at the left
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                ("Checkbutton.label", {"sticky": "nsew"})]})]})])
        style.configure("Dawn.TCheckbutton", padding=(0, px(2), px(1), px(2)), focuscolor="#B88A4A")
        style.map("Dawn.TCheckbutton", background=[("active", TWILIGHT)], foreground=[("active", HAZE)])

        # Hour and minute pickers, and their drop-down lists
        style.element_create("Dawn.Combobox.field", "image", img("field"), ("focus", img("field-focus")),
                             ("active", img("field-hover")), ("pressed", img("field-hover")),
                             border=px(6), padding=0, sticky="nsew")
        style.element_create("Dawn.Combobox.downarrow", "image", img("chevron"), sticky="")
        style.layout("Dawn.TCombobox", [("Dawn.Combobox.field", {"sticky": "nsew", "children": [
            ("Dawn.Combobox.downarrow", {"side": "right", "sticky": "ns"}),
            ("Combobox.padding", {"expand": "1", "sticky": "nsew", "children": [
                ("Combobox.textarea", {"sticky": "nsew"})]})]})])
        style.configure("Dawn.TCombobox", foreground=HAZE, padding=(px(10), px(4), 0, px(4)),
                        selectbackground=SLATE, selectforeground=HAZE, fieldbackground=SLATE)
        style.map("Dawn.TCombobox", foreground=[("readonly", HAZE)],
                  selectbackground=[("readonly", SLATE)], selectforeground=[("readonly", HAZE)])
        self.root.option_add("*TCombobox*Listbox.background", SLATE)
        self.root.option_add("*TCombobox*Listbox.foreground", HAZE)
        self.root.option_add("*TCombobox*Listbox.selectBackground", FIRST_LIGHT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", INK)
        self.root.option_add("*TCombobox*Listbox.font", self.font_body)
        self.root.option_add("*TCombobox*Listbox.borderWidth", px(4))  # flat, so it reads as inner padding
        self.root.option_add("*TCombobox*Listbox.highlightThickness", 0)
        self.root.option_add("*TCombobox*Listbox.activeStyle", "none")
        style.configure("ComboboxPopdownFrame", background=SLATE, bordercolor=EDGE, relief="solid",
                        borderwidth=1)
        style.configure("Vertical.TScrollbar", background=EDGE, troughcolor=SLATE, arrowcolor=MIST,
                        bordercolor=SLATE, lightcolor=EDGE, darkcolor=EDGE, gripcount=0, arrowsize=px(11))
        style.map("Vertical.TScrollbar", background=[("active", "#4D5270")])

    def _draw_meter(self, count: int | None) -> None:
        """Thin bar of players out of 100, with a tick where the server counts as seeded."""
        c, px = self.meter, self.px
        c.delete("all")
        width, y, thick = self.content_width, px(7), px(6)
        left, right = thick / 2, width - thick / 2
        c.create_line(left, y, right, y, fill=TRACK, width=thick, capstyle="round")
        if count:
            seeded = count >= self.config.seeded_threshold
            x = left + (right - left) * min(count, PLAYERS_MAX) / PLAYERS_MAX
            c.create_line(left, y, x, y, fill=PADDY if seeded else FIRST_LIGHT, width=thick, capstyle="round")
        tick = left + (right - left) * min(max(self.config.seeded_threshold, 0), PLAYERS_MAX) / PLAYERS_MAX
        c.create_line(tick, px(1), tick, px(13), fill=HAZE, width=px(2))
        label = c.create_text(tick, px(15), text=f"Seeded at {self.config.seeded_threshold}", anchor="n",
                              fill=MIST, font=self.font_small)
        x0, _, x1, _ = c.bbox(label)
        c.move(label, max(0, -x0) - max(0, x1 - width), 0)  # near either end, kept on the meter

    def _show_clock(self) -> None:
        try:
            hour = int(self.hour.get())
        except ValueError:  # a hand-edited settings file
            self.clock.config(text="")
            return
        self.clock.config(text=f"{hour % 12 or 12}:{self.minute.get()} {'AM' if hour < 12 else 'PM'}")

    def _show_server(self, count: int | None) -> None:
        self._count = count
        if count is None:
            self.count.grid_remove()
            self.server.config(text="Couldn't reach the server stats.")
            self.need.config(text="")
        else:
            missing = self.config.seeded_threshold - count
            self.count.config(text=str(count))
            self.count.grid(row=0, column=0, sticky="sw")
            self.server.config(text=f"of {PLAYERS_MAX} players right now")
            self.need.config(text=f"Needs {missing} more" if missing > 0 else "Seeded",
                             foreground=FIRST_LIGHT if missing > 0 else PADDY)
        self._draw_meter(count)

    # What the window does

    def _schedule_text(self) -> str:
        if schedule.is_scheduled():
            return (f"Seeds every day at {self.config.start_time}. Leave the PC on, signed in and "
                    "unlocked; if it's asleep it runs when it wakes.")
        return "Not scheduled. Tick “Seed automatically” and Save."

    def _refresh_server(self) -> None:
        # One fetch at a time, so a slow one can't land after a newer count and replace it.
        if self._fetch is None or not self._fetch.is_alive():
            self._fetch = threading.Thread(target=self._load_server, daemon=True)
            self._fetch.start()
        self.root.after(SERVER_REFRESH_MS, self._refresh_server)

    def _load_server(self) -> None:
        status = crcon.fetch(self.config.crcon_url)
        count = status.player_count if status else None
        self.root.after(0, lambda: self._show_server(count))

    def save(self) -> None:
        self.config.start_time = f"{self.hour.get()}:{self.minute.get()}"
        self.config.launcher = self.launcher.get()
        self.config.save()
        try:
            if self.enabled.get():
                schedule.schedule(self.config.start_time)
            else:
                schedule.unschedule()
        except (OSError, RuntimeError) as exc:
            log.exception("Scheduling failed")
            self.status.config(text=f"Couldn't set up the schedule: {exc}", foreground=FLARE)
            return
        self.status.config(text="Saved. " + self._schedule_text(), foreground=MIST)

    def seed_now(self) -> None:
        if instance.seeding_processes():
            self.status.config(text="Already seeding.")
            return
        self.save()
        # A run stops at once in these cases, so say why here rather than "started".
        if self._count is not None and self._count >= self.config.seeded_threshold:
            self.status.config(text=f"The server is already seeded ({self._count} players), so there's "
                                    "nothing to do.")
            return
        if Game(self.config).running():
            self.status.config(text="The game is already open. Close it first: Seed now won't take over "
                                    "a game you're playing.")
            return
        _start_seed_process()
        self.status.config(text="Seeding started. The game will open shortly; leave the "
                                "mouse and keyboard alone while it joins.")

    def stop(self) -> None:
        if instance.stop_seeding():
            Game(self.config).close()
            self.status.config(text="Stopped seeding and closed the game.")
        else:
            self.status.config(text="Nothing is seeding right now.")

    def open_log(self) -> None:
        path = app_dir() / "seeder.log"
        if path.exists() and os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]

    def run(self) -> None:
        self.root.mainloop()


def run(config: Config) -> int:
    SetupWindow(config).run()
    return 0


if __name__ == "__main__":
    sys.exit(run(Config.load()))
