"""
Ingester — loads, validates, and spatially filters the locations CSV.

Inputs:
  - csv_path: locations CSV (location_id, latitude, longitude, ...)
  - tcc_path: NLCD Tree Canopy Cover GeoTIFF
  - bbox: dict {min_lat, max_lat, min_lon, max_lon}

Outputs:
  - GeoDataFrame of filtered locations (EPSG:4326)
  - data_paths dict pointing to validated source files
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from utils.raster import get_raster_bounds


class IngestAgent:
    def __init__(self, csv_path: str, tcc_path: str):
        self.csv_path = csv_path
        self.tcc_path = tcc_path

    def run(self, bbox: dict) -> tuple:
        """
        Filter and validate locations within bounding box.

        Returns:
            (GeoDataFrame, data_paths dict)
        """
        print(f"[Ingester] Loading CSV: {self.csv_path}")
        df = self._load_csv()

        print(f"[Ingester] Filtering {len(df):,} locations to bbox")
        gdf = self._filter_to_bbox(df, bbox)
        print(f"[Ingester] {len(gdf):,} locations within bbox")

        if len(gdf) == 0:
            raise ValueError(
                f"No locations found in bounding box "
                f"lat [{bbox['min_lat']:.3f}, {bbox['max_lat']:.3f}], "
                f"lon [{bbox['min_lon']:.3f}, {bbox['max_lon']:.3f}]. "
                "Try a larger region or verify the CSV covers this area."
            )

        self._validate_tcc_coverage(bbox)

        data_paths = {"tcc": self.tcc_path}
        return gdf, data_paths

    # ── Private helpers ────────────────────────────────────────────────────────

    def _load_csv(self) -> pd.DataFrame:
        df = pd.read_csv(self.csv_path)

        required = {"latitude", "longitude", "location_id"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")

        before = len(df)
        df = df.dropna(subset=["latitude", "longitude"])
        df = df[
            df["latitude"].between(-90, 90) & df["longitude"].between(-180, 180)
        ].copy()

        dropped = before - len(df)
        if dropped:
            print(f"[Ingester] Dropped {dropped} rows with invalid coordinates")

        return df

    def _filter_to_bbox(self, df: pd.DataFrame, bbox: dict) -> gpd.GeoDataFrame:
        mask = (
            df["latitude"].between(bbox["min_lat"], bbox["max_lat"])
            & df["longitude"].between(bbox["min_lon"], bbox["max_lon"])
        )
        filtered = df[mask].copy()

        geometry = [Point(row.longitude, row.latitude) for row in filtered.itertuples()]
        return gpd.GeoDataFrame(filtered, geometry=geometry, crs="EPSG:4326")

    def _validate_tcc_coverage(self, bbox: dict):
        tcc = get_raster_bounds(self.tcc_path)
        issues = []

        checks = [
            (bbox["min_lat"] < tcc["min_lat"], f"bbox south {bbox['min_lat']:.3f} < TCC south {tcc['min_lat']:.3f}"),
            (bbox["max_lat"] > tcc["max_lat"], f"bbox north {bbox['max_lat']:.3f} > TCC north {tcc['max_lat']:.3f}"),
            (bbox["min_lon"] < tcc["min_lon"], f"bbox west {bbox['min_lon']:.3f} < TCC west {tcc['min_lon']:.3f}"),
            (bbox["max_lon"] > tcc["max_lon"], f"bbox east {bbox['max_lon']:.3f} > TCC east {tcc['max_lon']:.3f}"),
        ]

        for condition, msg in checks:
            if condition:
                issues.append(msg)

        if issues:
            print(f"[Ingester] WARNING — partial TCC coverage: {'; '.join(issues)}")
        else:
            print("[Ingester] TCC coverage confirmed for bbox")
