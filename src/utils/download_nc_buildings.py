#!/usr/bin/env python3
"""
Download and compile NC building footprints from Microsoft Global Building Footprints.

Workflow:
  1. Spatially filter the tile index for NC
  2. Derive parent quadkeys and look up download URLs
  3. Download/cache each .csv.gz tile (GeoJSONL format)
  4. Merge into a single GeoJSON

Usage:
  python utils/download_nc_buildings.py

Resumable: already-downloaded tiles are skipped on re-run.
"""

import gzip
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import box, shape

BASE_DIR = Path(__file__).parent.parent
INDEX_FILE = BASE_DIR / "data" / "buildings-with-height-coverage.geojson"
DATASET_FILE = BASE_DIR / "data" / "building_footprints_US_dataset.csv"
CACHE_DIR = BASE_DIR / "data" / ".tile_cache"
OUTPUT_FILE = BASE_DIR / "data" / "nc_buildings.geojson"
COMPLETED_LOG = CACHE_DIR / "completed.txt"

# NC bounding box: min_lon, min_lat, max_lon, max_lat
NC_BOUNDS = (-84.3218, 33.7528, -75.4601, 36.5881)


def get_nc_child_keys():
    print("Loading tile index...")
    index_gdf = gpd.read_file(INDEX_FILE)
    nc_shape = box(*NC_BOUNDS)
    nc_tiles = index_gdf[index_gdf.intersects(nc_shape)]
    keys = nc_tiles["quadkey"].tolist()
    print(f"  {len(keys)} index tiles intersect NC")
    return keys


def child_to_parent(key):
    """Strip leading 0 and last 2 chars: 11-char child -> 8-char parent."""
    return key[1:-2]


def get_tile_urls(child_keys):
    df = pd.read_csv(DATASET_FILE, dtype={"QuadKey": str})
    parent_keys = list({child_to_parent(k) for k in child_keys})
    print(f"  {len(parent_keys)} unique parent quadkeys")

    matches = df[df["QuadKey"].isin(parent_keys)][["QuadKey", "Url"]]
    missing = set(parent_keys) - set(matches["QuadKey"])
    if missing:
        print(f"  Warning: {len(missing)} parent keys not found in dataset")

    return matches.to_dict("records")


def load_completed():
    if COMPLETED_LOG.exists():
        return set(COMPLETED_LOG.read_text().splitlines())
    return set()


def mark_completed(quadkey):
    with open(COMPLETED_LOG, "a") as f:
        f.write(quadkey + "\n")


def download_tile(quadkey, url):
    """Download tile to cache and return local path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{quadkey}.csv.gz"
    if cache_path.exists():
        return cache_path

    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(cache_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
    return cache_path


def parse_tile(cache_path):
    """Parse a GeoJSONL .csv.gz tile into a GeoDataFrame."""
    features = []
    with gzip.open(cache_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            feat = json.loads(line)
            props = feat.get("properties", {})
            geom = shape(feat["geometry"])
            props["geometry"] = geom
            features.append(props)

    if not features:
        return None

    gdf = gpd.GeoDataFrame(features, geometry="geometry", crs="EPSG:4326")
    return gdf


def main():
    print("=== NC Building Footprints Download ===\n")

    # Step 1: find tiles
    child_keys = get_nc_child_keys()

    # Step 2: get URLs
    print("\nLooking up download URLs...")
    tiles = get_tile_urls(child_keys)
    print(f"  {len(tiles)} tiles to download\n")

    if not tiles:
        print("No matching tiles found. Exiting.")
        sys.exit(1)

    # Step 3: download + parse (resumable)
    completed = load_completed()
    n_skipped = sum(1 for t in tiles if t["QuadKey"] in completed)
    if n_skipped:
        print(f"Resuming: {n_skipped} tiles already completed, skipping.\n")

    gdfs = []
    for i, tile in enumerate(tiles, 1):
        qk = tile["QuadKey"]
        url = tile["Url"]
        prefix = f"[{i}/{len(tiles)}] {qk}"

        if qk in completed:
            cache_path = CACHE_DIR / f"{qk}.csv.gz"
            print(f"{prefix} (cached) - parsing...")
        else:
            print(f"{prefix} - downloading...")
            try:
                cache_path = download_tile(qk, url)
            except Exception as e:
                print(f"  ERROR downloading {qk}: {e}")
                continue

        try:
            gdf = parse_tile(cache_path)
        except Exception as e:
            print(f"  ERROR parsing {qk}: {e}")
            continue

        if gdf is None or gdf.empty:
            print(f"  (empty tile, skipping)")
            mark_completed(qk)
            continue

        gdfs.append(gdf)
        if qk not in completed:
            mark_completed(qk)
        print(f"  -> {len(gdf):,} buildings")

    if not gdfs:
        print("\nNo data parsed. Exiting.")
        sys.exit(1)

    # Step 4: merge and save
    print(f"\nMerging {len(gdfs)} tiles...")
    merged = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")
    print(f"Total buildings: {len(merged):,}")

    print(f"Saving to {OUTPUT_FILE}...")
    merged.to_file(OUTPUT_FILE, driver="GeoJSON")
    print("\nDone.")


if __name__ == "__main__":
    main()
