"""Shared colours and figure sizing (phone-first)."""

from __future__ import annotations

import numpy as np
from matplotlib.colors import LinearSegmentedColormap

INK = "#1f1f1d"
INK_MUTED = "#5f5e5a"
HALO = "#ffffff"
SEARCH = "#1f1f1d"
BASE = "#d6372b"  # base-camp star; reserved, never used for data
TRACK = "#256abf"
WATER = "#9ec5f4"

# Single-hue (sand -> umber) elevation ramp, light = low.
ELEVATION_STEPS = ["#f4eee3", "#e6d8c0", "#cfb68f", "#b0905f", "#86663f", "#5a4329"]
ELEVATION_CMAP = LinearSegmentedColormap.from_list("sargnc_elev", ELEVATION_STEPS)

PHONE_FIGSIZE = (7.0, 8.6)  # inches; ~1540 x 1900 px at 220 dpi
PHONE_DPI = 220

GRID = "#e4e2dc"
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]  # fixed order
BLUES = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]  # sequential ramp, ordinal-safe steps


def ordinal_blues(n: int) -> list[str]:
    idx = np.linspace(0, len(BLUES) - 1, n).round().astype(int)
    return [BLUES[i] for i in idx]


def apply_rc() -> None:
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 12, "axes.edgecolor": INK_MUTED, "text.color": INK,
                         "axes.labelcolor": INK, "xtick.color": INK_MUTED, "ytick.color": INK_MUTED})
