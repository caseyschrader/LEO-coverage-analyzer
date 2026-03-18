# AI Tool Disclosure

This document fulfills the assignment's AI tool transparency requirement. All AI tools used in this project are listed below, along with their purpose and cases where I diverged from AI-generated output.

---

## Tools Used

### Claude

Claude Code (CLI) and Claude.ai (web chat)

| Session | Purpose |
|---|---|
| Claude Code | Initial pipeline architecture design and translating the problem statement into an agent-driven workflow (BBox → Ingest → Risk → Report) |
| Claude Code | Scaffolding the `PipelineOrchestratorAgent` and its tool-use loop pattern |
| Claude Code | Implementing the `BBoxAgent` using Claude's tool-use API with Nominatim geocoding |
| Claude Code | Writing the `RiskAnalyzer`: TCC sampling, terrain horizon-angle calculation, and building obstruction scoring |
| Claude Code | Building `download_nc_buildings.py`: quadkey resolution, tile downloading, and parsing of Microsoft Building Footprints |
| Claude Code | Implementing the `ReporterAgent` with streaming output and matplotlib map generation |
| Claude Code | Adding `contextily` basemap to the risk map |
| Claude.ai | Understanding Microsoft's quadkey tile system and how to match 11-digit index keys to 8-digit dataset parent keys |
| Claude.ai | Drafting the analysis rationale write-up (Q&A format — Claude asked questions, I answered, it drafted) |

---

## Where I Diverged from AI-Generated Output

### 1. Rejected per-location LLM risk narration

Early in the design conversation, Claude suggested having an agent generate a short explanation for each location's risk score (e.g., "This location is high-risk due to dense canopy cover and a ridge to the north-east"). I declined this as the computational and API cost would be too much. Each analysis ended up having thousands of locations and having an explaination for each one would be overkill.

### 2. Used fixed, arbitrary risk weights instead of derived ones

Claude proposed attempting to derive or calibrate the TCC/terrain/buildings weights (0.4/0.2/0.4) from the Starlink installation guide's physical requirements. I declined this as I believe these weights need an in-field expert's input. I'm sure Claude could optimize my arbitrary weights but they would still be arbitrary.

### 3. Dropped the North Carolina state boundary spatial mask on building footprints

Claude's initial `download_nc_buildings.py` design included clipping all downloaded building footprints to the NC state boundary polygon (from a Census TIGER shapefile) to eliminate buildings from neighboring states that appear in edge tiles. I removed this step. Loading a state boundary and running a geometry clip on ~millions of polygons was unnecessary  given that the pipeline already filters buildings to the analysis bbox and the pipeline doesn't need to be state specific.

### 5. Replaced Folium with contextily for the risk map

Claude's response to my basemap request defaulted to Folium (interactive HTML map). I just went with `contextily` with matplotlib for a static PNG. I know an interactive map was a suggestion as a bonus deliverable but I didn't have time to polish it.

## Notes on Process

The initial architecture prompt was written by me before any code existed. Claude did not design the pipeline from scratch. The agent pattern, the choice of four stages, and the decision to use tool-use loops were in my original prompt. Claude's main contributions were translating those intentions into working Python, navigating library-specific syntax (rasterio, geopandas spatial indexing, the Anthropic API), and helping me think through the Microsoft quadkey structure.

The analysis write-up was a collaborative Q&A: Claude asked me questions about my methodology and I answered them. Claude then drafted the document from my answers.