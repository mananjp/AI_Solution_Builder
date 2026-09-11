"""Tests for the LangGraph agent pipeline and individual nodes (mock LLM)."""

from app.agents.graph import (
    clarification_router,
    discovery_graph,
    generation_graph,
)
from app.agents.nodes.business_analyst import business_analyst_node
from app.agents.nodes.business_recommendation import business_recommendation_node


def test_clarification_router_branches():
    assert clarification_router({"confidence_score": 0.3}) == "ask_clarification"
    assert (
        clarification_router({"confidence_score": 0.9, "identified_solutions": []})
        == "recommend_modules"
    )
    assert (
        clarification_router({"confidence_score": 0.9, "identified_solutions": ["CRM"]})
        == "generate_blueprints"
    )


async def test_discovery_graph_full_pipeline():
    result = await discovery_graph.ainvoke(
        {
            "user_message": "We run a B2B SaaS company selling CRM software and need "
            "a full customer relationship management system with lead pipeline tracking",
            "conversation_history": [],
        }
    )
    assert result["status"] == "complete"
    assert result["current_agent"] == "blueprint_generator"
    assert result["workable_ready"] is True
    assert result["roadmap"]["artifact_type"] == "roadmap"
    assert result["agent_messages"][-1]["agent"] == "blueprint_generator"


async def test_generation_graph_after_confirmation():
    result = await generation_graph.ainvoke(
        {
            "user_message": "Build us a CRM system",
            "business_description": "B2B SaaS CRM company",
            "industry": "crm",
            "stakeholders": ["Sales", "Support"],
            "pain_points": ["Lead leakage"],
            "confirmed_modules": ["CRM Module", "Reporting"],
        }
    )
    assert result["status"] == "complete"
    assert result["workable_ready"] is True
    assert result["current_agent"] == "blueprint_generator"
    assert result["generated_schema"] is not None


async def test_discovery_with_low_confidence_forces_clarification(monkeypatch):
    import json

    from langchain_core.messages import AIMessage

    class _LowConfidenceLLM:
        async def ainvoke(self, messages):
            return AIMessage(
                content=json.dumps(
                    {
                        "business_description": "We want software",
                        "industry": "general",
                        "business_size": "sme",
                        "business_stage": "idea",
                        "stakeholders": [],
                        "pain_points": [],
                        "identified_solutions": [],
                        "confidence_score": 0.4,
                        "clarification_questions": ["What systems do you need?"],
                        "analysis_summary": "Needs clarification",
                    }
                )
            )

    monkeypatch.setattr(
        "app.agents.nodes.business_analyst.get_llm", lambda **kw: _LowConfidenceLLM()
    )
    result = await discovery_graph.ainvoke({"user_message": "hi", "conversation_history": []})
    assert result["clarification_questions"]
    assert not result.get("workable_ready")
    assert result["status"] == "analyzing"


async def test_business_analyst_node_with_uploaded_context():
    state = {
        "user_message": "Describe the inventory management requirements",
        "uploaded_context": "We track 500 SKUs across 3 warehouses.",
        "conversation_history": [
            {"role": "user", "content": "Previous question about stock levels"}
        ],
    }
    out = await business_analyst_node(state)
    assert out["current_agent"] == "business_analyst"
    assert out["status"] == "analyzing"
    assert out["agent_messages"][-1]["agent"] == "business_analyst"
    assert isinstance(out["confidence_score"], float)


async def test_business_analyst_unparseable_response_is_resilient(monkeypatch):
    from langchain_core.messages import AIMessage

    class _BrokenLLM:
        async def ainvoke(self, messages):
            return AIMessage(content="not json at all")

    monkeypatch.setattr("app.agents.nodes.business_analyst.get_llm", lambda **kw: _BrokenLLM())
    out = await business_analyst_node({"user_message": "hello"})
    assert out["confidence_score"] == 0.5
    assert out["clarification_questions"]


async def test_business_recommendation_node():
    out = await business_recommendation_node(
        {
            "business_description": "Retail chain with 12 stores",
            "industry": "retail",
            "business_size": "sme",
            "business_stage": "growth",
            "pain_points": ["Manual stock counts"],
        }
    )
    assert out["recommended_modules"]
    assert out["current_agent"] == "business_recommendation"
    assert out["status"] == "recommending"
