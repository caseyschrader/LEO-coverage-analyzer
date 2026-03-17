"""OpenTopography API integration for DEM / horizon elevation angle analysis."""

import io
import math

import numpy as np
import requests

OPENTOPO_URL = "https://portal.opentopography.org/API/globaldem"
# SRTMGL1 = 30m resolution (requires API key)
# SRTMGL3 = 90m resolution (free, no key needed for small areas)
DEM_TYPE = "SRTMGL1"


def fetch_dem_patch(
    south: float,
    north: float,
    west: float,
    east: float,
    api_key: str,
    dem_type: str = DEM_TYPE,
) -> tuple:
    """
    Fetch a DEM patch from OpenTopography as a numpy array.

    Returns:
        (elevation_array: np.ndarray, transform, crs)
    """
    import rasterio

    params = {
        "demtype": dem_type,
        "south": south,
        "north": north,
        "west": west,
        "east": east,
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }

    resp = requests.get(OPENTOPO_URL, params=params, timeout=60)
    resp.raise_for_status()

    with rasterio.open(io.BytesIO(resp.content)) as ds:
        elev = ds.read(1).astype(float)
        nodata = ds.nodata
        if nodata is not None:
            elev[elev == nodata] = np.nan
        return elev, ds.transform, ds.crs


def horizon_elevation_angle(
    lat: float,
    lon: float,
    elev_array: np.ndarray,
    transform,
    n_directions: int = 8,
    distances_m: list = None,
) -> float:
    """
    Estimate the maximum horizon elevation angle (degrees) around a point.

    Samples elevation at n_directions compass headings × multiple distances,
    computes arctan((h_sample - h_center) / distance) for each, and returns
    the maximum (worst-case obstruction).

    Starlink needs approximately 100° unobstructed sky view, which roughly
    corresponds to keeping the horizon clear below ~25-40° elevation angle.
    An angle > 20° in any direction is considered significant obstruction.
    """
    if distances_m is None:
        distances_m = [500, 1000, 2000]  # metres

    # Get pixel coordinates of the center point
    inv_transform = ~transform
    c_col, c_row = inv_transform * (lon, lat)
    c_row, c_col = int(round(c_row)), int(round(c_col))

    h0 = elev_array[
        max(0, min(c_row, elev_array.shape[0] - 1)),
        max(0, min(c_col, elev_array.shape[1] - 1)),
    ]
    if np.isnan(h0):
        return 0.0

    max_angle = 0.0
    step = 360 // n_directions

    for bearing_deg in range(0, 360, step):
        bearing_rad = math.radians(bearing_deg)
        cos_lat = math.cos(math.radians(lat))

        for dist_m in distances_m:
            dlat = (dist_m * math.cos(bearing_rad)) / 111_320.0
            dlon = (dist_m * math.sin(bearing_rad)) / (111_320.0 * cos_lat)

            s_lat = lat + dlat
            s_lon = lon + dlon

            s_col, s_row = inv_transform * (s_lon, s_lat)
            s_row, s_col = int(round(s_row)), int(round(s_col))

            if 0 <= s_row < elev_array.shape[0] and 0 <= s_col < elev_array.shape[1]:
                h_s = elev_array[s_row, s_col]
                if not np.isnan(h_s):
                    angle = math.degrees(math.atan2(h_s - h0, dist_m))
                    max_angle = max(max_angle, angle)

    return max_angle
