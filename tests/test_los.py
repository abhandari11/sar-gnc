import numpy as np

from sargnc.terrain import line_of_sight, ray_intersect
from sargnc.terrain import synthetic as syn


def test_ray_plane_analytic():
    a = syn.plane(100.0, 0.2, -0.1)
    g = a.grid(1000.0, 10.0)
    rng = np.random.default_rng(2)
    n = 400
    o = np.column_stack([rng.uniform(-300, 300, (n, 2)), rng.uniform(400, 800, n)])
    v = np.column_stack([rng.uniform(-1, 1, (n, 2)), -rng.uniform(0.3, 1.0, n)])
    t, p = ray_intersect(g, o, v)
    u = v / np.linalg.norm(v, axis=1, keepdims=True)
    # plane: z = 100 + 0.2x - 0.1y ; o_z + t u_z = 100 + 0.2(o_x + t u_x) - 0.1(o_y + t u_y)
    t_ref = (100 + 0.2 * o[:, 0] - 0.1 * o[:, 1] - o[:, 2]) / (u[:, 2] - 0.2 * u[:, 0] + 0.1 * u[:, 1])
    inside = np.all(np.abs(o[:, :2] + t_ref[:, None] * u[:, :2]) <= 1000, axis=1)
    np.testing.assert_allclose(t[inside], t_ref[inside], rtol=1e-9, atol=1e-6)
    assert np.all(np.isnan(t[~inside]))
    np.testing.assert_allclose(g.agl(p[inside]), 0.0, atol=1e-6)


def test_ray_matches_dense_march_on_gaussian():
    g = syn.gaussian(300.0, 120.0, 1000.0).grid(600.0, 10.0)
    rng = np.random.default_rng(3)
    n = 300
    o = np.column_stack([rng.uniform(-550, 550, (n, 2)), rng.uniform(1050, 1400, n)])
    v = np.column_stack([rng.uniform(-1, 1, (n, 2)), -rng.uniform(0.05, 0.6, n)])
    t, _ = ray_intersect(g, o, v)
    u = v / np.linalg.norm(v, axis=1, keepdims=True)
    s = np.arange(0, 3000, 0.01)
    for k in range(n):
        pts = o[k] + s[:, None] * u[k]
        f = g.agl(pts)
        below = np.flatnonzero(f <= 0)
        out = np.flatnonzero(np.isnan(f))
        if below.size and (not out.size or below[0] < out[0]):
            assert abs(t[k] - s[below[0]]) < 0.02
        else:
            assert np.isnan(t[k])


def test_vertical_and_upward_rays():
    g = syn.gaussian(300.0, 150.0, 1000.0).grid(500.0, 10.0)
    t, p = ray_intersect(g, [[0.0, 0.0, 2000.0]], [[0.0, 0.0, -1.0]])
    np.testing.assert_allclose(t, 2000.0 - 1300.0, atol=1e-6)
    t, _ = ray_intersect(g, [[0.0, 0.0, 2000.0]], [[0.3, 0.1, 1.0]])
    assert np.isnan(t[0])
    t, _ = ray_intersect(g, [[0.0, 0.0, 1200.0]], [[1.0, 0.0, 0.0]])  # starts under the summit
    assert t[0] == 0.0


def test_los_over_hill():
    g = syn.gaussian(300.0, 150.0, 1000.0).grid(800.0, 10.0)
    low_w, low_e = [-600.0, 0.0, 1010.0], [600.0, 0.0, 1010.0]
    high_w, high_e = [-600.0, 0.0, 1400.0], [600.0, 0.0, 1400.0]
    assert not line_of_sight(g, low_w, low_e)
    assert line_of_sight(g, high_w, high_e)
    # observer above the summit sees a target lying on the far flank
    tgt = [300.0, 0.0, float(g.elevation(300.0, 0.0))]
    assert line_of_sight(g, [0.0, 0.0, 1500.0], tgt)
    # but not from behind the hill at low altitude
    assert not line_of_sight(g, [-500.0, 0.0, 1050.0], tgt)


def test_los_vectorised_shape():
    g = syn.plane(0.0, 0.0, 0.0).grid(500.0, 10.0)
    p1 = np.column_stack([np.linspace(-400, 400, 9), np.zeros(9), np.zeros(9)])
    vis = line_of_sight(g, [0.0, 0.0, 100.0], p1)
    assert vis.shape == (9,) and vis.all()
