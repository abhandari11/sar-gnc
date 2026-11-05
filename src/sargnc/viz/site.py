"""Run manifests and the phone-friendly static index page."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Artifact:
    file: str
    title: str
    kind: str  # "image" | "html"
    caption: str = ""


@dataclass
class Manifest:
    run: str
    title: str
    created: str
    summary: dict = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)

    def write(self, run_dir: Path) -> Path:
        p = run_dir / "manifest.json"
        p.write_text(json.dumps(asdict(self), indent=2))
        return p

    @classmethod
    def read(cls, run_dir: Path) -> "Manifest":
        d = json.loads((run_dir / "manifest.json").read_text())
        d["artifacts"] = [Artifact(**a) for a in d["artifacts"]]
        return cls(**d)


_CSS = """
:root { --bg:#faf9f6; --card:#ffffff; --ink:#1f1f1d; --muted:#5f5e5a; --line:#e4e2dc; --accent:#256abf; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#171716; --card:#22221f; --ink:#ecebe6; --muted:#a5a39b; --line:#383835; --accent:#86b6ef; } }
:root[data-theme="dark"] { --bg:#171716; --card:#22221f; --ink:#ecebe6; --muted:#a5a39b; --line:#383835; --accent:#86b6ef; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font: 16px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 20px 16px 48px; }
h1 { font-size: 1.45rem; margin: 0 0 4px; }
h2 { font-size: 1.15rem; margin: 0 0 2px; }
.sub { color: var(--muted); margin: 0 0 20px; font-size: .92rem; }
section.run { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 16px; margin: 0 0 20px; }
dl { display: grid; grid-template-columns: auto 1fr; gap: 2px 12px; margin: 10px 0 14px; font-size: .9rem; }
dt { color: var(--muted); } dd { margin: 0; font-variant-numeric: tabular-nums; }
figure { margin: 14px 0 0; }
figure img { width: 100%; height: auto; border-radius: 8px; border: 1px solid var(--line); display:block; }
figcaption { color: var(--muted); font-size: .88rem; margin-top: 6px; }
a.btn { display: block; text-align: center; padding: 14px; border-radius: 10px; margin-top: 14px;
  background: var(--accent); color: #fff; text-decoration: none; font-weight: 600; }
@media (prefers-color-scheme: dark) { a.btn { color:#0d1b2e; } }
"""


def _run_section(run_dir_rel: str, m: Manifest) -> str:
    rows = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>" for k, v in m.summary.items())
    parts = [f'<section class="run"><h2>{html.escape(m.title)}</h2>',
             f'<p class="sub">run <code>{html.escape(m.run)}</code> · {html.escape(m.created)}</p>',
             f"<dl>{rows}</dl>"]
    for a in m.artifacts:
        href = f"{run_dir_rel}/{a.file}"
        cap = f"<figcaption>{html.escape(a.caption)}</figcaption>" if a.caption else ""
        if a.kind == "image":
            parts.append(f'<figure><a href="{href}"><img src="{href}" alt="{html.escape(a.title)}" '
                         f'decoding="async"></a>{cap}</figure>')
        else:
            parts.append(f'<a class="btn" href="{href}">{html.escape(a.title)} ↗</a>{cap}')
    parts.append("</section>")
    return "".join(parts)


def write_index(site_dir: Path, title: str = "sar-gnc — results") -> Path:
    """Regenerate site_dir/index.html from every <run>/manifest.json, newest first."""
    runs = sorted((Manifest.read(p.parent) for p in site_dir.glob("*/manifest.json")),
                  key=lambda m: m.created, reverse=True)
    body = "".join(_run_section(m.run, m) for m in runs) or "<p>No runs published yet.</p>"
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head><body><main>"
        f'<h1>{html.escape(title)}</h1><p class="sub">Terrain-aware GNC for SAR in mountains · '
        "Stage 1: simulation environment</p>"
        f"{body}</main></body></html>"
    )
    p = site_dir / "index.html"
    p.write_text(page)
    return p
