"""
AI Solution Builder — Process Intelligence Agent Node

Designs the BPMN 2.0 process layer (Section 4 of the implementation plan):
interactive React Flow graphs, swimlanes, and bottleneck prediction.
Outputs a `bpmn_flows` artifact consumed by the @xyflow/react renderer.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import PROCESS_INTELLIGENCE_SYSTEM
from app.agents.state import DiscoveryState
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


async def process_intelligence_node(state: DiscoveryState) -> dict[str, Any]:
    """Generate BPMN workflows with bottleneck detection for confirmed modules."""
    logger.info("Process Intelligence Agent: generating BPMN workflows")

    llm = get_llm(temperature=0.2, max_tokens=8192, state=state)

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
Architecture Components: {json.dumps(hld.get("components", []), default=str)}
Stakeholders: {json.dumps(stakeholders)}"""
        ),
    ]

    response = await llm.ainvoke(messages)

    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        result = json.loads(content.strip())
    except (json.JSONDecodeError, IndexError):
        logger.error("Failed to parse process intelligence response")
        result = {
            "bpmn": {"name": "Core Process", "xml": "", "flows": []},
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
