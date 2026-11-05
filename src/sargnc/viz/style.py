"""Shared colours and figure sizing (phone-first)."""

from __future__ import annotations

from matplotlib.colors import LinearSegmentedColormap

INK = "#1f1f1d"
INK_MUTED = "#5f5e5a"
HALO = "#ffffff"
SEARCH = "#1f1f1d"

# Single-hue (sand -> umber) elevation ramp, light = low.
ELEVATION_STEPS = ["#f4eee3", "#e6d8c0", "#cfb68f", "#b0905f", "#86663f", "#5a4329"]
ELEVATION_CMAP = LinearSegmentedColormap.from_list("sargnc_elev", ELEVATION_STEPS)

PHONE_FIGSIZE = (7.0, 7.9)  # inches; ~1540 x 1740 px at 220 dpi
PHONE_DPI = 220
