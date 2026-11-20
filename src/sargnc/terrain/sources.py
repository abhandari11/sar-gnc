"""DEM tile sources. Each source downloads native tiles into data/raw/<source>/."""

from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Protocol

import requests


class DemSource(Protocol):
    name: str
    crs: str
    native_resolution_m: float

    def fetch(self, lon_min: float, lat_min: float, lon_max: float, lat_max: float, dest: Path) -> list[Path]:
        """Download all tiles covering the WGS84 bbox; return local GeoTIFF paths."""
        ...


class SwissAlti3D:
    """swisstopo swissALTI3D 2 m DEM (LV95 / LN02), open data via the geo.admin.ch STAC API."""

    name = "swissalti3d"
    crs = "EPSG:2056"
    native_resolution_m = 2.0
    _items_url = "https://data.geo.admin.ch/api/stac/v0.9/collections/ch.swisstopo.swissalti3d/items"
    _asset_re = re.compile(r"swissalti3d_(\d{4})_(\d{4}-\d{4})_2_2056_5728\.tif$")

    def _list_assets(self, bbox: tuple[float, float, float, float]) -> dict[str, tuple[int, str]]:
        """Latest-year 2 m GeoTIFF href per tile id."""
        latest: dict[str, tuple[int, str]] = {}
        url: str | None = self._items_url
        params: dict | None = {"bbox": ",".join(f"{v:.6f}" for v in bbox), "limit": 100}
        while url:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            page = r.json()
            for feat in page["features"]:
                for key, asset in feat["assets"].items():
                    m = self._asset_re.search(key)
                    if m:
                        year, tile = int(m.group(1)), m.group(2)
                        if tile not in latest or year > latest[tile][0]:
                            latest[tile] = (year, asset["href"])
            url = next((lk["href"] for lk in page.get("links", []) if lk.get("rel") == "next"), None)
            params = None
        return latest

    def fetch(self, lon_min: float, lat_min: float, lon_max: float, lat_max: float, dest: Path) -> list[Path]:
        dest.mkdir(parents=True, exist_ok=True)
        assets = self._list_assets((lon_min, lat_min, lon_max, lat_max))
        if not assets:
            raise RuntimeError("swissALTI3D: no tiles in bbox; is the area inside Switzerland?")
        paths = []
        for tile, (year, href) in sorted(assets.items()):
            path = dest / Path(href).name
            if not path.exists():
                _download(href, path)
            paths.append(path)
        return paths


class CopernicusGLO30:
    """Copernicus DEM GLO-30 (~30 m, WGS84 / EGM2008), open COGs on the AWS Open Data bucket.

    One 1x1 degree tile per integer lat/lon cell; ocean-only cells have no tile.
    """

    name = "copernicus_glo30"
    crs = "EPSG:4326"
    native_resolution_m = 30.0
    _url = "https://copernicus-dem-30m.s3.amazonaws.com/{id}/{id}.tif"

    @staticmethod
    def tile_id(lat: int, lon: int) -> str:
        ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
        return f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"

    def fetch(self, lon_min: float, lat_min: float, lon_max: float, lat_max: float, dest: Path) -> list[Path]:
        dest.mkdir(parents=True, exist_ok=True)
        paths = []
        for lat in range(math.floor(lat_min), math.floor(lat_max) + 1):
            for lon in range(math.floor(lon_min), math.floor(lon_max) + 1):
                tid = self.tile_id(lat, lon)
                path = dest / f"{tid}.tif"
                if not path.exists():
                    _download(self._url.format(id=tid), path)
                paths.append(path)
        return paths


def _download(href: str, path: Path, attempts: int = 3) -> None:
    for attempt in range(attempts):
        try:
            with requests.get(href, timeout=120, stream=True) as r:
                r.raise_for_status()
                tmp = path.with_suffix(".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.rename(path)
            return
        except requests.RequestException:
            if attempt == attempts - 1:
                raise
            time.sleep(2.0)


SOURCES: dict[str, type] = {"swissalti3d": SwissAlti3D, "copernicus_glo30": CopernicusGLO30}


def get_source(name: str) -> DemSource:
    try:
        return SOURCES[name]()
    except KeyError:
        raise ValueError(f"unknown dem_source '{name}'; available: {sorted(SOURCES)}") from None
