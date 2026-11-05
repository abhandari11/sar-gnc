"""Interactive 3-D terrain (plotly) sized for phones."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import plotly.graph_objects as go

from sargnc.scenario.region import SearchRegion
from sargnc.scenario.site import Base
from sargnc.terrain.grid import TerrainGrid
from sargnc.viz import style as S

MAX_BYTES = 10 * 1024 * 1024
VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'
_AXIS = dict(backgroundcolor="#efede7", gridcolor="#d9d6ce", zerolinecolor="#d9d6ce", showspikes=False)


def _plotly_scale(steps: list[str]) -> list[list]:
    return [[i / (len(steps) - 1), c] for i, c in enumerate(steps)]


def _draped(t: TerrainGrid, v: np.ndarray, lift: float = 8.0, step: float = 10.0) -> tuple[np.ndarray, ...]:
    """Densify a closed polygon and lift it slightly above the terrain."""
    v = np.vstack([v, v[:1]])
    e, n = [], []
    for a, b in zip(v[:-1], v[1:]):
        k = max(2, int(np.hypot(*(b - a)) / step))
        s = np.linspace(0, 1, k, endpoint=False)
        e.append(a[0] + (b[0] - a[0]) * s)
        n.append(a[1] + (b[1] - a[1]) * s)
    e, n = np.append(np.concatenate(e), v[-1, 0]), np.append(np.concatenate(n), v[-1, 1])
    return e, n, t.elevation(e, n) + lift


def region_traces(t: TerrainGrid, region: SearchRegion) -> list[go.Scatter3d]:
    out = []
    for v in region.polygons:
        e, n, z = _draped(t, v)
        out.append(go.Scatter3d(x=e, y=n, z=z, mode="lines", line=dict(color=S.SEARCH, width=6),
                                name=region.name, hoverinfo="skip"))
    return out


def base_traces(t: TerrainGrid, base: Base) -> list[go.Scatter3d]:
    z = float(t.elevation(base.east, base.north))
    return [go.Scatter3d(x=[base.east], y=[base.north], z=[z + 15], mode="markers+text",
                         marker=dict(symbol="diamond", size=9, color=S.BASE, line=dict(color="#ffffff", width=2)),
                         text=["Base"], textposition="top center", textfont=dict(size=13, color=S.INK),
                         name=base.name,
                         hovertemplate=f"{base.name}<br>E %{{x:.0f}} N %{{y:.0f}}<br>{z:.0f} m<extra></extra>")]


def terrain_figure(t: TerrainGrid, title: str, region: SearchRegion | None = None, base: Base | None = None,
                   extra: Sequence[go.BaseTraceType] = (), max_nodes: int = 401) -> go.Figure:
    step = max(1, int(np.ceil(max(t.shape) / max_nodes)))
    g = t.decimated(step)
    data: list = [go.Surface(
        x=g.x.astype(np.float32), y=g.y.astype(np.float32), z=g.z.astype(np.float32),
        colorscale=_plotly_scale(S.ELEVATION_STEPS), showscale=False,
        lighting=dict(ambient=0.45, diffuse=0.85, specular=0.05, roughness=0.9, fresnel=0.0),
        lightposition=dict(x=-1e5, y=1e5, z=6e4),
        hovertemplate="E %{x:.0f} m<br>N %{y:.0f} m<br>%{z:.0f} m<extra></extra>",
        name="terrain",
    )]
    if region is not None:
        data += region_traces(t, region)
    if base is not None:
        data += base_traces(t, base)
    data += list(extra)
    e0, e1, n0, n1 = g.bounds
    zr = float(t.z.max() - t.z.min())
    fig = go.Figure(data)
    fig.update_layout(
        title=dict(text=f"{title} — {g.d:.0f} m mesh", x=0.02, font=dict(size=14)),
        margin=dict(l=0, r=0, t=36, b=0),
        showlegend=False,
        modebar=dict(orientation="v"),
        paper_bgcolor="#faf9f6",
        scene=dict(
            aspectmode="manual",
            aspectratio=dict(x=1, y=(n1 - n0) / (e1 - e0), z=zr / (e1 - e0)),
            xaxis=dict(title="East [m]", **_AXIS), yaxis=dict(title="North [m]", **_AXIS),
            zaxis=dict(title="Alt [m]", **_AXIS),
            camera=dict(eye=dict(x=0.68, y=-1.3, z=1.3)),
        ),
    )
    return fig


def write_html(fig_fn, path: Path, title: str, max_nodes: int = 401) -> tuple[Path, go.Figure]:
    """Write fig_fn(max_nodes) as an HTML page (plotly.js from CDN), shrinking the mesh until < 10 MB."""
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        fig = fig_fn(max_nodes)
        fig.write_html(path, include_plotlyjs="cdn", full_html=True,
                       config=dict(responsive=True, displaylogo=False, scrollZoom=True))
        html = path.read_text().replace("<head>", f"<head>{VIEWPORT}<title>{title}</title>", 1)
        path.write_text(html)
        if path.stat().st_size < MAX_BYTES or max_nodes < 50:
            return path, fig
        max_nodes = int(max_nodes * 0.8)


def write_png(fig: go.Figure, path: Path, width: int = 480, height: int = 540) -> Path | None:
    """Static render of a 3-D figure via kaleido; None if no browser is available."""
    try:
        fig.write_image(path, width=width, height=height, scale=2)
    except Exception as e:  # kaleido or Chrome missing
        logging.getLogger(__name__).warning("3-D PNG skipped: %s", str(e).splitlines()[0] if str(e) else e)
        return None
    return path
