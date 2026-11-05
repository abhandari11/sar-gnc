"""2-D terrain map: tinted hillshade, contours and search-area overlay."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource, Normalize
from matplotlib.cm import ScalarMappable

from sargnc.scenario.region import SearchRegion
from sargnc.scenario.site import Base
from sargnc.terrain.grid import TerrainGrid
from sargnc.terrain.siting import water_mask
from sargnc.viz import style as S

_HALO = [pe.withStroke(linewidth=3.0, foreground=S.HALO)]


def tinted_hillshade(t: TerrainGrid, azdeg: float = 315.0, altdeg: float = 40.0) -> np.ndarray:
    """RGB array (ny, nx, 3), row 0 = north, of elevation tint blended with hillshade."""
    ls = LightSource(azdeg=azdeg, altdeg=altdeg)
    norm = Normalize(t.z.min(), t.z.max())
    return ls.shade(t.z[::-1], cmap=S.ELEVATION_CMAP, norm=norm, blend_mode="soft", dx=t.d, dy=t.d, vert_exag=1.0)[..., :3]


def _draw_region(ax, region: SearchRegion, km: float) -> None:
    for v in region.polygons:
        e, n = np.append(v[:, 0], v[0, 0]) / km, np.append(v[:, 1], v[0, 1]) / km
        ax.plot(e, n, color=S.HALO, lw=4.5, solid_joinstyle="miter")
        ax.plot(e, n, color=S.SEARCH, lw=2.0, solid_joinstyle="miter")
    e0, _, _, n1 = (b / km for b in region.bounds)
    ax.text(e0 + 0.04, n1 - 0.06, region.name, va="top", fontsize=11, weight="bold", path_effects=_HALO)


def _draw_base(ax, base: Base, km: float) -> None:
    lo = base.home_loiter
    th = np.linspace(0, 2 * np.pi, 120)
    ax.plot((lo.east + lo.radius_m * np.cos(th)) / km, (lo.north + lo.radius_m * np.sin(th)) / km,
            color=S.INK, lw=1.2, ls=(0, (3, 2)), path_effects=_HALO)
    ax.plot(base.east / km, base.north / km, marker="*", ms=22, color=S.BASE, mec=S.HALO, mew=1.5, zorder=5)
    ax.text(base.east / km - 0.08, base.north / km, base.name, ha="right", va="center", fontsize=11,
            weight="bold", path_effects=_HALO, zorder=5)


def terrain_map(t: TerrainGrid, path: Path, title: str, region: SearchRegion | None = None,
                base: Base | None = None, contour_m: float = 50.0) -> Path:
    """Write the hillshade/contour map PNG; axes in km of local ENU."""
    km = 1000.0
    e0, e1, n0, n1 = t.bounds
    ext = (e0 / km, e1 / km, n0 / km, n1 / km)
    plt.rcParams.update({"font.size": 12, "axes.edgecolor": S.INK_MUTED, "text.color": S.INK,
                         "axes.labelcolor": S.INK, "xtick.color": S.INK_MUTED, "ytick.color": S.INK_MUTED})
    fig, ax = plt.subplots(figsize=S.PHONE_FIGSIZE, dpi=S.PHONE_DPI, layout="constrained")
    ax.imshow(tinted_hillshade(t), extent=ext, interpolation="bilinear")
    water = water_mask(t)
    if water.any():
        ax.contourf(t.x / km, t.y / km, water.astype(float), levels=[0.5, 1.5], colors=[S.WATER])

    X, Y = t.x / km, t.y / km
    lo = np.ceil(t.z.min() / contour_m) * contour_m
    levels = np.arange(lo, t.z.max(), contour_m)
    major = levels[np.isclose(np.mod(levels, 5 * contour_m), 0)]
    ax.contour(X, Y, t.z, levels=levels, colors=S.INK, linewidths=0.25, alpha=0.45)
    cs = ax.contour(X, Y, t.z, levels=major, colors=S.INK, linewidths=0.7, alpha=0.7)
    ax.clabel(cs, fmt="%d", fontsize=8, inline_spacing=2)

    if region is not None:
        _draw_region(ax, region, km)
    if base is not None:
        _draw_base(ax, base, km)
    ax.plot(0, 0, "+", color=S.INK, ms=10, mew=1.5)

    # scale bar + north arrow
    x_sb, y_sb = ext[0] + 0.25, ext[2] + 0.25
    ax.plot([x_sb, x_sb + 1.0], [y_sb, y_sb], color=S.INK, lw=3, solid_capstyle="butt", path_effects=_HALO)
    ax.text(x_sb + 0.5, y_sb + 0.08, "1 km", ha="center", fontsize=11, path_effects=_HALO)
    ax.annotate("N", xy=(ext[1] - 0.3, ext[3] - 0.2), xytext=(ext[1] - 0.3, ext[3] - 0.65), ha="center",
                fontsize=13, weight="bold", arrowprops=dict(arrowstyle="-|>", color=S.INK, lw=1.5),
                path_effects=_HALO)

    ax.set_xlabel("East [km]")
    ax.set_ylabel("North [km]")
    ax.set_aspect("equal")
    ax.set_title(title, loc="left", fontsize=14, weight="bold")
    sm = ScalarMappable(Normalize(t.z.min(), t.z.max()), S.ELEVATION_CMAP)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.04, pad=0.02, aspect=40)
    cb.set_label("Elevation [m]  ·  contours every %d m" % contour_m)
    cb.outline.set_visible(False)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
