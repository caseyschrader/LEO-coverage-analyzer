"""
User-in-the-loop review helpers for the LEO risk pipeline.

Four intervention points:
  1. confirm_bbox        — preview map + confirm / override / abort after bbox resolution
  2. confirm_ingest      — show location count, confirm before expensive risk analysis
  3. review_thresholds   — show risk distribution, optionally adjust LOW/HIGH thresholds
  4. apply_thresholds    — re-tier risk scores after threshold adjustment
"""

import os

import contextily as ctx
import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from pyproj import Transformer


# ── 1. Bbox preview map ────────────────────────────────────────────────────────

def _generate_bbox_map(bbox: dict, output_dir: str) -> str:
    """Render the bounding box as a red rectangle over an OSM basemap."""
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

    min_x, min_y = transformer.transform(bbox["min_lon"], bbox["min_lat"])
    max_x, max_y = transformer.transform(bbox["max_lon"], bbox["max_lat"])

    pad_x = (max_x - min_x) * 0.20
    pad_y = (max_y - min_y) * 0.20

    fig, ax = plt.subplots(figsize=(10, 8))

    rect = Rectangle(
        (min_x, min_y),
        max_x - min_x,
        max_y - min_y,
        linewidth=2,
        edgecolor="#e74c3c",
        facecolor="#e74c3c",
        alpha=0.15,
    )
    ax.add_patch(rect)

    ax.set_xlim(min_x - pad_x, max_x + pad_x)
    ax.set_ylim(min_y - pad_y, max_y + pad_y)

    ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, zoom="auto")

    bbox_patch = mpatches.Patch(
        edgecolor="#e74c3c", facecolor="#e74c3c", alpha=0.4, label="Analysis Bbox"
    )
    ax.legend(handles=[bbox_patch], loc="lower right", fontsize=9)

    ax.set_title(
        f"Proposed Analysis Bounding Box\n"
        f"N {bbox['max_lat']:.4f}   S {bbox['min_lat']:.4f}   "
        f"W {bbox['min_lon']:.4f}   E {bbox['max_lon']:.4f}",
        fontsize=11,
        fontweight="bold",
    )
    ax.set_axis_off()
    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "bbox_preview.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return path


def _print_bbox(bbox: dict):
    print(f"    North : {bbox['max_lat']:.6f}")
    print(f"    South : {bbox['min_lat']:.6f}")
    print(f"    East  : {bbox['max_lon']:.6f}")
    print(f"    West  : {bbox['min_lon']:.6f}")


def _prompt_manual_bbox(current_bbox: dict, output_dir: str) -> dict:
    """Interactively collect manual coordinates, regenerating the preview on each attempt."""
    while True:
        print("\n  Enter new bounding box coordinates (decimal degrees):")
        try:
            min_lat = float(input("    South (min_lat): ").strip())
            max_lat = float(input("    North (max_lat): ").strip())
            min_lon = float(input("    West  (min_lon): ").strip())
            max_lon = float(input("    East  (max_lon): ").strip())
        except ValueError:
            print("  Invalid input — please enter decimal numbers.")
            continue

        if min_lat >= max_lat:
            print("  South must be less than North.")
            continue
        if min_lon >= max_lon:
            print("  West must be less than East.")
            continue

        new_bbox = {
            **current_bbox,
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lon": min_lon,
            "max_lon": max_lon,
        }
        map_path = _generate_bbox_map(new_bbox, output_dir)
        print(f"\n  Updated preview map saved: {map_path}")
        print("\n  New coordinates:")
        _print_bbox(new_bbox)
        _divider()
        print("  [y] Confirm new bbox")
        print("  [m] Re-enter coordinates")
        print("  [n] Abort")
        _divider()
        while True:
            c = input("  Your choice: ").strip().lower()
            if c == "y":
                print("  Manual bbox confirmed.")
                return new_bbox
            if c == "n":
                raise RuntimeError("Pipeline aborted by user at bbox verification step.")
            if c == "m":
                break  # re-enter coords outer loop
            print("  Please enter y, m, or n.")


def _divider():
    print("  " + "─" * 56)


def confirm_bbox(bbox: dict, output_dir: str) -> dict:
    """
    Generate a bbox preview map, display the coordinates, and prompt the user to:
      [y] confirm  [m] enter manual coordinates  [n] abort

    Returns the (possibly modified) bbox dict.
    Raises RuntimeError if the user aborts.
    """
    map_path = _generate_bbox_map(bbox, output_dir)

    print()
    _divider()
    print("  USER REVIEW: Bounding Box Verification")
    _divider()
    _print_bbox(bbox)
    print(f"\n  Preview map saved: {map_path}")
    _divider()
    print("  [y] Confirm and continue")
    print("  [m] Enter manual coordinates")
    print("  [n] Abort")
    _divider()

    while True:
        choice = input("  Your choice: ").strip().lower()
        if choice == "y":
            print("  Bbox confirmed.\n")
            return bbox
        if choice == "n":
            raise RuntimeError("Pipeline aborted by user at bbox verification step.")
        if choice == "m":
            return _prompt_manual_bbox(bbox, output_dir)
        print("  Please enter y, m, or n.")


# ── 2. Post-ingest confirmation ────────────────────────────────────────────────

def confirm_ingest(location_count: int, bbox: dict) -> None:
    """
    Display the number of locations found and prompt the user to proceed before
    kicking off the (potentially expensive) risk analysis stage.

    Raises RuntimeError if the user aborts.
    """
    print()
    _divider()
    print("  USER REVIEW: Pre-Analysis Confirmation")
    _divider()
    print(f"  Found {location_count:,} locations within the bounding box.")
    print("  Next: TCC sampling + building / terrain scoring")
    _divider()
    print("  [y] Proceed with risk analysis")
    print("  [n] Abort")
    _divider()

    while True:
        choice = input("  Your choice: ").strip().lower()
        if choice == "y":
            print("  Proceeding with risk analysis.\n")
            return
        if choice == "n":
            raise RuntimeError("Pipeline aborted by user before risk analysis.")
        print("  Please enter y or n.")


# ── 3. Score threshold review ──────────────────────────────────────────────────

def _show_distribution(risk_gdf: gpd.GeoDataFrame, low_t: float, high_t: float):
    total = len(risk_gdf)
    counts = risk_gdf["risk_tier"].value_counts().to_dict()
    print(f"\n  Thresholds: LOW < {low_t}  |  MEDIUM {low_t}–{high_t}  |  HIGH ≥ {high_t}")
    print(f"  Distribution ({total:,} locations):")
    for tier in ["HIGH", "MEDIUM", "LOW"]:
        n = counts.get(tier, 0)
        pct = n / total * 100 if total else 0.0
        bar = "█" * max(1, int(pct / 2)) if n else ""
        print(f"    {tier:6s}: {n:4d}  ({pct:5.1f}%)  {bar}")
    print(f"  Avg risk score: {risk_gdf['risk_score'].mean():.3f}")


def _preview_distribution(risk_gdf: gpd.GeoDataFrame, low_t: float, high_t: float):
    """Show what the distribution would look like under new thresholds."""
    total = len(risk_gdf)

    def _tier(score):
        if score >= high_t:
            return "HIGH"
        if score >= low_t:
            return "MEDIUM"
        return "LOW"

    new_tiers = risk_gdf["risk_score"].apply(_tier)
    counts = new_tiers.value_counts().to_dict()
    print(f"\n  Preview with LOW < {low_t}  |  MEDIUM {low_t}–{high_t}  |  HIGH ≥ {high_t}:")
    for tier in ["HIGH", "MEDIUM", "LOW"]:
        n = counts.get(tier, 0)
        pct = n / total * 100 if total else 0.0
        bar = "█" * max(1, int(pct / 2)) if n else ""
        print(f"    {tier:6s}: {n:4d}  ({pct:5.1f}%)  {bar}")


def review_thresholds(
    risk_gdf: gpd.GeoDataFrame,
    low_threshold: float,
    high_threshold: float,
) -> tuple[float, float]:
    """
    Show the risk score distribution and optionally let the user adjust the
    LOW / HIGH tier thresholds before the report is generated.

    Returns (low_threshold, high_threshold) — possibly updated by the user.
    Raises RuntimeError if the user aborts.
    """
    print()
    _divider()
    print("  USER REVIEW: Risk Score Thresholds")
    _divider()
    _show_distribution(risk_gdf, low_threshold, high_threshold)
    _divider()
    print("  [y] Accept thresholds and generate report")
    print("  [a] Adjust thresholds")
    print("  [n] Abort")
    _divider()

    while True:
        choice = input("  Your choice: ").strip().lower()

        if choice == "y":
            print("  Thresholds accepted.\n")
            return low_threshold, high_threshold

        if choice == "n":
            raise RuntimeError("Pipeline aborted by user at threshold review step.")

        if choice == "a":
            while True:
                print(
                    f"\n  Current: LOW < {low_threshold:.2f}  "
                    f"|  HIGH ≥ {high_threshold:.2f}  (scores are 0–1)"
                )
                try:
                    new_low = float(input("  New LOW threshold  (< this = LOW): ").strip())
                    new_high = float(input("  New HIGH threshold (≥ this = HIGH): ").strip())
                except ValueError:
                    print("  Invalid input — enter decimal numbers between 0 and 1.")
                    continue

                if not (0.0 < new_low < new_high < 1.0):
                    print("  Invalid: must satisfy  0 < low < high < 1.")
                    continue

                _preview_distribution(risk_gdf, new_low, new_high)
                confirm = input("\n  Apply these thresholds? [y/n]: ").strip().lower()
                if confirm == "y":
                    print("  New thresholds applied.\n")
                    return new_low, new_high
                # else re-enter

        else:
            print("  Please enter y, a, or n.")


# ── 4. Apply revised thresholds ────────────────────────────────────────────────

def apply_thresholds(
    risk_gdf: gpd.GeoDataFrame,
    low_threshold: float,
    high_threshold: float,
) -> gpd.GeoDataFrame:
    """Re-label risk_tier using updated thresholds."""

    def _tier(score):
        if score >= high_threshold:
            return "HIGH"
        if score >= low_threshold:
            return "MEDIUM"
        return "LOW"

    result = risk_gdf.copy()
    result["risk_tier"] = result["risk_score"].apply(_tier)
    return result
