# LEO Satellite Coverage Risk Pipeline — Project Write-Up

---

## 1. Data Ingestion and Analysis Workflow

### Architecture Overview

The pipeline is composed of four functional agents orchestrated by a fifth controlling agent. Each agent has a defined scope, a set of tools it can call, and a clear handoff contract with the next stage.

### Agent Boundaries and Tool Access

**BBoxAgent** — Translates a natural language location query into a geographic bounding box. This is the only stage where LLM reasoning is genuinely necessary: interpreting vague or complex location descriptions ("Monroe Rd Indian Trail, NC" or "Western NC Mountains") into precise coordinates requires geographic knowledge and the ability to decide when a Nominatim result is too tight and needs a buffer. The agent runs a tool-use loop with two tools: `geocode_place` (calls Nominatim OSM) and `create_bounding_box` (commits the final coordinates with optional expansion).

**IngestAgent** — Loads the locations CSV, validates required columns, drops rows with null or out-of-range coordinates, filters to the bounding box, and confirms that the TCC raster covers the analysis area. No LLM involvement — this is pure data engineering with deterministic outputs.

**RiskAnalyzer** — Scores each location against three obstruction factors (described in Section 2). Pure computation — no LLM. Results are saved to `risk_scores.csv` before any report is generated, so a report failure does not lose scoring output.

**ReporterAgent** — Calls Claude (streaming) to write a narrative stakeholder report from a structured JSON summary, and generates a color-coded map using matplotlib and contextily. The LLM is appropriate here because the report requires synthesizing statistics into readable prose for a non-technical audience.

**PipelineOrchestratorAgent** — Manages the sequence and handles errors. Rather than hardcoding recovery logic (e.g., `if count == 0: expand_bbox(25)`), the orchestrator uses Claude's tool-use loop to make judgment calls. This is appropriate because some recovery decisions are fuzzy: how far to expand a bounding box, when to give up versus retry, and how to communicate failure clearly. For a non-technical user, having the orchestrator handle these decisions invisibly is preferable to surfacing raw exceptions. The tradeoff is added API cost and latency for what is essentially a control-flow layer — acknowledged as a design choice that could be simplified in a production hardening pass.

### Tool Definitions

#### BBoxAgent Tools

```json
{
  "name": "geocode_place",
  "description": "Geocode a place name via Nominatim OSM. Returns lat/lon and bounding box when available.",
  "input_schema": {
    "query": { "type": "string", "description": "Place name, including state/country for disambiguation" }
  },
  "returns": {
    "place_name": "string",
    "lat": "float",
    "lon": "float",
    "bbox_from_nominatim": { "south": "float", "north": "float", "west": "float", "east": "float" }
  }
}
```

```json
{
  "name": "create_bounding_box",
  "description": "Commit the final bounding box. Applies an optional km buffer to each edge.",
  "input_schema": {
    "south": "float", "north": "float", "west": "float", "east": "float",
    "buffer_km": { "type": "float", "optional": true, "default": 0 }
  },
  "returns": { "min_lat": "float", "max_lat": "float", "min_lon": "float", "max_lon": "float" }
}
```

#### PipelineOrchestratorAgent Tools

| Tool | Purpose | Key Inputs |
|---|---|---|
| `run_bbox(query)` | Invoke BBoxAgent | Location query string |
| `expand_bbox(buffer_km)` | Widen current bbox | km to add per edge (25 → 50 → 100) |
| `run_ingest()` | Invoke IngestAgent | Uses current bbox state |
| `run_risk_analysis()` | Invoke RiskAnalyzer | Uses ingested GeoDataFrame |
| `run_report()` | Invoke ReporterAgent | Uses risk-scored GeoDataFrame |
| `abort(reason)` | Terminate with message | Human-readable failure explanation |

### State Management

State passes between agents via the orchestrator's instance variables rather than message passing. Each tool writes to a shared slot (`_bbox`, `_gdf`, `_data_paths`, `_risk_gdf`) that the next tool reads.

### Failure Handling

| Stage | Failure condition | Recovery |
|---|---|---|
| BBoxAgent | Implausibly small area | Retry with larger buffer |
| IngestAgent | 0 locations found | `expand_bbox` 25 km → 50 km → 100 km, then abort |
| IngestAgent | Partial TCC coverage | Warn and proceed |
| RiskAnalyzer | Any exception | Abort immediately (no safe fallback) |
| ReporterAgent | Any exception | Log error, preserve `risk_scores.csv`, continue |
| Terrain scoring | DEM fetch fails | Skip terrain factor, redistribute weights |
| Buildings scoring | No file provided | Skip building factor, redistribute weights |

User intervention is possible at three checkpoints: bbox confirmation (with manual override), pre-analysis location count confirmation, and post-scoring threshold review. Any checkpoint can abort the pipeline cleanly.

---

## 2. Analysis Rationale

### From the Install Guide to Methodology

The Starlink residential install guide states: *"Your Starlink needs a clear view of the sky so it can stay connected with satellites as they move overhead. Objects that obstruct the connection between your Starlink and the satellite, such as a tree branch, pole, or roof, will cause service interruptions."*

The guide frames obstruction as essentially binary — any obstruction causes interruption. For a remote analysis across thousands of locations, a binary model is too blunt: it would classify any location with a single tree as unserviceable. The challenge instead called for a risk scoring approach that could differentiate between a location with light suburban canopy and one sitting beneath a dense hardwood canopy.

Three physical obstruction categories follow directly from the guide's language:

- **Vegetation** — tree branches are explicitly named. Tree canopy cover is the most consistently available public data proxy for this.
- **Structures** — poles and roofs are named. Building footprints with height estimates are the closest available proxy for nearby structural obstruction.
- **Terrain** — not explicitly named in the guide, but a practical concern in mountainous areas. A location in a valley or on the shaded side of a ridge faces the same signal blockage problem as one under a tree. This factor was included based on domain knowledge from living in Utah's mountainous terrain.

One important limitation identified during design: Starlink terminals in the northern hemisphere need a clear view toward the southern sky, where satellites spend most of their time. The analysis currently calculates horizon angles in all directions equally, which overstates risk from northern obstructions. A directional weighting model (de-emphasizing north-facing obstructions) would be more physically accurate and would also reduce computation overhead. This remains an open improvement.

### Why This Approach Over Alternatives

The main alternative would be a purely geometry-based viewshed analysis using LiDAR point clouds and computing the actual sky visibility cone from each location. That would be more accurate but requires sourcing and processing state-specific LiDAR data, which is not consistently available nationally. NLCD tree canopy cover trades spatial precision for complete CONUS coverage, making the pipeline generalizable to any region without per-state data sourcing.

### Defining "At-Risk" for a Non-Technical Audience

A location is **at-risk** anywhere there is likely to be something blocking the dish's view of the sky. This could be tall trees in the yard, a home deep in a valley, or a building surrounded by taller buildings. The more sky that is blocked, the more likely the dish will lose its connection as satellites pass overhead.

In practice, the pipeline assigns each location a risk score between 0 and 1 based on how much canopy, terrain, and building obstruction is present. Locations are then grouped into three tiers:

- **LOW** — minimal obstruction expected. Standard installation should work reliably.
- **MEDIUM** — moderate obstruction present. Service may degrade, elevated mounting or selective trimming may help.
- **HIGH** — dense obstruction. High probability of persistent signal loss. A professional site visit is strongly recommended before installation.

### Score Thresholds — Honest Account

The LOW/MEDIUM/HIGH thresholds (0.30 and 0.60) were set as approximately equal-distribution cutoffs across the 0–1 score range. They were not derived from a physical model of how much obstruction Starlink can actually tolerate. The install guide does not provide that information in depth. Expert input from a Starlink field installation team would be needed to assign these thresholds more accurately.

### Risk Factor Weights — Honest Account

| Factor | Weight (full model) | Rationale |
|---|---|---|
| Tree Canopy Cover | 0.40 | Primary obstruction source identified by the install guide; nationally consistent data |
| Building Obstruction | 0.40 | Equal weight to TCC for initial testing; building obstructions are likely more severe than equivalent canopy |
| Terrain | 0.20 | Lower weight for the NC-focused dataset; the Piedmont and coastal plain are not significantly mountainous |

The building and TCC weights were set equally as a starting point. In practice, a tall building that fully shadows a dish is a harder obstruction than a comparable tree canopy (which has some seasonal variation and partial transparency). Adjusting building weight upward relative to TCC is a reasonable next step.

When terrain data is unavailable (no OpenTopography API key), the remaining weight is split proportionally between TCC and buildings. When buildings are unavailable, TCC carries 70% and terrain 30%.

### Known Limitations vs. On-Site Assessment

The most significant gap between this remote analysis and an actual site visit is **individual tree detection**. The NLCD tree canopy cover raster has a 30-meter resolution. Such a resoluation can be used effectively for characterizing neighborhood-level canopy density, but insufficient to detect a single large tree in a front yard that could block a dish. A location in a lightly wooded neighborhood might score LOW risk while having a single tree directly obstructing the optimal dish placement angle. An on-site assessor would catch this immediately; the remote model would not.

Additional gaps:

- **Building height quality** — Microsoft Building Footprints heights are ML-estimated from imagery. Actual heights may differ, particularly for irregular structures.
- **Directionality** — the model does not account for which  direction an obstruction faces relative to the satellite ground track.
- **Dish placement flexibility** — on-site assessors can choose where on a property to mount the dish. The model scores a fixed point (the location centroid or rooftop coordinate).
---

## 3. Data Sourcing and Quality

### Datasets and Obstruction Factor Mapping

| Dataset | Source | Obstruction Factor | Notes |
|---|---|---|---|
| NLCD Tree Canopy Cover 2023 | [MRLC Viewer](https://www.mrlc.gov/viewer/) | Vegetation | CONUS-wide, 30m resolution, WGS84 |
| MS Global Building Footprints | [Microsoft Planetary Computer](https://github.com/microsoft/GlobalMLBuildingFootprints) | Structural obstruction | ML-derived footprints + height estimates |
| OpenTopography SRTMGL1 DEM | [OpenTopography](https://opentopography.org) | Terrain obstruction | 30m resolution, API key required, optional |
| Nominatim / OSM | OpenStreetMap | Bounding box geocoding | Used by BBoxAgent only |

**Why NLCD TCC over alternatives:** NLCD 2023 was the most polished and easily downloadable source available. Higher-resolution alternatives exist.I found a global 1m global canopy height map but I struggled to find the source data.Some states publish high resolution LiDAR data that could be processed to show canopy cover.

**Why Microsoft Building Footprints:** The dataset provides both polygon footprints and ML-estimated heights at national scale. No comparable free alternative with height estimates exists for the US. The height estimates are model-derived and not field-validated; `height == -1` in the dataset signals an unknown height, handled by defaulting to 0 (no contribution to obstruction score).

### Data Quality Issues in the Locations CSV

- **Missing coordinates:** Rows with null latitude or longitude were dropped during ingestion.
- **Out-of-range coordinates:** Rows outside valid WGS84 bounds (lat ±90, lon ±180) were dropped.
- **TCC resolution mismatch:** At 30m resolution, the TCC raster assigns a single canopy value to an area roughly the size of a house lot. A location at a parcel centroid may sample canopy from a neighboring property rather than the actual installation site.
- **Location point precision:** The CSV provides a single lat/lon per location (rooftop or parcel centroid). The model has no information about where on a property a dish would actually be mounted.

### What Cannot Be Modeled with Public Data

- **Individual tree detection at parcel scale** - public canopy data is too coarse
- **Dish mounting height** - unknown for each location
- **Local ordinances** - tree removal restrictions vary by municipality and affect options
---

## 4. Findings

### Core Findings (Charlotte, NC Run)

> **Note on the Charlotte run:** The reporter agent (Claude) generated a methodology table in the output report with threshold values (LOW < 0.4, MEDIUM 0.4–0.7, HIGH > 0.7) that do not match the actual code thresholds (LOW < 0.30, MEDIUM 0.30–0.59, HIGH ≥ 0.60). I believe this is a hallucination by the reporting agent. The report was generated from a structured JSON summary, but the agent independently created the threshold table values rather than reading them from the input. The actual scoring used the code-defined thresholds. This is a known limitation of using an LLM for report generation and highlights the need for templated or programmatically-injected values for any quantitative claims in the report.

From the Charlotte, NC analysis (382,609 locations):

| Risk Tier | Locations | Share |
|---|---|---|
| LOW | 306,699 | 80.2% |
| MEDIUM | 75,475 | 19.7% |
| HIGH | 435 | 0.1% |

- Average tree canopy cover across all locations: **31.5%**
- Maximum observed canopy cover: **98%**
- The medium-risk population (75,475 locations) is the most operationally significant — these locations are serviceable but may require elevated mounting or seasonal performance management
- The 435 high-risk locations all exceed 80% canopy cover and should be treated as requiring individual site surveys before installation commitments are made