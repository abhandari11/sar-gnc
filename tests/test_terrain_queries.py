import numpy as np
import pytest

from sargnc.terrain import synthetic as syn


@pytest.mark.parametrize("method", ["bilinear", "bicubic"])
def test_plane_exact(method):
    a = syn.plane(100.0, 0.2, -0.1)
    g = a.grid(500.0, 10.0)
    rng = np.random.default_rng(0)
    x, y = rng.uniform(-490, 490, (2, 500))
    z, gx, gy = a.f(x, y)
    np.testing.assert_allclose(g.elevation(x, y, method), z, atol=1e-9)
    hx, hy = g.gradient(x, y, method)
    np.testing.assert_allclose(hx, gx, atol=1e-9)
    np.testing.assert_allclose(hy, gy, atol=1e-9)


def test_gaussian_bicubic_beats_bilinear():
    a = syn.gaussian(300.0, 150.0, 1000.0)
    g = a.grid(600.0, 10.0)
    rng = np.random.default_rng(1)
    x, y = rng.uniform(-500, 500, (2, 2000))
    z, gx, gy = a.f(x, y)
    err_lin = np.abs(g.elevation(x, y, "bilinear") - z).max()
    err_cub = np.abs(g.elevation(x, y, "bicubic") - z).max()
    assert err_cub < 0.1 and err_cub < err_lin
    hx, hy = g.gradient(x, y, "bicubic")
    assert np.abs(hx - gx).max() < 5e-3 and np.abs(hy - gy).max() < 5e-3


def test_cone_slope_and_normal():
    a = syn.cone(apex=500.0, slope=0.6, base=0.0)
    g = a.grid(1000.0, 5.0)
    th = np.linspace(0, 2 * np.pi, 50, endpoint=False)
    r = 400.0
    x, y = r * np.cos(th), r * np.sin(th)
    np.testing.assert_allclose(g.slope(x, y), np.arctan(0.6), atol=2e-3)
    n = g.normal(x, y)
    np.testing.assert_allclose(np.linalg.norm(n, axis=-1), 1.0, atol=1e-12)
    expect = np.stack([0.6 * np.cos(th), 0.6 * np.sin(th), np.ones_like(th)], -1)
    expect /= np.linalg.norm(expect, axis=-1, keepdims=True)
    np.testing.assert_allclose(n, expect, atol=3e-3)
    # aspect: downslope points radially outward, azimuth clockwise from north
    np.testing.assert_allclose(np.cos(g.aspect(x, y)), np.cos(np.arctan2(x, y)), atol=5e-3)


def test_agl_and_outside_is_nan():
    a = syn.plane(50.0, 0.0, 0.0)
    g = a.grid(100.0, 10.0)
    pts = np.array([[0.0, 0.0, 170.0], [10.0, -20.0, 40.0], [500.0, 0.0, 100.0]])
    agl = g.agl(pts)
    np.testing.assert_allclose(agl[:2], [120.0, -10.0])
    assert np.isnan(agl[2])


def test_shapes_broadcast():
    g = syn.gaussian().grid(500.0, 10.0)
    x = np.zeros((4, 5))
    assert g.elevation(x, 0.0).shape == (4, 5)
    assert g.normal(x, x).shape == (4, 5, 3)
    assert g.agl(np.zeros((7, 3))).shape == (7,)


def test_save_load_roundtrip(tmp_path):
    from sargnc.terrain.frames import LocalENU

    g = syn.gaussian().grid(200.0, 10.0)
    g.frame = LocalENU(47.25, 9.38, 0.0)
    g.meta = {"k": 1}
    g.save(tmp_path / "t.npz")
    h = type(g).load(tmp_path / "t.npz")
    np.testing.assert_allclose(h.z, g.z, atol=1e-3)
    assert h.frame == g.frame and h.meta == {"k": 1} and h.d == g.d
