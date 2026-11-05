"""Numba kernels for height-field interpolation and exact ray/bilinear-patch intersection.

Grid convention: z[i, j] is the height at (x0 + j*d, y0 + i*d); i indexes north, j east.
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit, prange

BILINEAR = 0
BICUBIC = 1


@njit(cache=True, inline="always")
def _cell(g: float, n: int) -> tuple[int, float]:
    c = int(math.floor(g))
    if c > n - 2:
        c = n - 2
    if c < 0:
        c = 0
    return c, g - c


@njit(cache=True)
def _bilinear(z, x0, y0, d, x, y):
    ny, nx = z.shape
    gx = (x - x0) / d
    gy = (y - y0) / d
    if not (0.0 <= gx <= nx - 1 and 0.0 <= gy <= ny - 1):
        return np.nan, np.nan, np.nan
    j, u = _cell(gx, nx)
    i, v = _cell(gy, ny)
    z00 = z[i, j]
    z10 = z[i, j + 1]
    z01 = z[i + 1, j]
    z11 = z[i + 1, j + 1]
    p = z10 - z00
    q = z01 - z00
    r = z00 - z10 - z01 + z11
    h = z00 + p * u + q * v + r * u * v
    return h, (p + r * v) / d, (q + r * u) / d


@njit(cache=True, inline="always")
def _cr_weights(t):
    t2 = t * t
    t3 = t2 * t
    w = (
        0.5 * (-t3 + 2.0 * t2 - t),
        0.5 * (3.0 * t3 - 5.0 * t2 + 2.0),
        0.5 * (-3.0 * t3 + 4.0 * t2 + t),
        0.5 * (t3 - t2),
    )
    dw = (
        0.5 * (-3.0 * t2 + 4.0 * t - 1.0),
        0.5 * (9.0 * t2 - 10.0 * t),
        0.5 * (-9.0 * t2 + 8.0 * t + 1.0),
        0.5 * (3.0 * t2 - 2.0 * t),
    )
    return w, dw


@njit(cache=True)
def _bicubic(z, x0, y0, d, x, y):
    """Catmull-Rom (cubic convolution, a=-0.5) with edge replication; C1 continuous."""
    ny, nx = z.shape
    gx = (x - x0) / d
    gy = (y - y0) / d
    if not (0.0 <= gx <= nx - 1 and 0.0 <= gy <= ny - 1):
        return np.nan, np.nan, np.nan
    j, u = _cell(gx, nx)
    i, v = _cell(gy, ny)
    wu, dwu = _cr_weights(u)
    wv, dwv = _cr_weights(v)
    h = 0.0
    hx = 0.0
    hy = 0.0
    for a in range(4):
        ii = min(max(i - 1 + a, 0), ny - 1)
        row = 0.0
        drow = 0.0
        for b in range(4):
            jj = min(max(j - 1 + b, 0), nx - 1)
            row += wu[b] * z[ii, jj]
            drow += dwu[b] * z[ii, jj]
        h += wv[a] * row
        hx += wv[a] * drow
        hy += dwv[a] * row
    return h, hx / d, hy / d


@njit(cache=True, parallel=True)
def sample(z, x0, y0, d, xs, ys, method):
    """Height and gradient (dz/dx, dz/dy) at points; NaN outside the grid."""
    n = xs.shape[0]
    h = np.empty(n)
    gx = np.empty(n)
    gy = np.empty(n)
    for k in prange(n):
        if method == BICUBIC:
            h[k], gx[k], gy[k] = _bicubic(z, x0, y0, d, xs[k], ys[k])
        else:
            h[k], gx[k], gy[k] = _bilinear(z, x0, y0, d, xs[k], ys[k])
    return h, gx, gy


@njit(cache=True, inline="always")
def _first_root(a2, a1, a0, s_max):
    """Smallest s in [0, s_max] with a2 s^2 + a1 s + a0 <= 0 given a0 > 0; else NaN."""
    if abs(a2) < 1e-12:
        if a1 < 0.0:
            s = -a0 / a1
            if s <= s_max:
                return s
        return np.nan
    disc = a1 * a1 - 4.0 * a2 * a0
    if disc < 0.0:
        return np.nan
    sq = math.sqrt(disc)
    qq = -0.5 * (a1 + math.copysign(sq, a1))
    r1 = qq / a2
    r2 = a0 / qq if qq != 0.0 else np.nan
    lo = min(r1, r2)
    hi = max(r1, r2)
    if 0.0 <= lo <= s_max:
        return lo
    if 0.0 <= hi <= s_max:
        return hi
    return np.nan


@njit(cache=True)
def _ray_one(z, x0, y0, d, ox, oy, oz, dx, dy, dz, t_max):
    """Distance along a unit ray to the first bilinear-surface hit, NaN if none in [0, t_max] inside the grid."""
    ny, nx = z.shape
    gx0 = (ox - x0) / d
    gy0 = (oy - y0) / d
    ax = dx / d
    ay = dy / d
    # Clip [0, t_max] to the grid box [0, nx-1] x [0, ny-1].
    t0 = 0.0
    t1 = t_max
    for g0, a, hi in ((gx0, ax, nx - 1.0), (gy0, ay, ny - 1.0)):
        if abs(a) < 1e-15:
            if g0 < 0.0 or g0 > hi:
                return np.nan
        else:
            ta = (0.0 - g0) / a
            tb = (hi - g0) / a
            if ta > tb:
                ta, tb = tb, ta
            t0 = max(t0, ta)
            t1 = min(t1, tb)
    if t0 > t1:
        return np.nan

    t = t0
    gx = gx0 + ax * t
    gy = gy0 + ay * t
    j, _ = _cell(gx, nx)
    i, _ = _cell(gy, ny)
    step_j = 1 if ax > 0 else -1
    step_i = 1 if ay > 0 else -1
    for _ in range(nx + ny + 4):
        # Exit parameter of the current cell.
        tx = np.inf
        if ax > 0:
            tx = (j + 1 - gx0) / ax
        elif ax < 0:
            tx = (j - gx0) / ax
        ty = np.inf
        if ay > 0:
            ty = (i + 1 - gy0) / ay
        elif ay < 0:
            ty = (i - gy0) / ay
        t_out = min(tx, ty, t1)

        u0 = gx0 + ax * t - j
        v0 = gy0 + ay * t - i
        z00 = z[i, j]
        z10 = z[i, j + 1]
        z01 = z[i + 1, j]
        z11 = z[i + 1, j + 1]
        p = z10 - z00
        q = z01 - z00
        r = z00 - z10 - z01 + z11
        h0 = z00 + p * u0 + q * v0 + r * u0 * v0
        h1 = p * ax + q * ay + r * (u0 * ay + v0 * ax)
        h2 = r * ax * ay
        rz = oz + dz * t
        f0 = rz - h0
        if f0 <= 0.0:
            return t
        zmax = max(max(z00, z10), max(z01, z11))
        if rz > zmax and rz + dz * (t_out - t) > zmax:
            s = np.nan
        else:
            s = _first_root(-h2, dz - h1, f0, t_out - t)
        if not np.isnan(s):
            return t + s
        if t_out >= t1:
            return np.nan
        t = t_out
        if tx <= ty:
            j += step_j
            if j < 0 or j > nx - 2:
                return np.nan
        if ty <= tx:
            i += step_i
            if i < 0 or i > ny - 2:
                return np.nan
    return np.nan


@njit(cache=True, parallel=True)
def ray_cast(z, x0, y0, d, origins, dirs, t_max):
    """Batched ray cast; dirs must be unit vectors. Returns hit distance (NaN = no hit)."""
    n = origins.shape[0]
    out = np.empty(n)
    for k in prange(n):
        out[k] = _ray_one(
            z, x0, y0, d,
            origins[k, 0], origins[k, 1], origins[k, 2],
            dirs[k, 0], dirs[k, 1], dirs[k, 2],
            t_max[k],
        )
    return out
