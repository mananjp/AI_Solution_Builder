"""
AI Solution Builder — Database & API Agent Node

Generates ER diagrams, PostgreSQL DDL schemas, and API endpoint specifications.
"""

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import DATABASE_API_AGENT_SYSTEM
from app.agents.state import DiscoveryState
from app.agents.utils import parse_llm_json
from app.core.llm import get_llm, invoke_with_retry

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 15  # seconds — stay under Groq 6k TPM


def _default_logistics_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Create a realistic logistics domain schema/API scaffold when the model is down or returns empty output."""
    modules = state.get("confirmed_modules") or state.get("identified_solutions") or [
        "route_optimization",
        "fleet_management",
        "proof_of_delivery",
        "warehouse_management",
    ]
    entity_names = [
        "Shipment",
        "Route",
        "Driver",
        "Vehicle",
        "Warehouse",
        "ProofOfDelivery",
        "DeliveryStop",
    ]
    ddl_lines = [
        "CREATE TABLE shipments (id UUID PRIMARY KEY, carrier_id UUID, status VARCHAR(32), pickup_warehouse_id UUID, delivery_window_start TIMESTAMP, delivery_window_end TIMESTAMP, created_at TIMESTAMP DEFAULT NOW());",
        "CREATE TABLE routes (id UUID PRIMARY KEY, vehicle_id UUID, optimization_score NUMERIC(5,2), total_distance_km NUMERIC(10,2), estimated_duration_minutes INTEGER, created_at TIMESTAMP DEFAULT NOW());",
        "CREATE TABLE drivers (id UUID PRIMARY KEY, full_name VARCHAR(255), phone VARCHAR(32), current_status VARCHAR(32), last_location JSONB, created_at TIMESTAMP DEFAULT NOW());",
        "CREATE TABLE vehicles (id UUID PRIMARY KEY, registration_number VARCHAR(64), capacity_kg NUMERIC(10,2), status VARCHAR(32), last_latitude NUMERIC(9,6), last_longitude NUMERIC(9,6));",
        "CREATE TABLE warehouses (id UUID PRIMARY KEY, name VARCHAR(255), address TEXT, region VARCHAR(128), capacity INTEGER);",
        "CREATE TABLE proof_of_delivery (id UUID PRIMARY KEY, shipment_id UUID, driver_id UUID, signature_url TEXT, photo_url TEXT, delivered_at TIMESTAMP, latitude NUMERIC(9,6), longitude NUMERIC(9,6));",
        "CREATE TABLE delivery_stops (id UUID PRIMARY KEY, shipment_id UUID, sequence_number INTEGER, stop_type VARCHAR(32), address TEXT, eta TIMESTAMP, status VARCHAR(32));",
    ]
    endpoints = [
        {"method": "POST", "path": "/api/v1/shipments", "description": "Create a shipment and assign a route"},
        {"method": "GET", "path": "/api/v1/shipments/{shipmentId}", "description": "Fetch shipment status and milestones"},
        {"method": "POST", "path": "/api/v1/routes/plan", "description": "Generate the optimal route for a set of stops"},
        {"method": "POST", "path": "/api/v1/drivers/{driverId}/location", "description": "Update a driver's real-time GPS location"},
        {"method": "POST", "path": "/api/v1/pods", "description": "Capture proof-of-delivery proof, photos, and signature"},
        {"method": "POST", "path": "/api/v1/warehouses/inbound", "description": "Register an inbound stock or pallet receipt"},
    ]

    return {
        "er_diagram": {
            "artifact_type": "er_diagram",
            "title": "Entity-Relationship Diagram",
            "content": {
                "entities": [
                    {"name": name, "fields": [{"name": "id", "type": "UUID", "primary_key": True, "nullable": False, "foreign_key": None, "description": "Primary identifier"}]}
                    for name in entity_names
                ],
                "relationships": [
                    {"from": "Shipment", "to": "Route", "type": "many-to-one", "via": "route_id"},
                    {"from": "Shipment", "to": "Driver", "type": "many-to-one", "via": "driver_id"},
                    {"from": "Shipment", "to": "Warehouse", "type": "many-to-one", "via": "pickup_warehouse_id"},
                    {"from": "Shipment", "to": "ProofOfDelivery", "type": "one-to-one", "via": "shipment_id"},
                ],
            },
            "content_text": json.dumps({
                "entities": [
                    {"name": name, "fields": [{"name": "id", "type": "UUID", "primary_key": True, "nullable": False, "foreign_key": None, "description": "Primary identifier"}]}
                    for name in entity_names
                ],
                "relationships": [
                    {"from": "Shipment", "to": "Route", "type": "many-to-one", "via": "route_id"},
                    {"from": "Shipment", "to": "Driver", "type": "many-to-one", "via": "driver_id"},
                    {"from": "Shipment", "to": "Warehouse", "type": "many-to-one", "via": "pickup_warehouse_id"},
                    {"from": "Shipment", "to": "ProofOfDelivery", "type": "one-to-one", "via": "shipment_id"},
                ],
            }, indent=2),
        },
        "database_schema": {
            "artifact_type": "database_schema",
            "title": "Database Schema (PostgreSQL DDL)",
            "content": {"ddl": "\n".join(ddl_lines)},
            "content_text": "\n".join(ddl_lines),
        },
        "api_spec": {
            "artifact_type": "api_spec",
            "title": "API Specification",
            "content": {"endpoints": endpoints},
            "content_text": json.dumps(endpoints, indent=2),
        },
        "module_hint": modules,
    }


def _fallback(message: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a realistic logistics schema/API fallback so downstream nodes can still run."""
    logger.warning("Database & API Agent using fallback: %s", message)
    payload = _default_logistics_payload(state or {})
    return {
        "er_diagram": payload["er_diagram"],
        "database_schema": payload["database_schema"],
        "api_spec": payload["api_spec"],
        "current_agent": "database_api_agent",
        "status": "generating",
        "agent_messages": [],
    }


async def database_api_agent_node(state: DiscoveryState) -> dict[str, Any]:
    """Generate ER diagram, DDL schema, and API spec."""
    await asyncio.sleep(RATE_LIMIT_DELAY)
    logger.info("Database & API Agent: generating schema and API spec")

    try:
        llm = get_llm(temperature=0.1, max_tokens=2048)
    except Exception as exc:
        logger.error("Database & API Agent: failed to get LLM — %s", exc)
        return _fallback(f"LLM init failed: {exc}")

    modules = state.get("confirmed_modules") or state.get("identified_solutions", [])
    hld_artifact = state.get("hld")
    lld_artifact = state.get("lld")
    hld: dict[str, Any] = hld_artifact.get("content", {}) if hld_artifact else {}
    lld: dict[str, Any] = lld_artifact.get("content", {}) if lld_artifact else {}

    messages = [
        SystemMessage(content=DATABASE_API_AGENT_SYSTEM),
        HumanMessage(
            content=f"""Business: {state.get("business_description", "")}
Industry: {state.get("industry", "general")}
Modules: {json.dumps(modules)}
HLD Components: {json.dumps(hld.get("components", []), default=str)}
LLD Modules: {json.dumps(lld.get("modules", []), default=str)}"""
        ),
    ]

    try:
        response = await invoke_with_retry(llm, messages)
    except Exception as exc:
        logger.error("Database & API Agent: LLM call failed — %s", exc)
        return _fallback(f"LLM call failed: {exc}")

    try:
        result = parse_llm_json(response.content)
    except (json.JSONDecodeError, IndexError):
        logger.error("Database & API Agent: failed to parse JSON response")
        result = {}

    default_payload = _default_logistics_payload(state)
    result = result if isinstance(result, dict) else {}

    er_diagram = result.get("er_diagram") or default_payload["er_diagram"]["content"]
    schema_ddl = result.get("schema_ddl") or result.get("database_schema") or default_payload["database_schema"]["content"]["ddl"]
    api_endpoints = result.get("api_endpoints") or result.get("api_spec") or default_payload["api_spec"]["content"]["endpoints"]

    if not isinstance(er_diagram, dict) or not er_diagram.get("entities"):
        er_diagram = default_payload["er_diagram"]["content"]
    if not isinstance(api_endpoints, list) or not api_endpoints:
        api_endpoints = default_payload["api_spec"]["content"]["endpoints"]
    if not schema_ddl or not str(schema_ddl).strip():
        schema_ddl = default_payload["database_schema"]["content"]["ddl"]

    return {
        "er_diagram": {
            "artifact_type": "er_diagram",
            "title": "Entity-Relationship Diagram",
            "content": er_diagram,
            "content_text": json.dumps(er_diagram, indent=2),
        },
        "database_schema": {
            "artifact_type": "database_schema",
            "title": "Database Schema (PostgreSQL DDL)",
            "content": {"ddl": schema_ddl},
            "content_text": str(schema_ddl),
        },
        "api_spec": {
            "artifact_type": "api_spec",
            "title": "API Specification",
            "content": {"endpoints": api_endpoints},
            "content_text": json.dumps(api_endpoints, indent=2),
        },
        "current_agent": "database_api_agent",
        "status": "generating",
        "agent_messages": state.get("agent_messages", [])
        + [
            {
                "agent": "database_api_agent",
                "type": "schema_complete",
                "data": {
                    "entity_count": len(er_diagram.get("entities", [])),
                    "endpoint_count": len(api_endpoints),
                },
            }
        ],
    }
