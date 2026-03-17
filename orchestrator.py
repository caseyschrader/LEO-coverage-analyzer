"""
LEO Coverage Risk Pipeline — Orchestrator

Chains four stages:
  1. BBox Agent      — natural language query → bounding box (Claude + Nominatim)
  2. Ingester        — load, validate, and spatially filter locations CSV
  3. Risk Analyzer   — score each location for satellite obstruction risk
  4. Reporter Agent  — generate stakeholder report + map (Claude streaming)

Usage
-----
  python orchestrator.py "Sacramento Valley, California"
  python orchestrator.py "rural Appalachian Virginia" --output results/va
  python orchestrator.py "Cascades, Washington" --opentopo-key YOUR_KEY

Environment
-----------
  ANTHROPIC_API_KEY   required for BBox Agent and Reporter Agent
  OPENTOPO_API_KEY    optional; enables terrain horizon-angle scoring
"""

import argparse
import os

from dotenv import load_dotenv
load_dotenv()

DEFAULT_CSV = "/home/kc/Documents/Ready_LEO_Project/DATA_CHALLENGE_50.csv"
DEFAULT_TCC = "/home/kc/Documents/Ready_LEO_Project/nlcd_tcc_conus_wgs84_v2023-5_20230101_20231231.tif"
DEFAULT_OUTPUT = "/home/kc/Documents/Ready_LEO_Project/"


def run_pipeline(
    query: str,
    csv_path: str = DEFAULT_CSV,
    tcc_path: str = DEFAULT_TCC,
    output_dir: str = DEFAULT_OUTPUT,
    opentopo_key: str = None,
):
    """
    Execute the full risk analysis pipeline for a natural language location query.

    Returns:
        GeoDataFrame with risk scores (also saved to output_dir/risk_scores.csv)
    """
    from agents.bbox_agent import get_bounding_box
    from agents.ingester import IngestAgent
    from agents.risk_analyzer import RiskAnalyzer
    from agents.reporter import ReporterAgent

    sep = "=" * 60
    print(f"\n{sep}")
    print("  LEO Coverage Risk Pipeline")
    print(f"  Query : {query}")
    print(f"{sep}\n")

    # ── Stage 1: Resolve bounding box ─────────────────────────────────────────
    print("[Stage 1/4] Resolving bounding box from query...")
    bbox = get_bounding_box(query)
    print(
        f"  → lat [{bbox['min_lat']:.4f}, {bbox['max_lat']:.4f}]  "
        f"lon [{bbox['min_lon']:.4f}, {bbox['max_lon']:.4f}]"
    )

    # ── Stage 2: Ingest & validate ────────────────────────────────────────────
    print("\n[Stage 2/4] Ingesting and validating data...")
    ingester = IngestAgent(csv_path=csv_path, tcc_path=tcc_path)
    gdf, data_paths = ingester.run(bbox)

    # ── Stage 3: Risk analysis ────────────────────────────────────────────────
    print("\n[Stage 3/4] Computing obstruction risk scores...")
    analyzer = RiskAnalyzer(elevation_api_key=opentopo_key)
    risk_gdf = analyzer.analyze(gdf, data_paths)

    os.makedirs(output_dir, exist_ok=True)
    csv_out = os.path.join(output_dir, "risk_scores.csv")
    risk_gdf.drop(columns="geometry").to_csv(csv_out, index=False)
    print(f"  → Risk scores saved: {csv_out}")

    # ── Stage 4: Report ───────────────────────────────────────────────────────
    print("\n[Stage 4/4] Generating stakeholder report and map...")
    reporter = ReporterAgent()
    reporter.generate_report(risk_gdf, query, output_dir)

    print(f"\n{sep}")
    print(f"  Pipeline complete. Outputs in: {output_dir}/")
    print(f"  Files: risk_scores.csv, report.md, risk_map.png")
    print(f"{sep}\n")

    return risk_gdf


def main():
    parser = argparse.ArgumentParser(
        description="LEO satellite coverage obstruction risk pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python orchestrator.py "Sacramento Valley, California"
  python orchestrator.py "rural Appalachian Virginia" --output results/va
  python orchestrator.py "Cascades, Washington" --opentopo-key YOUR_KEY
        """,
    )
    parser.add_argument("query", help="Natural language location query")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to locations CSV")
    parser.add_argument("--tcc", default=DEFAULT_TCC, help="Path to TCC GeoTIFF")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output directory")
    parser.add_argument(
        "--opentopo-key",
        default=os.environ.get("OPENTOPO_API_KEY"),
        help="OpenTopography API key (enables terrain scoring)",
    )

    args = parser.parse_args()

    run_pipeline(
        query=args.query,
        csv_path=args.csv,
        tcc_path=args.tcc,
        output_dir=args.output,
        opentopo_key=args.opentopo_key,
    )


if __name__ == "__main__":
    main()
