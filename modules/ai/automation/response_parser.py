import json
import re
from typing import Any, Dict, List

from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def parse_ai_json(payload: str) -> Any:
    if not payload:
        raise RuntimeError("Empty AI response")
    text = payload.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text, flags=re.IGNORECASE).strip()
        text = text.rstrip("`").strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    start = None
    for idx, ch in enumerate(text):
        if ch in "{[":
            start = idx
            break
    if start is None:
        raise RuntimeError("Failed to parse JSON from AI response")

    tail = text[start:]
    for end in range(len(tail), max(len(tail) - 2000, 0), -1):
        chunk = tail[:end]
        try:
            return json.loads(chunk)
        except Exception:
            continue

    raise RuntimeError("Failed to parse JSON from AI response")


def _normalize_string_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return [part.strip() for part in raw.split(",") if part.strip()]
    return [str(value).strip()] if str(value).strip() else []


def parse_story_arc_json(payload: str) -> Dict[str, Any]:
    data = parse_ai_json(payload)
    if not isinstance(data, dict):
        raise RuntimeError("Story arc response must be a JSON object")

    required_top_level = {"ArcTitle", "Premise", "Tone", "ScenarioCount", "Scenarios"}
    missing_top_level = sorted(key for key in required_top_level if key not in data)
    if missing_top_level:
        raise RuntimeError(f"Story arc is missing fields: {', '.join(missing_top_level)}")

    scenarios_raw = data.get("Scenarios", [])
    if not isinstance(scenarios_raw, list):
        raise RuntimeError("Story arc Scenarios must be a list")
    if not scenarios_raw:
        raise RuntimeError("Story arc contains no scenarios")

    scenarios: List[Dict[str, Any]] = []
    required_scenario_keys = {
        "Title",
        "Synopsis",
        "Goal",
        "KeyNPCs",
        "KeyLocations",
        "KeyItems",
        "Hooks",
        "Outcome",
        "LeadsTo",
    }
    for index, entry in enumerate(scenarios_raw, start=1):
        if not isinstance(entry, dict):
            raise RuntimeError(f"Scenario {index} is not a JSON object")
        missing_keys = sorted(key for key in required_scenario_keys if key not in entry)
        if missing_keys:
            raise RuntimeError(
                f"Scenario {index} is missing fields: {', '.join(missing_keys)}"
            )
        scenarios.append(
            {
                "Title": str(entry.get("Title", "")).strip(),
                "Synopsis": str(entry.get("Synopsis", "")).strip(),
                "Goal": str(entry.get("Goal", "")).strip(),
                "KeyNPCs": _normalize_string_list(entry.get("KeyNPCs")),
                "KeyLocations": _normalize_string_list(entry.get("KeyLocations")),
                "KeyItems": _normalize_string_list(entry.get("KeyItems")),
                "Hooks": _normalize_string_list(entry.get("Hooks")),
                "Outcome": str(entry.get("Outcome", "")).strip(),
                "LeadsTo": str(entry.get("LeadsTo", "")).strip(),
            }
        )

    try:
        scenario_count = int(data.get("ScenarioCount"))
    except (TypeError, ValueError):
        raise RuntimeError("Story arc ScenarioCount must be an integer")
    if scenario_count <= 0:
        raise RuntimeError("Story arc ScenarioCount must be greater than 0")

    arc = {
        "ArcTitle": str(data.get("ArcTitle", "")).strip(),
        "Premise": str(data.get("Premise", "")).strip(),
        "Tone": str(data.get("Tone", "")).strip(),
        "ScenarioCount": scenario_count,
        "Scenarios": scenarios,
    }

    if not arc["ArcTitle"]:
        raise RuntimeError("Story arc ArcTitle cannot be empty")
    if not arc["Premise"]:
        raise RuntimeError("Story arc Premise cannot be empty")
    if not arc["Tone"]:
        raise RuntimeError("Story arc Tone cannot be empty")

    if scenario_count != len(scenarios):
        scenario_count = len(scenarios)
    arc["ScenarioCount"] = scenario_count
    arc["Scenarios"] = scenarios[:scenario_count]
    return arc
