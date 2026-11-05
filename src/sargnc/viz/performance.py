"""Phone-portrait performance charts: one panel per measure, altitude as an ordinal blue ramp."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from sargnc.aircraft.performance import Performance
from sargnc.viz import style as S


def performance_figure(perf: Performance, path: Path, v_cruise: float, v_min: float) -> Path:
    panels = [
        ("p_batt", "Battery power, level flight [W]"),
        ("endurance_min", "Endurance (usable energy) [min]"),
        ("range_km", "Still-air range [km]"),
        ("climb", "Max climb rate, full throttle [m/s]"),
    ]
    S.apply_rc()
    fig, axes = plt.subplots(len(panels), 1, figsize=(7.0, 11.5), dpi=S.PHONE_DPI, sharex=True, layout="constrained")
    colors = S.ordinal_blues(len(perf.curves))
    for i, (ax, (key, label)) in enumerate(zip(axes, panels)):
        for c, col in zip(perf.curves, colors):
            y = getattr(c, key)
            ax.plot(c.V, y, color=col, lw=2.0, label=f"{c.h:.0f} m")
            if i == 0:  # curves are well separated only at high speed in the power panel
                k = np.nanargmax(np.where(np.isfinite(y), c.V, np.nan))
                ax.annotate(f"{c.h:.0f} m", (c.V[k], y[k]), xytext=(4, 0), textcoords="offset points",
                            fontsize=10, color=S.INK_MUTED, va="center")
        ax.axvline(v_cruise, color=S.INK_MUTED, lw=1, ls=(0, (3, 2)))
        ax.axvline(v_min, color=S.INK_MUTED, lw=1, ls=(0, (1, 2)))
        ax.set_title(label, loc="left", fontsize=12)
        ax.grid(True, color=S.GRID, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].text(v_cruise, axes[0].get_ylim()[1], " cruise", va="top", fontsize=9, color=S.INK_MUTED)
    axes[0].text(v_min, axes[0].get_ylim()[1], " min ", va="top", ha="right", fontsize=9, color=S.INK_MUTED)
    axes[-1].set_xlabel("True airspeed [m/s]")
    axes[-1].set_xlim(right=axes[-1].get_xlim()[1] + 1.5)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside upper right", ncols=len(colors), frameon=False,
               title="altitude (ISA)", fontsize=10, title_fontsize=10)
    fig.suptitle(f"{perf.aircraft} — steady performance (ISA)", x=0.02, ha="left", fontsize=14, weight="bold")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
