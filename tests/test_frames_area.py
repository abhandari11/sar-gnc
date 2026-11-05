import numpy as np
import pytest

from sargnc.terrain import AreaSpec, LocalENU


def test_enu_roundtrip_and_curvature():
    f = LocalENU(47.25, 9.38, 0.0)
    e, n, u = np.array([1500.0, -800.0]), np.array([-1200.0, 2000.0]), np.array([1800.0, 0.0])
    lat, lon, h = f.enu_to_geodetic(e, n, u)
    e2, n2, u2 = f.geodetic_to_enu(lat, lon, h)
    np.testing.assert_allclose([e2, n2, u2], [e, n, u], atol=1e-6)
    # a point on the ellipsoid 2 km away drops ~ d^2 / 2R below the tangent plane
    lat, lon, _ = f.enu_to_geodetic(2000.0, 0.0, 0.0)
    _, _, u0 = f.geodetic_to_enu(lat, lon, 0.0)
    assert u0 == pytest.approx(-2000.0**2 / (2 * 6.38e6), rel=0.02)


def test_lv95_roundtrip():
    f = LocalENU(47.25, 9.38, 0.0)
    x, y, h = f.enu_to_crs(100.0, 200.0, 1500.0, "EPSG:2056")
    assert 2.7e6 < x < 2.8e6 and 1.2e6 < y < 1.3e6
    e, n, u = f.crs_to_enu(x, y, h, "EPSG:2056")
    np.testing.assert_allclose([e, n, u], [100.0, 200.0, 1500.0], atol=1e-2)  # pyproj CH1903+ pipeline ~1 mm


def test_area_validation():
    a = AreaSpec("t", 47.0, 9.0)
    assert a.domain_bounds == (-2000.0, 2000.0, -2000.0, 2000.0)
    with pytest.raises(ValueError, match="buffer"):
        AreaSpec("t", 47.0, 9.0, buffer_m=500.0)
    with pytest.raises(ValueError, match="lat/lon"):
        AreaSpec("t", 147.0, 9.0)
