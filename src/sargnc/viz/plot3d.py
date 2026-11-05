"""Interactive 3-D terrain (plotly) sized for phones."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from sargnc.terrain.grid import TerrainGrid
from sargnc.viz import style as S

MAX_BYTES = 10 * 1024 * 1024
VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'


_AXIS = dict(backgroundcolor="#efede7", gridcolor="#d9d6ce", zerolinecolor="#d9d6ce", showspikes=False)


def _plotly_scale(steps: list[str]) -> list[list]:
    return [[i / (len(steps) - 1), c] for i, c in enumerate(steps)]


def _boundary_line(t: TerrainGrid, bounds, lift: float = 8.0) -> go.Scatter3d:
    e0, e1, n0, n1 = bounds
    s = np.linspace(0, 1, 120)
    e = np.concatenate([e0 + (e1 - e0) * s, np.full_like(s, e1), e1 - (e1 - e0) * s, np.full_like(s, e0)])
    n = np.concatenate([np.full_like(s, n0), n0 + (n1 - n0) * s, np.full_like(s, n1), n1 - (n1 - n0) * s])
    z = t.elevation(e, n) + lift
    return go.Scatter3d(x=e, y=n, z=z, mode="lines", line=dict(color=S.SEARCH, width=6),
                        name="search area", hoverinfo="skip")


def terrain_figure(t: TerrainGrid, title: str, search_bounds=None, max_nodes: int = 401) -> go.Figure:
    step = max(1, int(np.ceil(max(t.shape) / max_nodes)))
    g = t.decimated(step)
    surf = go.Surface(
        x=g.x.astype(np.float32), y=g.y.astype(np.float32), z=g.z.astype(np.float32),
        colorscale=_plotly_scale(S.ELEVATION_STEPS), showscale=False,
        lighting=dict(ambient=0.45, diffuse=0.85, specular=0.05, roughness=0.9, fresnel=0.0),
        lightposition=dict(x=-1e5, y=1e5, z=6e4),
        hovertemplate="E %{x:.0f} m<br>N %{y:.0f} m<br>%{z:.0f} m<extra></extra>",
        name="terrain",
    )
    data = [surf]
    if search_bounds is not None:
        data.append(_boundary_line(t, search_bounds))
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
            aspectratio=dict(x=1, y=(g.bounds[3] - g.bounds[2]) / (g.bounds[1] - g.bounds[0]),
                             z=zr / (g.bounds[1] - g.bounds[0])),
            xaxis=dict(title="East [m]", **_AXIS), yaxis=dict(title="North [m]", **_AXIS),
            zaxis=dict(title="Alt [m]", **_AXIS),
            camera=dict(eye=dict(x=0.68, y=-1.3, z=1.3)),
        ),
    )
    return fig


def write_terrain_html(t: TerrainGrid, path: Path, title: str, search_bounds=None,
                       max_nodes: int = 401) -> tuple[Path, go.Figure]:
    """Write an HTML page (plotly.js from CDN), shrinking the mesh until < 10 MB."""
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        fig = terrain_figure(t, title, search_bounds, max_nodes)
        fig.write_html(path, include_plotlyjs="cdn", full_html=True,
                       config=dict(responsive=True, displaylogo=False, scrollZoom=True))
        html = path.read_text().replace("<head>", f"<head>{VIEWPORT}<title>{title}</title>", 1)
        path.write_text(html)
        if path.stat().st_size < MAX_BYTES or max_nodes < 50:
            return path, fig
        max_nodes = int(max_nodes * 0.8)


def write_terrain_png(fig: go.Figure, path: Path, width: int = 480, height: int = 540) -> Path | None:
    """Static render of a 3-D figure via kaleido; None if no browser is available."""
    try:
        fig.write_image(path, width=width, height=height, scale=2)
    except Exception as e:  # kaleido or Chrome missing
        import logging

        logging.getLogger(__name__).warning("3-D PNG skipped: %s", str(e).splitlines()[0] if str(e) else e)
        return None
    return path
