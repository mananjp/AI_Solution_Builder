import pytest

from app.agents.nodes.database_api_agent import database_api_agent_node


@pytest.mark.asyncio
async def test_database_api_agent_generates_non_empty_default_payload_when_llm_fails(monkeypatch):
    async def fake_invoke_with_retry(*args, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        "app.agents.nodes.database_api_agent.get_llm",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        "app.agents.nodes.database_api_agent.invoke_with_retry",
        fake_invoke_with_retry,
    )

    state = {
        "business_description": "Design a freight logistics and dispatch platform with route optimization, live GPS tracking, POD collection, and warehouse management.",
        "industry": "logistics",
        "confirmed_modules": ["route_optimization", "fleet_management", "proof_of_delivery", "warehouse_management"],
    }

    result = await database_api_agent_node(state)

    assert result["database_schema"]["content"]["ddl"]
    assert result["database_schema"]["content_text"]
    assert result["api_spec"]["content"]["endpoints"]
    assert result["er_diagram"]["content"]["entities"]
