# LEO Coverage Risk Pipeline

An agentic pipeline that scores locations for satellite dish obstruction risk from LEO providers (e.g. Starlink). Given a natural language region query and a CSV of locations, it produces a risk-scored dataset, a stakeholder report, and a map.

## Architecture

```
orchestrator.py
    └── PipelineOrchestratorAgent  (Claude tool-use loop — manages stages + recovery)
            ├── BBox Agent         (Claude + Nominatim → bounding box)
            ├── IngestAgent        (CSV load → spatial filter → validation)
            ├── RiskAnalyzer       (TCC + terrain + buildings → risk score)
            └── ReporterAgent      (Claude streaming → report.md + risk_map.png)
```

**Risk factors and weights:**

| Factor | Source | Weight |
|---|---|---|
| Tree Canopy Cover (TCC) | NLCD raster | 0.4 |
| Terrain obstruction | OpenTopography DEM (optional) | 0.2 |
| Building obstruction | MS Building Footprints GeoJSON (optional) | 0.4 |

Risk tiers: `LOW` (< 0.30) · `MEDIUM` (0.30–0.59) · `HIGH` (≥ 0.60)

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=s\
OPENTOPO_API_KEY=...          # optional — enables terrain scoring
```

`ANTHROPIC_API_KEY` is required. `OPENTOPO_API_KEY` is optional; without it, terrain scoring is skipped and weights are redistributed between TCC and buildings.

Free OpenTopography API keys are available at [opentopography.org](https://opentopography.org).

### 4. Obtain data files

Place the following in the `data/` directory:

| File | Description | How to get |
|---|---|---|
| `DATA_CHALLENGE_50.csv` | Locations to score (`location_id`, `latitude`, `longitude`) | Provided separately |
| `nlcd_tcc_conus_wgs84_v2023-5_20230101_20231231.tif` | NLCD 2023 Tree Canopy Cover raster (CONUS, WGS84) | [MRLC Viewer](https://www.mrlc.gov/viewer/) |
| `nc_buildings.geojson` | Building footprints with heights | See `utils/download_nc_buildings.py` |

To download North Carolina building footprints:

```bash
python utils/download_nc_buildings.py
```

Data files are resolved relative to the project root by default, so no path configuration is needed as long as files are placed in `data/`.

## Usage

### Full pipeline

```bash
python orchestrator.py "Charolette, North Carolina"
python orchestrator.py "Analyze the Risk along Monroe Rd Indian Trail, NC" --output results/Monroe
python orchestrator.py "Ashenville, NC" --opentopo-key YOUR_KEY
```

### With custom data paths

```bash
python orchestrator.py "Western NC Mountains" \
    --csv data/my_locations.csv \
    --tcc data/tcc.tif \
    --buildings data/buildings.geojson \
    --output results/western-nc
```

### Regenerate map only (no API calls)

If `risk_scores.csv` already exists and you just want to update the map:

```bash
python orchestrator.py "Asheville, NC" --map-only
```

### CLI reference

```
positional arguments:
  query                 Natural language location query

options:
  --csv PATH            Path to locations CSV (default: data/DATA_CHALLENGE_50.csv)
  --tcc PATH            Path to TCC GeoTIFF
  --buildings PATH      Path to buildings GeoJSON
  --output DIR          Output directory (default: project root)
  --opentopo-key KEY    OpenTopography API key (overrides .env)
  --map-only            Regenerate map from existing risk_scores.csv
```

## Outputs

All outputs are written to the `--output` directory (default: project root):

| File | Description |
|---|---|
| `risk_scores.csv` | Risk scores for each location (`tcc_pct`, `tcc_score`, `building_angle`, `building_score`, `terrain_angle`, `terrain_score`, `risk_score`, `risk_tier`) |
| `report.md` | Stakeholder report with executive summary, methodology, findings, and recommendations |
| `risk_map.png` | Color-coded map of risk tiers with OSM basemap |

## Pipeline recovery behavior

The `PipelineOrchestratorAgent` uses Claude to manage recovery between stages:

- If the bounding box resolves to an implausibly small area, it retries with a larger buffer.
- If ingestion finds 0 locations, it expands the bounding box (25 km → 50 km → 100 km) before giving up.
- If risk analysis fails, the pipeline aborts immediately (no safe fallback for scoring).
- If report generation fails, the CSV is preserved and the error is surfaced without crashing.

## Project structure

```
orchestrator.py              Entry point and CLI
agents/
    pipeline_orchestrator.py LLM-driven pipeline controller
    bbox_agent.py            Natural language → bounding box (Claude + Nominatim)
    ingester.py              CSV load, validation, spatial filter
    risk_analyzer.py         TCC / terrain / building obstruction scoring
    reporter.py              Report generation (Claude streaming) + map
utils/
    raster.py                Raster sampling helpers
    elevation.py             OpenTopography DEM fetch + horizon angle
    download_nc_buildings.py Script to download NC building footprints
data/                        Input data (gitignored)
```

## Decision Log

### 1. NLCD Tree Canopy Cover as primary obstruction signal

**Decision:** Use NLCD 2023 Tree Canopy Cover (30m resolution) as the primary and always-available risk factor.

**Alternatives:** Sentinel-2 NDVI, LiDAR-derived canopy height models, Meta/WRI 1m Global Canopy Height Map.

**Reasoning:** NLCD TCC is a purpose-built canopy product covering all of CONUS at consistent resolution, already normalized to 0–100%, and freely available. NDVI captures vegetation broadly but doesn't distinguish canopy height. LiDAR would be more accurate but has no national coverage. The 1m global canopy height map was identified as a higher-resolution alternative but the source data pipeline was not fully resolved within the project timeline.

**What I'd revisit:** TCC lags reality, a location cleared of trees in 2024 may still show high canopy coverage in the 2023. The level of resolution is also not ideal for analyzing indvidual homes' TCC.

---

### 2. LLM-driven orchestration for pipeline control flow

**Decision:** Use Claude tool-use loop in PipelineOrchestratorAgent to manage stage sequencing and error recovery rather than hardcoded if/else logic.

**Alternatives:** Simple sequential script with try/except blocks, Airflow workflow orchestration.

**Reasoning:** Some recovery decisions are fuzzy for example: how far to expand a bounding box, when to give up vs retry, how to communicate failure clearly to a non-technical user. An agnet handles these judgment calls without requiring every failure mode to be anticipated and hardcoded. For a non-technical user, invisible recovery is preferable to dealing with exceptions.

**What I'd revisit:** The orchestrator adds API cost and latency. In production this could be simplified to deterministic logic once failure modes are well understood.

---

### 3. Microsoft Global Building Footprints for structural obstruction

**Decision:** Use Microsoft Global Building Footprints (ML-estimated heights) as the structural obstruction factor.

**Alternatives:** OpenStreetMap building data (no heights), local government parcel data (inconsistent availability), skip structural obstruction entirely.

**Reasoning:** No comparable free alternative with height estimates exists at national scale for the US. OSM building data lacks height information needed to compute obstruction angles. The MS dataset provides both polygon footprints and ML-estimated heights derived from imagery.

**What I'd revisit:** Height coverage is inconsisent as records have `height == -1` (unknown). The current implementation defaults unknown heights to 0, meaning those buildings contribute nothing to the obstruction score. A better approach might be to estimate height from footprint area or building type where height is missing.

---

### 4. Risk score weights and thresholds

**Decision:** TCC weight 0.40, building weight 0.40, terrain weight 0.20. Thresholds: LOW < 0.30, MEDIUM 0.30–0.59, HIGH ≥ 0.60.

**Alternatives:** Equal weighting across all three factors, data-driven weight derivation from ground truth, single-factor TCC-only model.

**Reasoning:** TCC and buildings were weighted equally as a starting point. Building obstructions are likely more severe than equivalent canopy (no partial transparency) but the dataset has inconsisent height coverage which limits confidence in the building score. Terrain was given lower weight for the NC-focused dataset given the state is not significantly mountainous. Thresholds were set as equal distribution across the 0–1 range, not derived from a physical model of Starlink's actual obstruction tolerance.

**What I'd revisit:** Both the weights and thresholds need field validation against known good and bad installation sites. Expert input from a Starlink field installation team would be needed to set these more accurately. The pipeline sets thresholds as a user-adjustable parameter at runtime for this reason.