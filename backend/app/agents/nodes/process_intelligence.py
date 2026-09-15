"""
AI Solution Builder — Process Intelligence Agent Node

Designs the BPMN 2.0 process layer (Section 4 of the implementation plan):
interactive React Flow graphs, swimlanes, and bottleneck prediction.
Outputs a `bpmn_flows` artifact consumed by the @xyflow/react renderer.
"""

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import PROCESS_INTELLIGENCE_SYSTEM
from app.agents.state import DiscoveryState
from app.agents.utils import parse_llm_json
from app.core.llm import get_llm, invoke_with_retry

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 15  # seconds — stay under Groq 6k TPM

_EMPTY_BPMN: dict[str, Any] = {"name": "Core Process", "xml": "", "flows": []}


def _fallback(message: str) -> dict[str, Any]:
    """Return empty BPMN so downstream nodes can still run."""
    logger.warning("Process Intelligence using fallback: %s", message)
    return {
        "bpmn_flows": [
            {
                "artifact_type": "bpmn_flows",
                "title": "Process Workflows",
                "content": {
                    "bpmn": _EMPTY_BPMN,
                    "react_flow": {"nodes": [], "edges": []},
                    "swimlanes": [],
                    "bottlenecks": [],
                },
                "content_text": json.dumps(_EMPTY_BPMN, indent=2),
            }
        ],
        "current_agent": "process_intelligence",
        "status": "generating",
        "agent_messages": [],
    }


async def process_intelligence_node(state: DiscoveryState) -> dict[str, Any]:
    """Generate BPMN workflows with bottleneck detection for confirmed modules."""
    await asyncio.sleep(RATE_LIMIT_DELAY)
    logger.info("Process Intelligence Agent: generating BPMN workflows")

    try:
        llm = get_llm(temperature=0.2, max_tokens=2048, state=state)
    except Exception as exc:
        logger.error("Process Intelligence: failed to get LLM — %s", exc)
        return _fallback(f"LLM init failed: {exc}")

    modules = state.get("confirmed_modules") or state.get("identified_solutions", [])
    hld_artifact = state.get("hld")
    hld: dict[str, Any] = hld_artifact.get("content", {}) if hld_artifact else {}
    stakeholders = state.get("stakeholders", [])

    messages = [
        SystemMessage(content=PROCESS_INTELLIGENCE_SYSTEM),
        HumanMessage(
            content=f"""Business: {state.get("business_description", "")}
Industry: {state.get("industry", "general")}
Modules: {json.dumps(modules)}
Architecture Components: {json.dumps(hld.get("components", []), default=str)[:1500]}
Stakeholders: {json.dumps(stakeholders)[:500]}"""
        ),
    ]

    try:
        response = await invoke_with_retry(llm, messages)
    except Exception as exc:
        logger.error("Process Intelligence: LLM call failed — %s", exc)
        return _fallback(f"LLM call failed: {exc}")

    try:
        result = parse_llm_json(response.content)
    except (json.JSONDecodeError, IndexError):
        logger.error("Process Intelligence: failed to parse JSON response")
        result = {
            "bpmn": _EMPTY_BPMN,
            "react_flow": {"nodes": [], "edges": []},
            "swimlanes": [],
            "bottlenecks": [],
        }

    bpmn_data = result.get("bpmn", {})
    react_flow = result.get("react_flow", {"nodes": [], "edges": []})
    bottlenecks = result.get("bottlenecks", [])

    artifact = {
        "artifact_type": "bpmn_flows",
        "title": f"Process Workflows — {bpmn_data.get('name', 'Core Business Process')}",
        "content": {
            "bpmn": bpmn_data,
            "react_flow": react_flow,
            "swimlanes": result.get("swimlanes", []),
            "bottlenecks": bottlenecks,
        },
        "content_text": json.dumps(result, indent=2),
    }

    bottleneck_count = len(bottlenecks)
    logger.info("Process Intelligence: %d bottlenecks flagged", bottleneck_count)

    return {
        "bpmn_flows": [artifact],
        "current_agent": "process_intelligence",
        "status": "generating",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "process_intelligence",
                "type": "process_complete",
                "data": {
                    "flow_count": len(result.get("bpmn", {}).get("flows", [])),
                    "react_nodes": len(react_flow.get("nodes", [])),
                    "bottleneck_count": bottleneck_count,
                },
            }
        ],
    }
