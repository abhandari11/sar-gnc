import json

import numpy as np
import pytest
import yaml

from sargnc.scenario import ScenarioError, SearchRegion, load_scenario, load_site
from sargnc.terrain import synthetic as syn
from sargnc.terrain.siting import find_level_site, water_mask
from sargnc.viz.site import Artifact, Manifest, write_index

SITE = {
    "site": {"name": "s", "origin": {"lat": 47.0, "lon": 9.0},
             "extent_m": {"east": [-2000, 2000], "north": [-2000, 2000]}},
    "base": {"name": "B", "position_m": {"east": 0, "north": 0}, "launch_heading_deg": 450,
             "home_loiter": {"center_m": {"east": 200, "north": 0}, "radius_m": 80, "height_agl_m": 100}},
}


def _write(tmp_path, name, doc):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(doc) if isinstance(doc, dict) else doc)
    return p


def _site(**over):
    d = json.loads(json.dumps(SITE))
    for k, v in over.items():
        sec, key = k.split("__")
        d[sec][key] = v
    return d


def test_load_site_and_scenario(tmp_path):
    (tmp_path / "sites").mkdir()
    _write(tmp_path / "sites", "s.yaml", SITE)
    s = load_site(tmp_path / "sites" / "s.yaml")
    assert s.base.launch_heading_deg == 90.0 and s.base.home_loiter.radius_m == 80
    sc = load_scenario(_write(tmp_path, "sc.yaml", {
        "name": "x", "site": "s", "search": {"rectangle": {"center_m": {"east": 0, "north": 0}, "size_m": [1000, 1000]}}}))
    assert sc.search.area_m2 == pytest.approx(1e6) and sc.site.name == "s"


@pytest.mark.parametrize(
    "over, msg",
    [
        ({"site__extent_m": {"east": [0, -1], "north": [-2000, 2000]}}, "max > min"),
        ({"base__position_m": {"east": 1500, "north": 0}}, "from the map edge"),
        ({"base__position_m": {"east": "far", "north": 0}}, "expected a number"),
        ({"base__speed": 3}, "unknown key"),
        ({"site__origin": {"lat": 47.0}}, "missing required key"),
    ],
)
def test_site_errors(tmp_path, over, msg):
    with pytest.raises(ScenarioError, match=msg):
        load_site(_write(tmp_path, "s.yaml", _site(**over)))


@pytest.mark.parametrize(
    "search, msg",
    [
        ({"polygons": [[[0, 0], [1, 1]]]}, ">= 3"),
        ({"polygons": [[[0, 0], [1, 1], [2, 2]]]}, "zero area"),
        ({"rectangle": {"center_m": {"east": 0, "north": 0}, "size_m": [1, 1]}, "polygons": []}, "exactly one"),
        ({"rectangle": {"center_m": {"east": 0, "north": 0}, "size_m": [3000, 1000]}}, "map edge"),
    ],
)
def test_search_errors(tmp_path, search, msg):
    (tmp_path / "sites").mkdir()
    _write(tmp_path / "sites", "s.yaml", SITE)
    with pytest.raises(ScenarioError, match=msg):
        load_scenario(_write(tmp_path, "sc.yaml", {"name": "x", "site": "s", "search": search}))


def test_search_region_polygon_ops():
    r = SearchRegion([[[0, 0], [100, 0], [100, 100], [0, 100]], [[200, 0], [300, 0], [250, 80]]])
    assert r.area_m2 == pytest.approx(1e4 + 4e3)
    assert r.contains([50, 250, 150], [50, 20, 50]).tolist() == [True, True, False]
    assert r.bounds == (0, 300, 0, 100)


def test_level_site_and_water():
    g = syn.cone(apex=300.0, slope=0.5, base=0.0).grid(800.0, 5.0)  # flat plain (water-like) + cone
    with pytest.raises(ValueError):
        find_level_site(g, 0.0, 0.0, search_radius_m=200)  # steep cone, then dead-flat plain only
    hill = syn.gaussian(100.0, 600.0, 0.0).grid(800.0, 5.0)
    p = find_level_site(hill, 300.0, 0.0, pad_radius_m=20, max_slope_deg=3.0)
    assert np.hypot(p.east, p.north) < 300 and p.max_slope_deg <= 3.0
    assert water_mask(g).sum() > 0 and not water_mask(hill).any()


def test_index_page(tmp_path):
    run = tmp_path / "r1"
    run.mkdir()
    Manifest("r1", "Run <1>", "2026-01-01 00:00 UTC", {"k": "v"},
             [Artifact("a.png", "A", "image", "cap"), Artifact("b.html", "B", "html")]).write(run)
    html = write_index(tmp_path).read_text()
    assert 'name="viewport"' in html and 'src="r1/a.png"' in html and 'href="r1/b.html"' in html
    assert "Run &lt;1&gt;" in html
