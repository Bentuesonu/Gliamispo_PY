import os
from pathlib import Path

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication


def _hex(h):
    h = h.lstrip("#")
    return QColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgba(h, alpha):
    c = _hex(h)
    c.setAlphaF(alpha)
    return c


# --- Backgrounds ---
BG0 = _hex("#f4f0eb")
BG1 = _hex("#ece7e0")
BG2 = _hex("#e1dbd2")
BG3 = _hex("#d4cec5")

# --- Text ---
TEXT0 = _hex("#0f0e0c")
TEXT1 = _hex("#2a2724")
TEXT2 = _hex("#4a4540")
TEXT3 = _hex("#7a7268")
TEXT4 = _hex("#a89e94")
TEXT_INV = _hex("#f0ece6")
TEXT_INV2 = _hex("#9a9086")

# --- Sidebar ---
SIDEBAR_BG = _hex("#1a1816")
SIDEBAR_HOVER = _hex("#262220")
SIDEBAR_BORDER = _rgba("#ffffff", 0.07)

# --- Gold accent ---
GOLD = _hex("#c8940a")
GOLD_BG = _rgba("#c8940a", 0.10)
GOLD_BD = _rgba("#c8940a", 0.35)
GOLD_DARK = _hex("#9a6e08")

# --- Status ---
STATUS_OK = _hex("#1a7a3a")
STATUS_WARN = _hex("#b85c08")
STATUS_ERR = _hex("#c01820")
STATUS_AI = _hex("#1a6898")

# --- Borders ---
BD0 = _rgba("#000000", 0.06)
BD1 = _rgba("#000000", 0.10)
BD2 = _rgba("#000000", 0.16)
BD3 = _rgba("#000000", 0.24)

# --- Breakdown categories ---
CATEGORY_COLORS = {
    "Cast": "#b06000",
    "Props": "#a02020",
    "Set Dressing": "#186868",
    "Vehicles": "#206838",
    "Special FX": "#8a1a2e",
    "Wardrobe": "#4a1a82",
    "Extras": "#1a4a72",
    "Stunts": "#6a3210",
    "Intimacy": "#8a2050",
    "Makeup": "#6a1a60",
    "Livestock": "#4a6020",
    "Animal Handlers": "#5a4020",
    "Music": "#2a4a6a",
    "Sound": "#3a5a40",
    "Greenery": "#2a6a20",
    "Special Equipment": "#4a4a4a",
    "Security": "#5a3030",
    "Additional Labor": "#4a4a20",
    "VFX": "#3a2a6a",
    "Mechanical FX": "#5a4a30",
    "Notes": "#6a6a5a",
}

_ICONS_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "gliamispo_icons")

CATEGORY_ICON_FILES = {
    "Cast":             "cat_cast.svg",
    "Props":            "cat_props.svg",
    "Set Dressing":     "cat_set_dressing.svg",
    "Vehicles":         "cat_vehicles.svg",
    "Special FX":       "cat_sfx.svg",
    "Wardrobe":         "cat_wardrobe.svg",
    "Extras":           "cat_extras.svg",
    "Stunts":           "cat_stunt.svg",
    "Intimacy":         "cat_intimacy.svg",
    "Makeup":           "cat_makeup.svg",
    "Livestock":        "cat_animals.svg",
    "Animal Handlers":  "cat_animal_handlers.svg",
    "Music":            "cat_music.svg",
    "Sound":            "cat_audio.svg",
    "Greenery":         "cat_greenery.svg",
    "Special Equipment": "cat_special_equipment.svg",
    "Security":         "cat_security.svg",
    "Additional Labor": "cat_labor.svg",
    "VFX":              "cat_vfx.svg",
    "Mechanical FX":    "cat_mechanical_fx.svg",
    "Notes":            "cat_notes.svg",
}

TAB_ICON_FILES = {
    "Breakdown":       "tab_breakdown.svg",
    "Script":          "tab_script.svg",
    "Stripboard":      "tab_stripboard.svg",
    "Budget":          "tab_budget.svg",
    "One-Liner":       "tab_oneliner.svg",
    "Day Out of Days": "tab_dood.svg",
}

# --- Stripboard colors ---
STRIP_COLORS = {
    ("INT", "GIORNO"): "#7a4a0e",
    ("INT", "DAY"): "#7a4a0e",
    ("EXT", "GIORNO"): "#1a5228",
    ("EXT", "DAY"): "#1a5228",
    ("INT", "NOTTE"): "#1e2e62",
    ("INT", "NIGHT"): "#1e2e62",
    ("EXT", "NOTTE"): "#3a2060",
    ("EXT", "NIGHT"): "#3a2060",
    ("INT", "ALBA"): "#6e3210",
    ("EXT", "ALBA"): "#6e3210",
    ("INT", "TRAMONTO"): "#6e3210",
    ("EXT", "TRAMONTO"): "#6e3210",
}
DEFAULT_STRIP_COLOR = "#5a5048"

# --- Tab definitions ---
TABS = [
    "Breakdown",
    "Script",
    "Stripboard",
    "Budget",
    "One-Liner",
    "Day Out of Days",
]


def _svg_icon(svg_path, color_hex, size=16):
    from PyQt6.QtGui import QIcon, QPixmap, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtCore import QByteArray, QSize, Qt
    try:
        with open(svg_path, encoding="utf-8") as f:
            data = f.read()
        data = data.replace("currentColor", color_hex)
        renderer = QSvgRenderer(QByteArray(data.encode()))
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


def category_qicon(cat, size=14):
    fn = CATEGORY_ICON_FILES.get(cat)
    if not fn:
        from PyQt6.QtGui import QIcon
        return QIcon()
    return _svg_icon(os.path.join(_ICONS_DIR, fn), CATEGORY_COLORS.get(cat, "#6a6a5a"), size)


def tab_qicon(name, color_hex, size=16):
    fn = TAB_ICON_FILES.get(name)
    if not fn:
        from PyQt6.QtGui import QIcon
        return QIcon()
    return _svg_icon(os.path.join(_ICONS_DIR, fn), color_hex, size)


def strip_color_for(int_ext, day_night):
    key = (int_ext or "INT", day_night or "GIORNO")
    return _hex(STRIP_COLORS.get(key, DEFAULT_STRIP_COLOR))


def category_color(cat):
    return _hex(CATEGORY_COLORS.get(cat, "#6a6a5a"))


def category_bg(cat):
    c = category_color(cat)
    c.setAlphaF(0.08)
    return c


def category_border(cat):
    c = category_color(cat)
    c.setAlphaF(0.25)
    return c


def confidence_color(conf):
    if conf is None:
        return TEXT3
    if conf >= 0.9:
        return STATUS_OK
    if conf >= 0.7:
        return STATUS_WARN
    return STATUS_ERR


_UI_FONT_FAMILY = None


def _resolve_ui_font():
    global _UI_FONT_FAMILY
    if _UI_FONT_FAMILY is not None:
        return _UI_FONT_FAMILY
    from PyQt6.QtGui import QFontDatabase
    families = QFontDatabase.families()
    for candidate in ("SF Pro Display", "SF Pro Text", ".AppleSystemUIFont",
                      "Helvetica Neue", "Segoe UI", "sans-serif"):
        if candidate in families:
            _UI_FONT_FAMILY = candidate
            return candidate
    _UI_FONT_FAMILY = ""
    return ""


def font_ui(size=13, bold=False):
    f = QFont(_resolve_ui_font(), size)
    if bold:
        f.setBold(True)
    return f


def font_mono(size=13, bold=False):
    f = QFont("Courier New", size)
    if bold:
        f.setBold(True)
    return f


def qss_color(c):
    if c.alpha() < 255:
        return f"rgba({c.red()},{c.green()},{c.blue()},{c.alphaF():.2f})"
    return c.name()


# --- Global stylesheet ---
APP_STYLE = f"""
QMainWindow {{
    background-color: {BG1.name()};
}}
QWidget {{
    font-family: ".AppleSystemUIFont", "Helvetica Neue", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT0.name()};
}}
QSplitter::handle {{
    background-color: {qss_color(BD1)};
    width: 1px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {qss_color(BD2)};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {qss_color(BD2)};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QToolTip {{
    background-color: {SIDEBAR_BG.name()};
    color: {TEXT_INV.name()};
    border: 1px solid {qss_color(BD2)};
    padding: 4px 8px;
    font-size: 11px;
}}
"""
