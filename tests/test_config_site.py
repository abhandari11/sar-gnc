import json

import pytest

from sargnc.scenario.config import ScenarioError, load_area
from sargnc.viz.site import Artifact, Manifest, write_index


def _write(tmp_path, text):
    p = tmp_path / "s.yaml"
    p.write_text(text)
    return p


def test_load_area_ok(tmp_path):
    a = load_area(_write(tmp_path, "area: {name: x, center: {lat: 47.0, lon: 9.0}, size_m: 1000}"))
    assert a.size_e_m == a.size_n_m == 1000 and a.resolution_m == 5.0


@pytest.mark.parametrize(
    "text, msg",
    [
        ("foo: 1", "missing required section 'area'"),
        ("area: {center: {lat: 1, lon: 2}}", "area.name: required"),
        ("area: {name: x, center: [1, 2]}", "expected {lat"),
        ("area: {name: x, center: {lat: 47, lon: 9}, sizee_m: 3}", "unknown keys"),
        ("area: {name: x, center: {lat: 47, lon: 9}, buffer_m: 10}", "buffer"),
        ("area: {name: x, center: {lat: 47, lon: 9}, size_m: [1, 2, 3]}", "size_m"),
    ],
)
def test_load_area_errors(tmp_path, text, msg):
    with pytest.raises(ScenarioError, match=msg.replace("[", r"\[").replace("{", r"\{")):
        load_area(_write(tmp_path, text))


def test_index_page(tmp_path):
    run = tmp_path / "r1"
    run.mkdir()
    Manifest("r1", "Run <1>", "2026-01-01 00:00 UTC", {"k": "v"},
             [Artifact("a.png", "A", "image", "cap"), Artifact("b.html", "B", "html")]).write(run)
    assert json.loads((run / "manifest.json").read_text())["run"] == "r1"
    html = write_index(tmp_path).read_text()
    assert 'name="viewport"' in html and 'src="r1/a.png"' in html and 'href="r1/b.html"' in html
    assert "Run &lt;1&gt;" in html
