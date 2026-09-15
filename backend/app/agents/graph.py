"""
AI Solution Builder — LangGraph Pipeline

Wires all agent nodes into a cyclic state machine with conditional routing:

  business_analysis → clarification_router →
    ├─ ask_clarification → END (wait for user)
    ├─ recommend_modules → business_recommendation → END (wait for confirmation)
    └─ generate → solutions_architect → ux_agent → process_intelligence
                  → database_api_agent → code_synthesizer → blueprint_generator → END
"""

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from app.agents.nodes.blueprint_generator import blueprint_generator_node
from app.agents.nodes.business_analyst import business_analyst_node
from app.agents.nodes.business_recommendation import business_recommendation_node
from app.agents.nodes.code_synthesizer import code_synthesizer_node
from app.agents.nodes.database_api_agent import database_api_agent_node
from app.agents.nodes.process_intelligence import process_intelligence_node
from app.agents.nodes.solutions_architect import solutions_architect_node
from app.agents.nodes.ux_agent import ux_agent_node
from app.agents.state import DiscoveryState

logger = logging.getLogger(__name__)


def clarification_router(
    state: DiscoveryState,
) -> Literal["ask_clarification", "recommend_modules", "generate_blueprints"]:
    """Route based on confidence score and whether solutions are identified."""
    confidence = state.get("confidence_score", 0.0)
    solutions = state.get("identified_solutions", [])

    if confidence < 0.7:
        logger.info(f"Routing to clarification (confidence={confidence})")
        return "ask_clarification"
    if not solutions:
        logger.info("Routing to recommendation (no solutions identified)")
        return "recommend_modules"

    logger.info(f"Routing to generation ({len(solutions)} solutions identified)")
    return "generate_blueprints"


def _add_generation_pipeline(graph: StateGraph) -> None:  # type: ignore[type-arg]
    """Wire the shared generation tail ending at blueprint_generator → END."""
    graph.add_node("solutions_architect", solutions_architect_node)
    graph.add_node("ux_agent", ux_agent_node)
    graph.add_node("process_intelligence", process_intelligence_node)
    graph.add_node("database_api_agent", database_api_agent_node)
    graph.add_node("code_synthesizer", code_synthesizer_node)
    graph.add_node("blueprint_generator", blueprint_generator_node)

    graph.add_edge("solutions_architect", "ux_agent")
    graph.add_edge("ux_agent", "process_intelligence")
    graph.add_edge("process_intelligence", "database_api_agent")
    graph.add_edge("database_api_agent", "code_synthesizer")
    graph.add_edge("code_synthesizer", "blueprint_generator")
    graph.add_edge("blueprint_generator", END)


def build_discovery_graph() -> StateGraph:  # type: ignore[type-arg]
    """Build the full multi-agent discovery pipeline."""
    graph = StateGraph(DiscoveryState)

    # ── Add Nodes ────────────────────────────────
    graph.add_node("business_analysis", business_analyst_node)
    graph.add_node("business_recommendation", business_recommendation_node)

    # Entry + analysis routing
    graph.set_entry_point("business_analysis")
    graph.add_conditional_edges(
        "business_analysis",
        clarification_router,
        {
            "ask_clarification": END,  # Wait for user input
            "recommend_modules": "business_recommendation",  # Propose modules
            "generate_blueprints": "solutions_architect",  # Proceed to generation
        },
    )

    # Recommendation waits for user confirmation
    graph.add_edge("business_recommendation", END)

    # Generation pipeline (sequential)
    _add_generation_pipeline(graph)

    return graph


def build_generation_graph() -> StateGraph:  # type: ignore[type-arg]
    """Build just the generation pipeline (for use after recommendation
    confirmation). Skips discovery and recommendation."""
    graph = StateGraph(DiscoveryState)
    graph.set_entry_point("solutions_architect")
    _add_generation_pipeline(graph)
    return graph


# Compile graphs (reusable across requests)
discovery_graph = build_discovery_graph().compile()
generation_graph = build_generation_graph().compile()
