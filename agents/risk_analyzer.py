"""
Risk Analyzer — scores each location for satellite dish obstruction risk.

Risk factors
  1. Tree Canopy Cover (TCC)  — from NLCD raster (always available)
  2. Terrain obstruction       — max horizon elevation angle from DEM (optional)

Scoring
  - TCC alone (no elevation):   risk_score = tcc_score
  - TCC + terrain:              risk_score = 0.7 * tcc_score + 0.3 * terrain_score

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
"""

import numpy as np
import pandas as pd
import geopandas as gpd

from utils.raster import sample_raster_at_points

TCC_WEIGHT = 0.7
TERRAIN_WEIGHT = 0.3

LOW_THRESHOLD = 0.30
HIGH_THRESHOLD = 0.60


def _tcc_score(tcc_pct: float) -> float:
    if np.isnan(tcc_pct) or tcc_pct < 0:
        return 0.0
    return min(float(tcc_pct) / 80.0, 1.0)


def _terrain_score(angle_deg: float) -> float:
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
                      risk_score, risk_tier
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
            result["risk_score"] = (
                TCC_WEIGHT * result["tcc_score"]
                + TERRAIN_WEIGHT * result["terrain_score"]
            )
        else:
            print("[RiskAnalyzer] No elevation API key — risk based on TCC only")
            result["terrain_angle"] = np.nan
            result["terrain_score"] = np.nan
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
