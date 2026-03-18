"""
Reporter Agent — generates a stakeholder report and static risk map.

Uses:
  - Claude API (streaming, adaptive thinking) to write the narrative
  - matplotlib to produce a color-coded map of risk tiers
"""

import json
import os
from datetime import datetime

import anthropic
import contextily as ctx
import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

RISK_COLORS = {
    "LOW": "#2ecc71",    # green
    "MEDIUM": "#f39c12", # amber
    "HIGH": "#e74c3c",   # red
}

REPORT_PROMPT = """\
You are a geospatial analyst writing a professional report for a non-technical state broadband officer. \
The report assesses satellite internet coverage obstruction risk for LEO (Low Earth Orbit) providers \
(e.g., Starlink) at locations the providers are committed to serve.

Query analyzed: "{query}"

Risk analysis summary:
{summary_json}

Write a markdown stakeholder report with these sections:

## Executive Summary
2–3 sentences covering the overall risk picture.

## Methodology
Brief description: what data sources were used (NLCD Tree Canopy Cover, optionally terrain elevation), \
how risk was scored, what LOW / MEDIUM / HIGH mean for satellite dish installation.

## Risk Distribution
Interpret the HIGH / MEDIUM / LOW breakdown with percentages. Call out any notable patterns.

## Key Findings
What does the data reveal about obstruction risk in this specific region? \
Reference geographic context (tree cover density, terrain character, etc.).

## Notable High-Risk Locations
Reference specific locations from top_high_risk with their coordinates and scores.

## Recommendations
Practical guidance for LEO providers: site surveys, alternative mounting heights, \
seasonal canopy variation considerations, etc.

---
Keep the tone professional and concise. Avoid unnecessary hedging. \
The audience is for broadband providers not the general public.
Include the map image at the end: ![Risk Map](risk_map.png)
"""


class ReporterAgent:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def generate_map_only(
        self,
        risk_gdf: gpd.GeoDataFrame,
        query: str,
        output_dir: str,
    ) -> str:
        """Generate just the risk map without calling the Claude API."""
        os.makedirs(output_dir, exist_ok=True)
        map_path = self._generate_map(risk_gdf, query, output_dir)
        print(f"\n[Reporter] Map → {map_path}")
        return map_path

    def generate_report(
        self,
        risk_gdf: gpd.GeoDataFrame,
        query: str,
        output_dir: str,
    ) -> tuple:
        """
        Generate a stakeholder report and risk map.

        Returns:
            (report_text: str, map_path: str)
        """
        os.makedirs(output_dir, exist_ok=True)

        summary = self._compute_summary(risk_gdf)
        map_path = self._generate_map(risk_gdf, query, output_dir)
        report_text = self._write_report(summary, query)

        report_path = os.path.join(output_dir, "report.md")
        header = (
            f"---\n"
            f"generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"query: \"{query}\"\n"
            f"total_locations: {summary['total_locations']}\n"
            f"---\n\n"
        )
        with open(report_path, "w") as f:
            f.write(header + report_text)

        print(f"\n[Reporter] Report → {report_path}")
        print(f"[Reporter] Map    → {map_path}")

        return report_text, map_path

    # ── Private helpers ────────────────────────────────────────────────────────

    def _compute_summary(self, gdf: gpd.GeoDataFrame) -> dict:
        total = len(gdf)
        counts = gdf["risk_tier"].value_counts().to_dict()

        def pct(tier):
            return round(counts.get(tier, 0) / total * 100, 1)

        high_locs = (
            gdf[gdf["risk_tier"] == "HIGH"]
            .nlargest(5, "risk_score")
        )

        return {
            "total_locations": total,
            "high_risk":   counts.get("HIGH", 0),
            "medium_risk": counts.get("MEDIUM", 0),
            "low_risk":    counts.get("LOW", 0),
            "high_risk_pct":   pct("HIGH"),
            "medium_risk_pct": pct("MEDIUM"),
            "low_risk_pct":    pct("LOW"),
            "avg_tcc_pct": round(float(gdf["tcc_pct"].mean()), 1),
            "max_tcc_pct": round(float(gdf["tcc_pct"].max()), 1),
            "bbox": {
                "min_lat": round(float(gdf["latitude"].min()), 4),
                "max_lat": round(float(gdf["latitude"].max()), 4),
                "min_lon": round(float(gdf["longitude"].min()), 4),
                "max_lon": round(float(gdf["longitude"].max()), 4),
            },
            "top_high_risk": [
                {
                    "location_id": str(row.location_id),
                    "lat": round(float(row.latitude), 5),
                    "lon": round(float(row.longitude), 5),
                    "risk_score": round(float(row.risk_score), 3),
                    "tcc_pct": (
                        round(float(row.tcc_pct), 1)
                        if not np.isnan(row.tcc_pct)
                        else None
                    ),
                }
                for row in high_locs.itertuples()
            ],
        }

    def _generate_map(
        self, gdf: gpd.GeoDataFrame, query: str, output_dir: str
    ) -> str:
        # Reproject to Web Mercator so tile basemap aligns correctly
        gdf_web = gdf.to_crs(epsg=3857)

        fig, ax = plt.subplots(figsize=(12, 8))

        for tier in ["LOW", "MEDIUM", "HIGH"]:
            subset = gdf_web[gdf_web["risk_tier"] == tier]
            if len(subset):
                subset.plot(
                    ax=ax,
                    color=RISK_COLORS[tier],
                    markersize=6,
                    alpha=0.85,
                )

        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, zoom="auto")

        legend_patches = [
            mpatches.Patch(color=color, label=f"{tier} ({len(gdf[gdf['risk_tier']==tier])})")
            for tier, color in RISK_COLORS.items()
        ]
        ax.legend(handles=legend_patches, loc="lower right", title="Risk Tier", fontsize=9)

        ax.set_title(
            f"Satellite Coverage Obstruction Risk\n{query}",
            fontsize=11,
            fontweight="bold",
        )
        ax.set_axis_off()
        plt.tight_layout()
        map_path = os.path.join(output_dir, "risk_map.png")
        plt.savefig(map_path, dpi=150, bbox_inches="tight")
        plt.close()

        return map_path

    def _write_report(self, summary: dict, query: str) -> str:
        prompt = REPORT_PROMPT.format(
            query=query,
            summary_json=json.dumps(summary, indent=2),
        )

        report_text = ""
        print("\n[Reporter] Generating report...\n")

        with self.client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=2048,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                report_text += text
                print(text, end="", flush=True)
            final = stream.get_final_message()

        print()  # trailing newline after stream
        print(
            f"[Reporter] Usage — input: {final.usage.input_tokens:,} tokens, "
            f"output: {final.usage.output_tokens:,} tokens"
        )
        return report_text
