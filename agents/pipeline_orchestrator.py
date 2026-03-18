"""
Pipeline Orchestrator Agent — LLM-driven pipeline controller.

Uses Claude (tool use) to manage the four pipeline stages, making recovery
decisions when stages fail rather than crashing immediately.

Tools available to the agent
  - run_bbox(query)              → resolves natural language query to a bounding box
  - expand_bbox(buffer_km)       → widens the current bbox and retries ingestion
  - run_ingest()                 → loads/filters locations CSV and validates data sources
  - run_risk_analysis()          → scores each location for obstruction risk
  - run_report()                 → generates stakeholder report and map
  - abort(reason)                → stops the pipeline with a clear error message

The agent calls these tools in order, inspecting each result and deciding
whether to retry with adjusted parameters or abort with a useful message.
"""

import json

import anthropic
import geopandas as gpd

SYSTEM_PROMPT = """\
You are a pipeline controller managing a satellite coverage obstruction risk analysis.

Your job is to run four stages in order — bbox, ingest, risk_analysis, report — \
by calling the provided tools. After each tool call, inspect the result and decide \
whether to proceed, retry with adjusted parameters, or abort.

Recovery rules:
- If run_bbox fails or returns an implausibly small area: retry once with a larger buffer.
- If run_ingest returns 0 locations: call expand_bbox (start with 25 km, up to 100 km) \
  and retry ingest. If still 0 after two expansions, call abort.
- If run_ingest warns about partial data coverage: proceed but note the warning.
- If run_risk_analysis fails: call abort — there is no safe fallback for scoring.
- If run_report fails: proceed anyway and note the report could not be generated; \
  the risk scores CSV was already saved.

Always call abort instead of stopping silently so the caller gets a clear error message.
"""


class PipelineOrchestratorAgent:
    def __init__(
        self,
        csv_path: str,
        tcc_path: str,
        output_dir: str,
        opentopo_key: str = None,
        buildings_path: str = None,
    ):
        self.csv_path = csv_path
        self.tcc_path = tcc_path
        self.output_dir = output_dir
        self.opentopo_key = opentopo_key
        self.buildings_path = buildings_path
        self.client = anthropic.Anthropic()

        # Shared pipeline state written by tools, read by later tools
        self._bbox: dict | None = None
        self._gdf: gpd.GeoDataFrame | None = None
        self._data_paths: dict | None = None
        self._risk_gdf: gpd.GeoDataFrame | None = None

    # ── Public entry point ─────────────────────────────────────────────────────

    def run(self, query: str) -> gpd.GeoDataFrame:
        """
        Run the full pipeline under agent control.

        Returns the risk-scored GeoDataFrame on success.
        Raises RuntimeError if the agent calls abort().
        """
        messages = [
            {
                "role": "user",
                "content": (
                    f"Run the satellite obstruction risk pipeline for this query:\n\n"
                    f'  "{query}"\n\n'
                    f"CSV path: {self.csv_path}\n"
                    f"TCC path: {self.tcc_path}\n"
                    f"Output directory: {self.output_dir}\n\n"
                    "Call the pipeline tools in order. Handle any errors per the recovery rules."
                ),
            }
        ]

        # Agentic loop
        total_input_tokens = 0
        total_output_tokens = 0
        while True:
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=self._tool_schemas(),
                messages=messages,
            )
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                print(f"[Orchestrator] → {block.name}({json.dumps(block.input)})")
                result = self._dispatch(block.name, block.input, query)
                print(f"[Orchestrator] ← {json.dumps(result)[:200]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

        print(
            f"[Orchestrator] Usage — input: {total_input_tokens:,} tokens, "
            f"output: {total_output_tokens:,} tokens"
        )

        if self._risk_gdf is None:
            raise RuntimeError("Pipeline did not complete — risk scores were not produced.")

        return self._risk_gdf

    # ── Tool dispatch ──────────────────────────────────────────────────────────

    def _dispatch(self, name: str, inputs: dict, query: str) -> dict:
        try:
            if name == "run_bbox":
                return self._tool_run_bbox(inputs["query"])
            if name == "expand_bbox":
                return self._tool_expand_bbox(inputs["buffer_km"])
            if name == "run_ingest":
                return self._tool_run_ingest()
            if name == "run_risk_analysis":
                return self._tool_run_risk_analysis()
            if name == "run_report":
                return self._tool_run_report(query)
            if name == "abort":
                raise RuntimeError(f"Pipeline aborted by orchestrator: {inputs['reason']}")
            return {"error": f"Unknown tool: {name}"}
        except RuntimeError:
            raise
        except Exception as exc:
            return {"error": str(exc)}

    # ── Tool implementations ───────────────────────────────────────────────────

    def _tool_run_bbox(self, query: str) -> dict:
        from agents.bbox_agent import get_bounding_box

        self._bbox = get_bounding_box(query)
        return {
            "status": "ok",
            "bbox": {k: v for k, v in self._bbox.items() if k != "reasoning"},
            "place_name": self._bbox.get("place_name"),
        }

    def _tool_expand_bbox(self, buffer_km: float) -> dict:
        if self._bbox is None:
            return {"error": "No bbox to expand — run_bbox has not succeeded yet."}

        import math

        b = self._bbox
        mid_lat = (b["min_lat"] + b["max_lat"]) / 2
        buf_lat = buffer_km / 111.0
        buf_lon = buffer_km / (111.0 * math.cos(math.radians(mid_lat)))

        self._bbox = {
            **b,
            "min_lat": b["min_lat"] - buf_lat,
            "max_lat": b["max_lat"] + buf_lat,
            "min_lon": b["min_lon"] - buf_lon,
            "max_lon": b["max_lon"] + buf_lon,
        }
        return {"status": "ok", "expanded_bbox": self._bbox, "buffer_km": buffer_km}

    def _tool_run_ingest(self) -> dict:
        if self._bbox is None:
            return {"error": "No bbox available — call run_bbox first."}

        from agents.ingester import IngestAgent

        ingester = IngestAgent(
            csv_path=self.csv_path,
            tcc_path=self.tcc_path,
            buildings_path=self.buildings_path,
        )
        self._gdf, self._data_paths = ingester.run(self._bbox)

        return {
            "status": "ok",
            "location_count": len(self._gdf),
            "bbox_used": self._bbox,
        }

    def _tool_run_risk_analysis(self) -> dict:
        if self._gdf is None or self._data_paths is None:
            return {"error": "No ingested data — call run_ingest first."}

        import os
        from agents.risk_analyzer import RiskAnalyzer

        analyzer = RiskAnalyzer(elevation_api_key=self.opentopo_key)
        self._risk_gdf = analyzer.analyze(self._gdf, self._data_paths)

        os.makedirs(self.output_dir, exist_ok=True)
        csv_out = os.path.join(self.output_dir, "risk_scores.csv")
        self._risk_gdf.drop(columns="geometry").to_csv(csv_out, index=False)

        tier_counts = self._risk_gdf["risk_tier"].value_counts().to_dict()
        return {
            "status": "ok",
            "location_count": len(self._risk_gdf),
            "risk_distribution": tier_counts,
            "csv_saved": csv_out,
        }

    def _tool_run_report(self, query: str) -> dict:
        if self._risk_gdf is None:
            return {"error": "No risk scores — call run_risk_analysis first."}

        from agents.reporter import ReporterAgent

        reporter = ReporterAgent()
        reporter.generate_report(self._risk_gdf, query, self.output_dir)

        return {"status": "ok", "output_dir": self.output_dir}

    # ── Tool schemas ───────────────────────────────────────────────────────────

    def _tool_schemas(self) -> list:
        return [
            {
                "name": "run_bbox",
                "description": (
                    "Resolve a natural language location query to a geographic bounding box. "
                    "Call this first."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The location query string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "expand_bbox",
                "description": (
                    "Expand the current bounding box by a buffer in kilometers on all sides. "
                    "Use this when run_ingest returns 0 locations."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "buffer_km": {
                            "type": "number",
                            "description": "Kilometers to add to each edge (e.g. 25, 50, 100)",
                        },
                    },
                    "required": ["buffer_km"],
                },
            },
            {
                "name": "run_ingest",
                "description": (
                    "Load, filter, and validate locations within the current bounding box. "
                    "Requires run_bbox to have succeeded."
                ),
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "run_risk_analysis",
                "description": (
                    "Score each location for satellite obstruction risk. "
                    "Requires run_ingest to have succeeded."
                ),
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "run_report",
                "description": (
                    "Generate the stakeholder report and risk map. "
                    "Requires run_risk_analysis to have succeeded."
                ),
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "abort",
                "description": (
                    "Stop the pipeline and surface a clear error message to the user. "
                    "Use this when a stage fails and no recovery is possible."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Human-readable explanation of why the pipeline cannot continue",
                        },
                    },
                    "required": ["reason"],
                },
            },
        ]
