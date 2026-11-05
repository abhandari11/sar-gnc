"""Flight-result plots: track on the terrain map, time histories, 3-D track."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go

from sargnc.scenario.region import SearchRegion
from sargnc.scenario.site import Base
from sargnc.sim.simulator import SimResult
from sargnc.terrain.grid import TerrainGrid
from sargnc.viz import style as S
from sargnc.viz.map2d import _HALO, _draw_base, _draw_region, tinted_hillshade
from sargnc.terrain.siting import water_mask

PHASES = ("launch", "climb", "transit", "orbit", "return", "home")
PHASE_COLORS = dict(zip(PHASES, S.CATEGORICAL))


def _segments(phase: np.ndarray):
    """Yield (phase, start_idx, end_idx_inclusive) runs."""
    start = 0
    for i in range(1, len(phase) + 1):
        if i == len(phase) or phase[i] != phase[start]:
            yield phase[start], start, min(i, len(phase) - 1)
            start = i


def flight_map(t: TerrainGrid, res: SimResult, path: Path, title: str, region: SearchRegion | None,
               base: Base, pad_m: float = 400.0) -> Path:
    L, km = res.log, 1000.0
    e0 = min(np.nanmin(L["east"]), base.east) - pad_m
    e1 = max(np.nanmax(L["east"]), base.east) + pad_m
    n0 = min(np.nanmin(L["north"]), base.north) - pad_m
    n1 = max(np.nanmax(L["north"]), base.north) + pad_m
    if region is not None:
        b = region.bounds
        e0, e1, n0, n1 = min(e0, b[0] - 100), max(e1, b[1] + 100), min(n0, b[2] - 100), max(n1, b[3] + 100)
    tb = t.bounds
    e0, e1, n0, n1 = max(e0, tb[0]), min(e1, tb[1]), max(n0, tb[2]), min(n1, tb[3])
    S.apply_rc()
    fig, ax = plt.subplots(figsize=S.PHONE_FIGSIZE, dpi=S.PHONE_DPI, layout="constrained")
    ext = (tb[0] / km, tb[1] / km, tb[2] / km, tb[3] / km)
    ax.imshow(tinted_hillshade(t), extent=ext, interpolation="bilinear", alpha=0.9)
    w = water_mask(t)
    if w.any():
        ax.contourf(t.x / km, t.y / km, w.astype(float), levels=[0.5, 1.5], colors=[S.WATER])
    lv = np.arange(np.ceil(t.z.min() / 100) * 100, t.z.max(), 100)
    ax.contour(t.x / km, t.y / km, t.z, levels=lv, colors=S.INK, linewidths=0.3, alpha=0.4)
    if region is not None:
        _draw_region(ax, region, km)
    for ph, i, j in _segments(L["phase"]):
        if ph not in PHASE_COLORS:
            continue
        ax.plot(L["east"][i:j + 1] / km, L["north"][i:j + 1] / km, color=S.HALO, lw=4.0, solid_capstyle="round")
        ax.plot(L["east"][i:j + 1] / km, L["north"][i:j + 1] / km, color=PHASE_COLORS[ph], lw=2.0,
                solid_capstyle="round")
    for ph in PHASES:
        if ph in set(L["phase"]):
            ax.plot([], [], color=PHASE_COLORS[ph], lw=3, label=ph)
    _draw_base(ax, base, km)
    ax.set_xlim(e0 / km, e1 / km)
    ax.set_ylim(n0 / km, n1 / km)
    ax.set_aspect("equal")
    ax.set_xlabel("East [km]")
    ax.set_ylabel("North [km]")
    wn, we = L["wind_n"][0], L["wind_e"][0]
    spd = float(np.hypot(wn, we))
    if spd > 0.1:
        cx, cy = e0 / km + 0.12 * (e1 - e0) / km, n1 / km - 0.1 * (n1 - n0) / km
        s = 0.25 / spd
        ax.annotate("", xy=(cx + we * s * 0.5, cy + wn * s * 0.5), xytext=(cx - we * s * 0.5, cy - wn * s * 0.5),
                    arrowprops=dict(arrowstyle="-|>", color=S.INK, lw=2))
        ax.text(cx, cy - 0.12, f"wind {spd:.0f} m/s", ha="center", va="top", fontsize=10, path_effects=_HALO)
    ax.legend(loc="lower right", fontsize=10, framealpha=0.9, title="phase", title_fontsize=10)
    ax.set_title(title, loc="left", fontsize=14, weight="bold")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def time_histories(res: SimResult, path: Path, title: str, bank_max_deg: float, v_min: float) -> Path:
    L = res.log
    tt = L["t"] / 60.0
    d = np.degrees
    S.apply_rc()
    panels = 7
    fig, axes = plt.subplots(panels, 1, figsize=(7.0, 15.5), dpi=S.PHONE_DPI, sharex=True, layout="constrained")
    for ax in axes:
        for ph, i, j in _segments(L["phase"]):
            if ph in PHASE_COLORS:
                ax.axvspan(tt[i], tt[j], color=PHASE_COLORS[ph], alpha=0.08, lw=0)
        ax.grid(True, color=S.GRID, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)

    a = axes[0]
    a.fill_between(tt, np.nanmin(L["terrain"]) - 50, L["terrain"], color=S.ELEVATION_STEPS[2], lw=0, label="ground below")
    a.plot(tt, L["alt_cmd"], color=S.INK_MUTED, lw=1.2, ls=(0, (3, 2)), label="command")
    a.plot(tt, L["alt"], color=S.TRACK, lw=2.0, label="Gildo")
    a.set_title("Altitude [m]", loc="left", fontsize=12)
    a.legend(fontsize=9, loc="lower right", ncols=3, frameon=True, framealpha=0.85, edgecolor="none")
    a.set_ylim(top=a.get_ylim()[1] + 0.12 * (a.get_ylim()[1] - a.get_ylim()[0]))
    for ph, i, j in _segments(L["phase"]):
        if ph in PHASE_COLORS and (tt[j] - tt[i]) > 0.6:
            a.text(0.5 * (tt[i] + tt[j]), 0.97, ph, ha="center", va="top", fontsize=9,
                   color=S.INK_MUTED, transform=a.get_xaxis_transform())

    axes[1].plot(tt, L["agl"], color=S.TRACK, lw=1.8)
    axes[1].set_title("Height above ground [m]", loc="left", fontsize=12)
    axes[1].set_ylim(bottom=0)

    axes[2].plot(tt, L["Va_cmd"], color=S.INK_MUTED, lw=1.2, ls=(0, (3, 2)))
    axes[2].plot(tt, L["Va"], color=S.TRACK, lw=1.8)
    axes[2].axhline(v_min, color=S.INK_MUTED, lw=1, ls=(0, (1, 2)))
    axes[2].set_title("Airspeed [m/s] (dashed = command, dotted = minimum)", loc="left", fontsize=12)

    axes[3].plot(tt, d(L["phi"]), color=S.TRACK, lw=1.5)
    for s in (-1, 1):
        axes[3].axhline(s * bank_max_deg, color=S.INK_MUTED, lw=1, ls=(0, (1, 2)))
    axes[3].set_title("Bank angle [deg] (dotted = limit)", loc="left", fontsize=12)

    axes[4].plot(tt, d(L["theta"]), color=S.TRACK, lw=1.5)
    axes[4].set_title("Pitch angle [deg]", loc="left", fontsize=12)

    axes[5].plot(tt, L["p_batt"], color=S.TRACK, lw=1.2)
    axes[5].set_title("Battery power [W]", loc="left", fontsize=12)

    axes[6].plot(tt, L["energy_Wh"], color=S.TRACK, lw=2.0)
    axes[6].set_title("Energy used [Wh]", loc="left", fontsize=12)
    axes[-1].set_xlabel("Time [min]")
    fig.suptitle(title, x=0.02, ha="left", fontsize=14, weight="bold")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def track_traces(res: SimResult, every: int = 10) -> list[go.Scatter3d]:
    L = res.log
    out = []
    for ph, i, j in _segments(L["phase"]):
        if ph not in PHASE_COLORS:
            continue
        sl = slice(i, j + 1, every)
        idx = np.r_[np.arange(i, j + 1, every), j]
        out.append(go.Scatter3d(
            x=L["east"][idx], y=L["north"][idx], z=L["alt"][idx], mode="lines",
            line=dict(color=PHASE_COLORS[ph], width=5), name=ph,
            customdata=np.column_stack([L["t"][idx], L["agl"][idx], L["Va"][idx]]),
            hovertemplate=f"{ph}<br>t %{{customdata[0]:.0f}} s<br>alt %{{z:.0f}} m · AGL %{{customdata[1]:.0f}} m"
                          "<br>Va %{customdata[2]:.1f} m/s<extra></extra>"))
        del sl
    return out
