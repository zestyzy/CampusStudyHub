"""Centralized UI style constants for the CustomTkinter dark theme."""
from __future__ import annotations

# Color palette (dark + blue accent)
BG_DARK = "#0f1115"
BG_CARD = "#151a21"
BORDER = "#1f2633"
ACCENT = "#2f80ed"
ACCENT_ALT = "#3ea6ff"
TEXT_PRIMARY = "#e5e9f0"
TEXT_MUTED = "#9aa7b8"
TEXT_WARN = "#ffb74d"
TEXT_ERROR = "#ef5350"
TEXT_SUCCESS = "#6ee7b7"

# Layout constants
CARD_RADIUS = 16
CARD_BORDER_WIDTH = 1
CARD_PAD_X = 10
CARD_PAD_Y = 8
SECTION_GAP = 12

# Font helpers (macOS friendly defaults)
TITLE_FONT = ("Helvetica", 18, "bold")
HEADER_FONT = ("Helvetica", 24, "bold")
LABEL_FONT = ("Helvetica", 13)
LABEL_BOLD = ("Helvetica", 13, "bold")
MONO_FONT = ("SFMono-Regular", 12)
CLOCK_FONT = ("SFMono-Regular", 36, "bold")
DATE_FONT = ("Helvetica", 14)
BADGE_FONT = ("Helvetica", 12, "bold")


def card_kwargs() -> dict:
    """Default kwargs for a dashboard-style card."""
    return {
        "corner_radius": CARD_RADIUS,
        "border_width": CARD_BORDER_WIDTH,
        "border_color": BORDER,
        "fg_color": BG_CARD,
    }


def badge_kwargs() -> dict:
    """Default kwargs for small pill-like buttons/labels."""
    return {
        "corner_radius": 10,
        "fg_color": ACCENT,
        "hover_color": ACCENT_ALT,
        "font": BADGE_FONT,
    }
