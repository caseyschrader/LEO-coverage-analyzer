"""
Risk Analyzer — scores each location for satellite dish obstruction risk.

Risk factors
  1. Tree Canopy Cover (TCC)    — from NLCD raster (always available)
  2. Terrain obstruction         — max horizon elevation angle from DEM (optional)
  3. Building obstruction        — max horizon angle from neighboring buildings (optional)

Scoring weights
  TCC 0.4 · terrain 0.2 · buildings 0.4
  When terrain is unavailable:  TCC 0.5 · buildings 0.5
  When buildings are unavailable: TCC 0.7 · terrain 0.3  (legacy behavior)
  When neither terrain nor buildings: risk_score = tcc_score

Risk tiers (score → tier)
  < 0.30  → LOW
  0.30–0.59 → MEDIUM
  ≥ 0.60  → HIGH

TCC score mapping  (0–100 % → 0–1)  
  0 %   → 0.0   (no canopy, clear sky)
  80 %+ → 1.0   (dense canopy)

Terrain score mapping  (horizon angle in degrees → 0–1)
  0 °   → 0.0   (flat terrain)
  30 °+ → 1.0   (significant terrain obstruction; Starlink ~25-40° clearance needed)

Building score mapping  (horizon angle in degrees → 0–1)
  0 °   → 0.0   (no taller neighbors)
  30 °+ → 1.0   (significant building obstruction)
"""

import math

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from utils.raster import sample_raster_at_points

# These weights are arbitrary and need more consideration.

TCC_WEIGHT = 0.4
TERRAIN_WEIGHT = 0.2
BUILDING_WEIGHT = 0.4

LOW_THRESHOLD = 0.30
HIGH_THRESHOLD = 0.60

# Search radius for neighboring buildings (meters).
# 100 m captures tall commercial buildings at meaningful distances.
# Really this is a magic number that needs more consideration.
BUILDING_SEARCH_RADIUS_M = 100

# Height assumed for locations with no matching building footprint or height=-1.
DEFAULT_LOCATION_HEIGHT_M = 0


def _tcc_score(tcc_pct: float) -> float:
    if np.isnan(tcc_pct) or tcc_pct < 0:
        return 0.0
    return min(float(tcc_pct) / 80.0, 1.0)


def _terrain_score(angle_deg: float) -> float:
    if np.isnan(angle_deg) or angle_deg <= 0:
        return 0.0
    return min(float(angle_deg) / 30.0, 1.0)


def _building_score(angle_deg: float) -> float:
    if np.isnan(angle_deg) or angle_deg <= 0:
        return 0.0
    return min(float(angle_deg) / 30.0, 1.0)


def _risk_tier(score: float) -> str:
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= LOW_THRESHOLD:
        return "MEDIUM"
    return "LOW"


class RiskAnalyzer:
    def __init__(self, elevation_api_key: str = None):
        self.elevation_api_key = elevation_api_key

    def analyze(self, gdf: gpd.GeoDataFrame, data_paths: dict) -> gpd.GeoDataFrame:
        """
        Compute obstruction risk scores for every location in gdf.

        Adds columns: tcc_pct, tcc_score, terrain_angle, terrain_score,
                      building_angle, building_score, risk_score, risk_tier
        """
        result = gdf.copy()

        # ── Tree Canopy Cover ──────────────────────────────────────────────────
        print(f"[RiskAnalyzer] Sampling TCC for {len(result):,} locations")
        tcc_values = sample_raster_at_points(
            data_paths["tcc"],
            result["latitude"].tolist(),
            result["longitude"].tolist(),
        )
        result["tcc_pct"] = tcc_values
        result["tcc_score"] = result["tcc_pct"].apply(_tcc_score)

        # ── Terrain / Elevation (optional) ────────────────────────────────────
        use_terrain = bool(self.elevation_api_key)

        if use_terrain:
            print("[RiskAnalyzer] Fetching DEM and computing horizon angles")
            terrain_angles = self._compute_terrain_angles(result)
            result["terrain_angle"] = terrain_angles
            result["terrain_score"] = result["terrain_angle"].apply(_terrain_score)
        else:
            print("[RiskAnalyzer] No elevation API key — skipping terrain scores")
            result["terrain_angle"] = np.nan
            result["terrain_score"] = np.nan

        # ── Building obstruction (optional) ───────────────────────────────────
        use_buildings = "buildings" in data_paths

        if use_buildings:
            print("[RiskAnalyzer] Loading buildings and computing obstruction angles")
            building_angles = self._compute_building_angles(result, data_paths["buildings"])
            result["building_angle"] = building_angles
            result["building_score"] = result["building_angle"].apply(_building_score)
        else:
            print("[RiskAnalyzer] No buildings path — skipping building scores")
            result["building_angle"] = np.nan
            result["building_score"] = np.nan

        # ── Composite risk score ───────────────────────────────────────────────
        if use_terrain and use_buildings:
            result["risk_score"] = (
                TCC_WEIGHT * result["tcc_score"]
                + TERRAIN_WEIGHT * result["terrain_score"]
                + BUILDING_WEIGHT * result["building_score"]
            )
        elif use_buildings:
            # Normalize TCC and buildings weights (drop terrain)
            w_tcc = TCC_WEIGHT / (TCC_WEIGHT + BUILDING_WEIGHT)
            w_bld = BUILDING_WEIGHT / (TCC_WEIGHT + BUILDING_WEIGHT)
            result["risk_score"] = (
                w_tcc * result["tcc_score"] + w_bld * result["building_score"]
            )
        elif use_terrain:
            result["risk_score"] = (
                0.7 * result["tcc_score"] + 0.3 * result["terrain_score"]
            )
        else:
            result["risk_score"] = result["tcc_score"]

        result["risk_tier"] = result["risk_score"].apply(_risk_tier)

        tier_counts = result["risk_tier"].value_counts().to_dict()
        print(f"[RiskAnalyzer] Distribution: {tier_counts}")

        return result

    def _compute_terrain_angles(self, gdf: gpd.GeoDataFrame) -> pd.Series:
        from utils.elevation import fetch_dem_patch, horizon_elevation_angle

        bounds = gdf.total_bounds  # (min_lon, min_lat, max_lon, max_lat)
        buf = 0.05  # ~5 km buffer for horizon sampling beyond the bbox edge

        try:
            elev_array, transform, _ = fetch_dem_patch(
                south=bounds[1] - buf,
                north=bounds[3] + buf,
                west=bounds[0] - buf,
                east=bounds[2] + buf,
                api_key=self.elevation_api_key,
            )
        except Exception as exc:
            print(f"[RiskAnalyzer] DEM fetch failed ({exc}) — skipping terrain scores")
            return pd.Series([np.nan] * len(gdf), index=gdf.index)

        angles = [
            horizon_elevation_angle(
                lat=row.latitude,
                lon=row.longitude,
                elev_array=elev_array,
                transform=transform,
            )
            for row in gdf.itertuples()
        ]
        return pd.Series(angles, index=gdf.index)

    def _compute_building_angles(
        self, gdf: gpd.GeoDataFrame, buildings_path: str
    ) -> pd.Series:
        """
        For each location, find taller neighboring buildings within
        BUILDING_SEARCH_RADIUS_M and return the maximum obstruction angle (degrees).

        The location height defaults to DEFAULT_LOCATION_HEIGHT_M when the point
        falls outside any building footprint or the footprint has height == -1.
        Neighbor heights of -1 are treated as 0 (unknown → no contribution).
        """
        bounds = gdf.total_bounds  # (min_lon, min_lat, max_lon, max_lat)
        mid_lat = (bounds[1] + bounds[3]) / 2
        cos_lat = math.cos(math.radians(mid_lat))
        buf_deg_lat = BUILDING_SEARCH_RADIUS_M / 111_320.0
        buf_deg_lon = BUILDING_SEARCH_RADIUS_M / (111_320.0 * cos_lat)

        # Load only buildings that intersect the analysis area (+ search radius).
        load_bbox = (
            bounds[0] - buf_deg_lon,
            bounds[1] - buf_deg_lat,
            bounds[2] + buf_deg_lon,
            bounds[3] + buf_deg_lat,
        )
        buildings = gpd.read_file(buildings_path, bbox=load_bbox)
        print(f"[RiskAnalyzer] Loaded {len(buildings):,} buildings in analysis area")

        if buildings.empty:
            return pd.Series([0.0] * len(gdf), index=gdf.index)

        sindex = buildings.sindex

        angles = []
        for row in gdf.itertuples():
            lat, lon = row.latitude, row.longitude
            cos_lat_loc = math.cos(math.radians(lat))
            buf_lat = BUILDING_SEARCH_RADIUS_M / 111_320.0
            buf_lon = BUILDING_SEARCH_RADIUS_M / (111_320.0 * cos_lat_loc)

            candidate_idx = list(
                sindex.intersection((lon - buf_lon, lat - buf_lat, lon + buf_lon, lat + buf_lat))
            )

            if not candidate_idx:
                angles.append(0.0)
                continue

            candidates = buildings.iloc[candidate_idx]

            # Determine location building height.
            pt = Point(lon, lat)
            containing = candidates[candidates.contains(pt)]
            if not containing.empty:
                loc_h = containing.iloc[0]["height"]
                if loc_h < 0:
                    loc_h = DEFAULT_LOCATION_HEIGHT_M
            else:
                loc_h = DEFAULT_LOCATION_HEIGHT_M

            # Find max obstruction angle from taller neighbors.
            max_angle = 0.0
            for bldg in candidates.itertuples():
                bldg_h = bldg.height if bldg.height >= 0 else 0.0
                if bldg_h <= loc_h:
                    continue

                centroid = bldg.geometry.centroid
                dlat_m = (centroid.y - lat) * 111_320.0
                dlon_m = (centroid.x - lon) * 111_320.0 * cos_lat_loc
                dist_m = math.hypot(dlat_m, dlon_m)

                if dist_m < 1.0:
                    continue  # same footprint

                angle = math.degrees(math.atan2(bldg_h - loc_h, dist_m))
                max_angle = max(max_angle, angle)

            angles.append(max_angle)

        return pd.Series(angles, index=gdf.index)
