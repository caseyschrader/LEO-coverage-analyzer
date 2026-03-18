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
ANTHROPIC_API_KEY=sk-ant-...
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
