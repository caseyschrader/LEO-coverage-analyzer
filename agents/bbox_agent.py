"""
BBox Agent — converts a natural language location query to a geographic bounding box.

Uses Claude (tool use + adaptive thinking) with two tools:
  - geocode_place: calls Nominatim OSM to resolve a place name to coordinates
  - create_bounding_box: finalizes the bounding box (with optional buffer)

Returns a dict: {min_lat, max_lat, min_lon, max_lon, place_name, reasoning}
"""

import json
import math

import anthropic
import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# ── Tool implementations ───────────────────────────────────────────────────────

def _geocode_place(query: str) -> dict:
    """Call Nominatim to geocode a place name."""
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": "LEO-Risk-Pipeline/1.0"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()

    if not results:
        return {"error": f"No geocoding results found for '{query}'"}

    r = results[0]
    result = {
        "place_name": r["display_name"],
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "type": r.get("type", "unknown"),
    }

    # Nominatim returns [south, north, west, east] as strings
    if "boundingbox" in r:
        bb = r["boundingbox"]
        result["bbox_from_nominatim"] = {
            "south": float(bb[0]),
            "north": float(bb[1]),
            "west": float(bb[2]),
            "east": float(bb[3]),
        }

    return result


def _create_bounding_box(
    south: float,
    north: float,
    west: float,
    east: float,
    buffer_km: float = 0,
) -> dict:
    """Create (and optionally expand) a bounding box."""
    if buffer_km > 0:
        mid_lat = (south + north) / 2
        buf_lat = buffer_km / 111.0
        buf_lon = buffer_km / (111.0 * math.cos(math.radians(mid_lat)))
        south -= buf_lat
        north += buf_lat
        west -= buf_lon
        east += buf_lon

    return {
        "min_lat": round(south, 6),
        "max_lat": round(north, 6),
        "min_lon": round(west, 6),
        "max_lon": round(east, 6),
    }


# ── Tool schemas for Claude ────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "geocode_place",
        "description": (
            "Geocode a place name to get its coordinates and bounding box. "
            "Use this to find the location of a city, valley, mountain range, "
            "county, or other geographic area. Returns lat/lon and a bounding box "
            "when available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The place name to geocode. Be specific — include state or "
                        "country for disambiguation. E.g. 'Sacramento Valley, California'"
                    ),
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_bounding_box",
        "description": (
            "Finalize a geographic bounding box from known coordinates. "
            "Call this as the last step to commit the bounding box. "
            "Use the Nominatim bounding box when available; otherwise use "
            "your geographic knowledge. Add a buffer_km when the region's "
            "Nominatim box seems too tight."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "south": {"type": "number", "description": "Southern boundary (min latitude)"},
                "north": {"type": "number", "description": "Northern boundary (max latitude)"},
                "west": {"type": "number", "description": "Western boundary (min longitude)"},
                "east": {"type": "number", "description": "Eastern boundary (max longitude)"},
                "buffer_km": {
                    "type": "number",
                    "description": "Optional buffer in km to expand each edge (default 0)",
                },
            },
            "required": ["south", "north", "west", "east"],
        },
    },
]


# ── Agent entry point ──────────────────────────────────────────────────────────

def get_bounding_box(query: str) -> dict:
    """
    Convert a natural language location query to a geographic bounding box.

    Args:
        query: E.g. "Sacramento Valley, California" or
               "Where in the Appalachian Mountains is there high obstruction risk?"

    Returns:
        dict with keys: min_lat, max_lat, min_lon, max_lon, place_name, reasoning
    """
    client = anthropic.Anthropic()

    messages = [
        {
            "role": "user",
            "content": (
                f"I need a geographic bounding box for this location query:\n\n"
                f"  \"{query}\"\n\n"
                "Steps:\n"
                "1. Call geocode_place to look up the location.\n"
                "2. Review the result. If a bbox_from_nominatim is returned, use those "
                "coordinates (possibly adding a small buffer for large regions). If not, "
                "use your geographic knowledge to define appropriate bounds.\n"
                "3. Call create_bounding_box with the final coordinates to commit the result.\n\n"
                "The box should capture the full spatial extent of the named region."
            ),
        }
    ]

    bbox_result = None
    reasoning = ""

    # Agentic loop — runs until Claude stops calling tools
    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            thinking={"type": "adaptive"},
            tools=TOOLS,
            messages=messages,
        )

        # Collect any text / thinking for reasoning
        for block in response.content:
            if hasattr(block, "text") and block.text:
                reasoning = block.text

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason != "tool_use":
            break

        # Execute tool calls and collect results
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "geocode_place":
                result = _geocode_place(block.input["query"])
            elif block.name == "create_bounding_box":
                result = _create_bounding_box(
                    south=block.input["south"],
                    north=block.input["north"],
                    west=block.input["west"],
                    east=block.input["east"],
                    buffer_km=block.input.get("buffer_km", 0),
                )
                bbox_result = result
            else:
                result = {"error": f"Unknown tool: {block.name}"}

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })

        messages.append({"role": "user", "content": tool_results})

    if bbox_result is None:
        raise ValueError(
            f"BBox agent failed to produce a bounding box for query: '{query}'"
        )

    bbox_result["place_name"] = query
    bbox_result["reasoning"] = reasoning
    return bbox_result
