"""Tests for ML detection and dual-architecture generation (Next.js fullstack vs Unified Container)."""

from pathlib import Path

from app.services.app_spec import (
    AcceptanceTest,
    AppSpec,
    Entity,
    Screen,
    SpecField,
    TestStep,
    detect_ml_requirements,
)
from app.services.spec_codegen import write_generated


def test_detect_ml_requirements_detects_frameworks():
    assert detect_ml_requirements("Build an image classifier with PyTorch and YOLO")[0] is True
    assert "PyTorch" in detect_ml_requirements("Build an image classifier with PyTorch and YOLO")[1]
    assert "YOLO" in detect_ml_requirements("Build an image classifier with PyTorch and YOLO")[1]

    has_ml, frameworks = detect_ml_requirements("Churn prediction using scikit-learn random forest")
    assert has_ml is True
    assert "scikit-learn" in frameworks
    assert "Random Forest" in frameworks

    # Regular apps without local ML models
    assert (
        detect_ml_requirements("A project management tool with Kanban boards and milestones")[0]
        is False
    )
    assert (
        detect_ml_requirements("A support ticketing system that calls the OpenAI chat API")[0]
        is False
    )


def test_app_spec_defaults_to_next_fullstack_when_no_ml():
    spec = AppSpec(
        app_name="team_kanban",
        one_liner="Kanban for software teams",
        core_value="Real-time task tracking and collaboration",
        entities=[
            Entity(name="task", plural="tasks", fields=[SpecField(name="title", type="string")])
        ],
        actions=[],
        screens=[
            Screen(
                name="Tasks",
                route="/tasks",
                purpose="View tasks",
                uses_entities=["task"],
                key_interactions=["Create task"],
            )
        ],
        acceptance_tests=[
            AcceptanceTest(
                name="t1",
                description="create",
                steps=[TestStep(method="POST", path="/tasks", body={"title": "Test"})],
            ),
            AcceptanceTest(
                name="t2", description="list", steps=[TestStep(method="GET", path="/tasks")]
            ),
            AcceptanceTest(
                name="t3", description="del", steps=[TestStep(method="DELETE", path="/tasks/1")]
            ),
        ],
    )
    assert spec.architecture == "next_fullstack"
    assert spec.has_ml_model is False
    assert spec.ml_frameworks == []


def test_app_spec_auto_selects_unified_container_when_ml_present():
    spec = AppSpec(
        app_name="vision_tagger",
        one_liner="AI image tagger",
        core_value="Tag product photos with deep learning using a PyTorch neural network",
        entities=[
            Entity(name="photo", plural="photos", fields=[SpecField(name="url", type="string")])
        ],
        actions=[],
        screens=[
            Screen(
                name="Photos",
                route="/photos",
                purpose="Tag photos",
                uses_entities=["photo"],
                key_interactions=["Upload photo"],
            )
        ],
        acceptance_tests=[
            AcceptanceTest(
                name="t1",
                description="create",
                steps=[
                    TestStep(
                        method="POST", path="/photos", body={"url": "http://example.com/p.jpg"}
                    )
                ],
            ),
            AcceptanceTest(
                name="t2", description="list", steps=[TestStep(method="GET", path="/photos")]
            ),
            AcceptanceTest(
                name="t3", description="del", steps=[TestStep(method="DELETE", path="/photos/1")]
            ),
        ],
    )
    assert spec.architecture == "unified_container"
    assert spec.has_ml_model is True
    assert "PyTorch" in spec.ml_frameworks


def test_write_generated_produces_next_route_handlers_and_dockerfile(tmp_path: Path):
    (tmp_path / "frontend").mkdir(parents=True, exist_ok=True)
    spec = AppSpec(
        app_name="next_booking",
        one_liner="Appointment booking platform",
        core_value="Manages calendars and bookings",
        entities=[
            Entity(
                name="booking",
                plural="bookings",
                fields=[SpecField(name="customer", type="string")],
            )
        ],
        actions=[],
        screens=[
            Screen(
                name="Bookings",
                route="/bookings",
                purpose="View bookings",
                uses_entities=["booking"],
                key_interactions=["Book slot"],
            )
        ],
        acceptance_tests=[
            AcceptanceTest(
                name="t1",
                description="create",
                steps=[TestStep(method="POST", path="/bookings", body={"customer": "Alice"})],
            ),
            AcceptanceTest(
                name="t2", description="list", steps=[TestStep(method="GET", path="/bookings")]
            ),
            AcceptanceTest(
                name="t3", description="del", steps=[TestStep(method="DELETE", path="/bookings/1")]
            ),
        ],
    )
    write_generated(tmp_path, spec)

    # 1. Next.js Route Handlers
    assert (tmp_path / "frontend" / "src" / "app" / "api" / "v1" / "health" / "route.ts").exists()
    assert (tmp_path / "frontend" / "src" / "app" / "api" / "v1" / "bookings" / "route.ts").exists()
    assert (
        tmp_path / "frontend" / "src" / "app" / "api" / "v1" / "bookings" / "[id]" / "route.ts"
    ).exists()
    assert (tmp_path / "frontend" / "src" / "lib" / "db.ts").exists()

    # 2. Node.js single-stage Dockerfile
    dockerfile = tmp_path / "Dockerfile"
    assert dockerfile.exists()
    content = dockerfile.read_text(encoding="utf-8")
    assert "FROM node:20-alpine" in content
    assert "npm run build" in content
    assert "wget" in content or "curl" in content
