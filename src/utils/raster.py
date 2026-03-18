"""Rasterio helpers for sampling raster data at point locations."""

import numpy as np


def sample_raster_at_points(raster_path: str, lats: list, lons: list) -> np.ndarray:
    """
    Sample raster values at (lat, lon) point locations.

    Uses rasterio.DatasetReader.sample() for on-disk point sampling — avoids
    loading the full raster band into memory (critical for CONUS-scale files).
    Automatically reprojects WGS84 coordinates to the raster's native CRS.

    Returns array of float values; nodata pixels → NaN.
    """
    import rasterio
    from pyproj import Transformer

    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)

    with rasterio.open(raster_path) as src:
        nodata = src.nodata

        # Reproject WGS84 lon/lat to the raster's native CRS if needed
        raster_crs = src.crs.to_epsg()
        if raster_crs != 4326:
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            xs, ys = transformer.transform(lons, lats)
        else:
            xs, ys = lons, lats

        coords = list(zip(xs, ys))
        values = np.array([val[0] for val in src.sample(coords)], dtype=float)

        if nodata is not None:
            values[values == nodata] = np.nan

        return values


def get_raster_bounds(raster_path: str) -> dict:
    """Return geographic bounds (EPSG:4326) and CRS of a raster."""
    import rasterio
    from rasterio.warp import transform_bounds

    with rasterio.open(raster_path) as src:
        bounds_4326 = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        return {
            "min_lon": bounds_4326[0],
            "min_lat": bounds_4326[1],
            "max_lon": bounds_4326[2],
            "max_lat": bounds_4326[3],
            "crs": str(src.crs),
        }
