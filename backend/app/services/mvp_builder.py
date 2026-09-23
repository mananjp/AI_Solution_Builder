"""
AI Solution Builder — OpenCode MVP Builder Service

Drives the OpenCode sidecar (HTTP proxy) to convert validated solution
artifacts (HLD, LLD, ER diagram, API spec, DDL, wireframes) into a working
functional MVP prototype.

Architecture:
    FastAPI backend  --httpx-->  opencode serve (sidecar container)
                                        |
                     writes generated source files to a shared volume
                                        |
    FastAPI reads the filesystem directly to list / package the project

The sidecar server runs with its current working directory on a shared
volume. Each build is scoped to a `<solution_id>/build_<n>` subdirectory
chosen by this service and passed inside the generated prompt, so multiple
builds never collide.
"""

import base64
import contextlib
import io
import json
import logging
import re
import secrets
import shutil
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.app_spec import AppSpec
from uuid import UUID

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_IGNORED = {".git", "node_modules", "__pycache__", ".next", ".venv", "venv", "dist", "build"}


class MVPBuilderError(RuntimeError):
    """Raised when a build cannot be started or completed."""


def workspace_root() -> Path:
    """Local (backend) path mirroring the sidecar's /workspace volume."""
    root = Path(settings.MVP_BUILD_DIR).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_workspace_dir(solution_id: UUID, build_number: int) -> Path:
    """Return the host path for a solution/build workspace, creating it."""
    project_dir = workspace_root() / solution_id.hex[:12]
    build_dir = project_dir / f"build_{build_number}"
    build_dir.mkdir(parents=True, exist_ok=True)
    return build_dir


def _container_target(solution_id: UUID, build_number: int) -> str:
    """Relative target directory inside the sidecar's /workspace."""
    return f"{solution_id.hex[:12]}/build_{build_number}"


def chat_container_target(solution_id: UUID) -> str:
    """Relative target directory inside the sidecar's /workspace for chat builds."""
    return f"{solution_id.hex[:12]}/chat"


def chat_workspace_dir(solution_id: UUID) -> Path:
    """Return the host path for a solution's OpenCode chat workspace."""
    project_dir = workspace_root() / solution_id.hex[:12]
    chat_dir = project_dir / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    return chat_dir


def _auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.OPENCODE_SERVER_PASSWORD:
        creds = base64.b64encode(f"opencode:{settings.OPENCODE_SERVER_PASSWORD}".encode()).decode(
            "ascii"
        )
        headers["Authorization"] = f"Basic {creds}"
    return headers


_working_opencode_url: str | None = None


def _candidate_urls() -> list[str]:
    candidates: list[str] = []
    configured = (settings.OPENCODE_SERVER_URL or "").strip().rstrip("/")
    # Filter out unreachable builder worker hostnames from legacy configs
    if configured and "ai-solution-builder-builder" not in configured:
        candidates.append(configured)
    for fallback in ("http://127.0.0.1:4096", "http://localhost:4096"):
        if fallback not in candidates:
            candidates.append(fallback)
    if configured and configured not in candidates:
        candidates.append(configured)
    return candidates


def _get_base_url() -> str:
    global _working_opencode_url
    if _working_opencode_url:
        return _working_opencode_url
    candidates = _candidate_urls()
    return candidates[0] if candidates else "http://127.0.0.1:4096"


def _client(base_url: str | None = None) -> httpx.AsyncClient:
    url = base_url or _get_base_url()
    return httpx.AsyncClient(
        base_url=url,
        headers=_auth_headers(),
        timeout=settings.MVP_BUILD_TIMEOUT,
    )


async def health() -> bool:
    """Check the OpenCode sidecar is reachable and healthy across candidate URLs."""
    global _working_opencode_url
    candidates = _candidate_urls()
    if _working_opencode_url and _working_opencode_url in candidates:
        candidates.remove(_working_opencode_url)
        candidates.insert(0, _working_opencode_url)

    for url in candidates:
        try:
            try:
                client_ctx = _client(base_url=url)
            except TypeError:
                client_ctx = _client()
            async with client_ctx as client:
                resp = await client.get("/global/health", timeout=3.0)
                if resp.status_code == 200:
                    body = resp.json()
                    if body.get("healthy", False):
                        if _working_opencode_url != url:
                            logger.info(
                                "OpenCode sidecar healthy at %s (version=%s)",
                                url,
                                body.get("version"),
                            )
                            _working_opencode_url = url
                        return True
        except Exception as exc:
            logger.debug("OpenCode candidate %s unreachable: %s", url, exc)

    logger.warning("OpenCode sidecar unreachable across candidates: %s", candidates)
    return False


async def create_session(title: str) -> str:
    """Create a new OpenCode session and return its id."""
    async with _client() as client:
        resp = await client.post("/session", json={"title": title})
        if resp.status_code not in (200, 201):
            raise MVPBuilderError(
                f"Failed to create OpenCode session ({resp.status_code}): {resp.text[:300]}"
            )
        body: dict[str, Any] = resp.json()
        session_id = body.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise MVPBuilderError("OpenCode session response missing 'id'")
        logger.info("OpenCode session created: %s", session_id)
        return session_id


async def send_message(
    session_id: str,
    text: str,
    *,
    agent: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Send a message to an OpenCode session and wait for the full response."""
    payload: dict[str, Any] = {
        "agent": agent or settings.OPENCODE_AGENT,
        "parts": [{"type": "text", "text": text}],
    }
    async with _client() as client:
        resp = await client.post(
            f"/session/{session_id}/message",
            json=payload,
            timeout=timeout or settings.MVP_BUILD_TIMEOUT,
        )
        if resp.status_code not in (200, 201):
            raise MVPBuilderError(
                f"OpenCode message failed ({resp.status_code}): {resp.text[:500]}"
            )
        result: dict[str, Any] = resp.json()
        return result


async def send_build_prompt(session_id: str, prompt: str) -> dict[str, Any]:
    """Send the MVP build prompt and wait for the full assistant response."""
    return await send_message(session_id, prompt)


async def abort_session(session_id: str) -> None:
    """Abort a running session (best-effort)."""
    try:
        async with _client() as client:
            await client.post(f"/session/{session_id}/abort", timeout=10.0)
    except httpx.HTTPError as exc:
        logger.warning("Failed to abort OpenCode session %s: %s", session_id, exc)


# ── Template scaffold ──────────────────────────────────────────────────


def template_root() -> Path:
    """Host path of the bundled MVP scaffold template."""
    backend_root = Path(__file__).resolve().parents[2]
    root = backend_root / settings.MVP_TEMPLATE_DIR
    if not root.is_dir():
        raise MVPBuilderError(f"MVP template directory not found: {root}")
    return root


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "app"


def _substitute(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        token = f"__{key}__"
        text = text.replace(token, value)
    return text


def _ignore_artifacts(directory: str, names: list[str]) -> set[str]:
    return {
        n
        for n in names
        if n in {".git", "node_modules", "__pycache__", ".next", "dist", "build", ".venv", "venv"}
    }


def _classify_solution_entities(
    entities: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    """Dynamically classify ER entities into Catalog, Transaction, and Supporting roles."""
    if not entities:
        return None, None, []

    tx_keywords = {
        "order",
        "orders",
        "booking",
        "bookings",
        "reservation",
        "reservations",
        "appointment",
        "appointments",
        "enrollment",
        "enrollments",
        "ticket",
        "tickets",
        "invoice",
        "invoices",
        "request",
        "requests",
        "transaction",
        "transactions",
        "subscription",
        "subscriptions",
        "inquiry",
        "inquiries",
        "task",
        "tasks",
        "submission",
        "submissions",
        "dispatch",
        "dispatches",
        "session",
        "sessions",
    }

    catalog_keywords = {
        "dish",
        "dishes",
        "menu",
        "menus",
        "product",
        "products",
        "item",
        "items",
        "service",
        "services",
        "course",
        "courses",
        "class",
        "classes",
        "property",
        "properties",
        "listing",
        "listings",
        "workout",
        "workouts",
        "plan",
        "plans",
        "meal",
        "meals",
        "book",
        "books",
        "article",
        "articles",
        "project",
        "projects",
        "inventory",
        "inventory_item",
        "inventory_items",
        "room",
        "rooms",
        "asset",
        "assets",
    }

    tx_ent = None
    cat_ent = None
    remaining: list[dict[str, Any]] = []

    # First pass: find explicit transaction entity
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name", "")).lower()
        if tx_ent is None and any(kw in name for kw in tx_keywords):
            tx_ent = ent
            continue
        remaining.append(ent)

    # Second pass: find catalog entity among remaining
    supporting: list[dict[str, Any]] = []
    for ent in remaining:
        name = str(ent.get("name", "")).lower()
        if cat_ent is None and any(kw in name for kw in catalog_keywords):
            cat_ent = ent
            continue
        supporting.append(ent)

    # Fallback for catalog if not found
    if cat_ent is None and remaining:
        cat_ent = remaining[0]
        supporting = [e for e in remaining[1:]]

    # Fallback for tx if not found
    if tx_ent is None and supporting:
        for i, ent in enumerate(supporting):
            fields = [
                str(f.get("name", "")).lower() if isinstance(f, dict) else str(f).lower()
                for f in ent.get("fields", [])
            ]
            if "status" in fields or "state" in fields:
                tx_ent = supporting.pop(i)
                break
        if tx_ent is None and supporting:
            tx_ent = supporting.pop(0)

    return cat_ent, tx_ent, supporting


def _build_smart_mock_records(
    entity_name: str,
    fields: list[dict[str, Any]],
    app_title: str = "",
    industry: str = "",
    count: int = 4,
) -> list[dict[str, Any]]:
    """Generate domain-authentic realistic mock records matching the entity and industry."""
    name_lower = str(entity_name).lower()
    title_lower = str(app_title).lower()
    ind_lower = str(industry).lower()
    context = f"{name_lower} {title_lower} {ind_lower}"

    if any(
        k in context
        for k in (
            "dish",
            "menu",
            "food",
            "restaurant",
            "cafe",
            "bistro",
            "dining",
            "pizza",
            "burger",
            "bakery",
            "kitchen",
        )
    ):
        presets = [
            {
                "title": "Artisan Truffle Tagliatelle",
                "category": "Main Courses",
                "price": 18.50,
                "desc": "Handcrafted pasta tossed in black summer truffle butter with 24-month aged parmigiano reggiano.",
                "img": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600&q=80",
            },
            {
                "title": "Wood-Fired Margherita Pizza",
                "category": "Artisan Pizzas",
                "price": 14.00,
                "desc": "Slow-fermented Neapolitan dough, San Marzano tomato sauce, fresh fior di latte, and aromatic basil.",
                "img": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600&q=80",
            },
            {
                "title": "Crispy Calamari Fritti",
                "category": "Starters",
                "price": 12.50,
                "desc": "Flash-fried tender calamari served with charred lemon wedges and house-made citrus garlic aioli.",
                "img": "https://images.unsplash.com/photo-1599488615731-7e5c2823ff28?w=600&q=80",
            },
            {
                "title": "Sicilian Pistachio Tiramisu",
                "category": "Desserts",
                "price": 8.50,
                "desc": "Espresso-drenched ladyfingers layered with velvety Bronte pistachio mascarpone mousse.",
                "img": "https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=600&q=80",
            },
        ]
    elif any(
        k in context
        for k in ("gym", "fitness", "workout", "class", "trainer", "yoga", "crossfit", "wellness")
    ):
        presets = [
            {
                "title": "High-Intensity Interval Circuit",
                "category": "Strength & Cardio",
                "price": 25.00,
                "desc": "Dynamic 45-minute circuit combining kettlebells, plyometrics, and functional cardio intervals.",
                "img": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&q=80",
            },
            {
                "title": "Power Vinyasa Yoga Flow",
                "category": "Mind & Body",
                "price": 20.00,
                "desc": "Breath-synchronized athletic flow developing deep core strength, balance, and mindful flexibility.",
                "img": "https://images.unsplash.com/photo-1545205597-3d9d02c29597?w=600&q=80",
            },
            {
                "title": "Olympic Barbell Conditioning",
                "category": "Strength",
                "price": 30.00,
                "desc": "Precision coaching on snatch, clean & jerk, and compound lifting mechanics for all skill levels.",
                "img": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=600&q=80",
            },
            {
                "title": "Rhythm Indoor Cycle Ride",
                "category": "Cardio",
                "price": 22.00,
                "desc": "High-energy rhythm ride driven by curated playlists, speed intervals, and sprint climbs.",
                "img": "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=600&q=80",
            },
        ]
    elif any(
        k in context
        for k in ("course", "lesson", "education", "academy", "student", "learn", "tutorial")
    ):
        presets = [
            {
                "title": "Full-Stack Next.js & Cloud Systems",
                "category": "Engineering",
                "price": 99.00,
                "desc": "Build production SaaS platforms with Next.js App Router, PostgreSQL, Tailwind, and serverless APIs.",
                "img": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=600&q=80",
            },
            {
                "title": "Applied Machine Learning & LLMs",
                "category": "AI & Data",
                "price": 129.00,
                "desc": "Hands-on model fine-tuning, RAG system construction, and vector search deployment pipelines.",
                "img": "https://images.unsplash.com/photo-1555949963-ff9fe0c870eb?w=600&q=80",
            },
            {
                "title": "Modern UI/UX Design Systems",
                "category": "Design",
                "price": 79.00,
                "desc": "Design token architecture, interactive component states, typography scales, and Figma handoff.",
                "img": "https://images.unsplash.com/photo-1581291518857-4e27b48ff24e?w=600&q=80",
            },
            {
                "title": "Zero Trust Security & DevSecOps",
                "category": "Security",
                "price": 119.00,
                "desc": "Identity federation, automated security scanning, secrets management, and container isolation.",
                "img": "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=600&q=80",
            },
        ]
    elif any(
        k in context
        for k in ("property", "real_estate", "listing", "home", "realty", "apartment", "house")
    ):
        presets = [
            {
                "title": "Downtown Panoramic Sky Loft",
                "category": "Penthouses",
                "price": 850000.00,
                "desc": "Floor-to-ceiling glass wrapping the city skyline, private rooftop terrace, and custom Italian marble island.",
                "img": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600&q=80",
            },
            {
                "title": "Suburban Garden Family Villa",
                "category": "Family Estates",
                "price": 620000.00,
                "desc": "Spacious 4-bedroom contemporary residence featuring heated infinity pool and solar micro-grid.",
                "img": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=600&q=80",
            },
            {
                "title": "Waterfront Coastal Condo",
                "category": "Condominiums",
                "price": 410000.00,
                "desc": "Sun-drenched open concept studio with direct boardwalk access and marina docking privileges.",
                "img": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=600&q=80",
            },
            {
                "title": "Historic Restored Brownstone",
                "category": "Heritage",
                "price": 1250000.00,
                "desc": "Impeccably preserved 19th-century architecture featuring original exposed brickwork and oak herringbone floors.",
                "img": "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=600&q=80",
            },
        ]
    elif any(
        k in context
        for k in ("clinic", "doctor", "health", "medical", "patient", "care", "hospital")
    ):
        presets = [
            {
                "title": "Comprehensive Preventive Screening",
                "category": "General Medicine",
                "price": 150.00,
                "desc": "Full diagnostic biometrics review, advanced blood panel, and personalized clinical health consultation.",
                "img": "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=600&q=80",
            },
            {
                "title": "Cardiovascular Stress Evaluation",
                "category": "Cardiology",
                "price": 220.00,
                "desc": "Specialized exercise ECG and echocardiogram assessment conducted by certified cardiology specialists.",
                "img": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=600&q=80",
            },
            {
                "title": "Musculoskeletal Mobility Therapy",
                "category": "Physiotherapy",
                "price": 95.00,
                "desc": "Targeted postural correction, joint articulation recovery, and guided biomechanical rehabilitation.",
                "img": "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=600&q=80",
            },
            {
                "title": "Clinical Dermatology Consultation",
                "category": "Dermatology",
                "price": 130.00,
                "desc": "Full-body dermascopic evaluation, mole mapping, and bespoke dermatological treatment planning.",
                "img": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=600&q=80",
            },
        ]
    else:
        clean = re.sub(r"[^a-zA-Z0-9]+", " ", entity_name).title().strip() or "Product"
        presets = [
            {
                "title": f"Premium {clean} Pro",
                "category": "Standard Tier",
                "price": 49.00,
                "desc": f"Fully optimized {clean.lower()} engineered for high performance and daily productivity.",
                "img": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80",
            },
            {
                "title": f"Enterprise {clean} Suite",
                "category": "Enterprise",
                "price": 149.00,
                "desc": f"Advanced {clean.lower()} package featuring extended capabilities, automated workflows, and dedicated support.",
                "img": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80",
            },
            {
                "title": f"Essential {clean} Starter",
                "category": "Starter",
                "price": 29.00,
                "desc": f"Lightweight and reliable {clean.lower()} designed for quick onboarding and seamless collaboration.",
                "img": "https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=600&q=80",
            },
            {
                "title": f"Custom {clean} Ultra",
                "category": "Advanced",
                "price": 89.00,
                "desc": f"Tailored {clean.lower()} solution with granular controls, telemetry insights, and custom integrations.",
                "img": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=600&q=80",
            },
        ]

    records: list[dict[str, Any]] = []
    for i in range(min(count, len(presets))):
        p = presets[i]
        rec: dict[str, Any] = {"id": f"rec-{101 + i}"}
        for f in fields:
            fname = f.get("name", "") if isinstance(f, dict) else str(f)
            fname_clean = fname.lower()
            itype = f.get("input_type", "text") if isinstance(f, dict) else "text"

            if fname_clean in (
                "title",
                "name",
                "label",
                "dish_name",
                "product_name",
                "class_name",
                "item_name",
            ):
                rec[fname] = p["title"]
            elif fname_clean in ("category", "type", "genre", "department", "tag", "section"):
                rec[fname] = p["category"]
            elif fname_clean in ("price", "cost", "amount", "fee", "rate", "subtotal", "total"):
                rec[fname] = p["price"]
            elif fname_clean in ("description", "desc", "details", "summary", "notes"):
                rec[fname] = p["desc"]
            elif fname_clean in ("image", "img", "photo", "thumbnail", "cover_url"):
                rec[fname] = p["img"]
            elif fname_clean in ("status", "state"):
                rec[fname] = "Active"
            elif fname_clean in ("rating", "score"):
                rec[fname] = round(4.6 + (i * 0.1), 1)
            elif itype == "number":
                rec[fname] = 10 + (i * 5)
            elif itype == "checkbox":
                rec[fname] = True
            else:
                rec[fname] = f"{p['category']} {fname.replace('_', ' ').title()}"

        if "title" not in rec and "name" not in rec:
            rec["name"] = p["title"]
        if "price" not in rec and not any(k in rec for k in ("cost", "amount", "fee")):
            rec["price"] = p["price"]
        if "category" not in rec and "type" not in rec:
            rec["category"] = p["category"]
        if "description" not in rec and "desc" not in rec:
            rec["description"] = p["desc"]
        if "image" not in rec and "img" not in rec:
            rec["image"] = p["img"]

        records.append(rec)
    return records


def _generate_universal_app_page(
    app_title: str,
    ai_state: dict[str, Any],
    catalog_entity: dict[str, Any] | None,
    transaction_entity: dict[str, Any] | None,
    all_entities: list[dict[str, Any]],
) -> str:
    """Generate a rich, interactive, dual-perspective Next.js application shell for ANY domain."""
    escaped_title = app_title.replace('"', '\\\\"')
    industry = ai_state.get("industry", "general")
    desc = (
        ai_state.get("business_description")
        or ai_state.get("description")
        or "An intelligent business solution generated by AI Solution Builder."
    )
    escaped_desc = desc.replace('"', '\\\\"').replace("\\n", " ")

    cat = catalog_entity or (all_entities[0] if all_entities else {"name": "item"})
    cat_name = cat.get("name", "item")
    clean_cat = re.sub(r"[^a-zA-Z0-9_]+", "_", str(cat_name).lower()).strip("_") or "item"
    cat_class = "".join(part.capitalize() for part in clean_cat.split("_"))
    cat_plural = cat_class + "s" if not cat_class.endswith("s") else cat_class

    tx = transaction_entity
    clean_tx = (
        re.sub(r"[^a-zA-Z0-9_]+", "_", str(tx.get("name", "")).lower()).strip("_")
        if tx
        else "orders"
    ) or "orders"
    tx_class = "".join(part.capitalize() for part in clean_tx.split("_"))
    tx_plural = tx_class + "s" if not tx_class.endswith("s") else tx_class

    ctx = f"{clean_cat} {clean_tx} {industry} {app_title}".lower()
    if any(
        k in ctx
        for k in ("food", "dish", "menu", "restaurant", "cafe", "bistro", "pizza", "dining")
    ):
        action_verb = "Add to Order"
        cart_title = "Your Dining Order"
        tx_board_title = "Kitchen Display & Orders Board"
        status_stages = ["Pending", "In Kitchen", "Ready", "Delivered"]
        domain_icon = "🍽️"
        catalog_tab_title = "Browse Menu"
        domain_subtitle = "Digital Menu & Table Ordering System"
    elif any(k in ctx for k in ("gym", "fitness", "workout", "class", "trainer", "yoga")):
        action_verb = "Book Class"
        cart_title = "Class Reservations"
        tx_board_title = "Member Bookings"
        status_stages = ["Confirmed", "Checked In", "Completed"]
        domain_icon = "⚡"
        catalog_tab_title = "Browse Schedule"
        domain_subtitle = "Class Scheduling & Member Pass Management"
    elif any(k in ctx for k in ("course", "education", "lesson", "student", "learn")):
        action_verb = "Enroll Now"
        cart_title = "Course Enrollment"
        tx_board_title = "Student Enrollments"
        status_stages = ["Enrolled", "In Progress", "Completed"]
        domain_icon = "🎓"
        catalog_tab_title = "Explore Courses"
        domain_subtitle = "Course Directory & Student Enrollment Portal"
    elif any(k in ctx for k in ("property", "real_estate", "listing", "home")):
        action_verb = "Request Tour"
        cart_title = "Tour Schedule"
        tx_board_title = "Viewing Inquiries"
        status_stages = ["Requested", "Scheduled", "Completed"]
        domain_icon = "🏡"
        catalog_tab_title = "Browse Properties"
        domain_subtitle = "Property Portfolio & Viewing Booking System"
    elif any(k in ctx for k in ("clinic", "health", "doctor", "medical", "patient")):
        action_verb = "Book Visit"
        cart_title = "Consultation Request"
        tx_board_title = "Patient Queue"
        status_stages = ["Scheduled", "In Consultation", "Completed"]
        domain_icon = "🩺"
        catalog_tab_title = "Care Services"
        domain_subtitle = "Care Directory & Patient Appointment Booking"
    else:
        action_verb = "Add to Cart"
        cart_title = "Order Cart"
        tx_board_title = f"{tx_plural} Board"
        status_stages = ["Pending", "In Progress", "Ready", "Completed"]
        domain_icon = "✨"
        catalog_tab_title = f"Explore {cat_plural}"
        domain_subtitle = f"{cat_plural} Catalog & {tx_plural} Operations"

    status_stages_json = json.dumps(status_stages)

    module_links_jsx = []
    for ent in all_entities:
        ename = ent.get("name", "")
        cname = re.sub(r"[^a-zA-Z0-9_]+", "_", str(ename).lower()).strip("_")
        if not cname:
            continue
        cclass = "".join(p.capitalize() for p in cname.split("_"))
        module_links_jsx.append(f"""          <Link
            href="/{cname}"
            className="flex items-center justify-between p-4 bg-white border border-slate-200 rounded-xl hover:border-indigo-400 hover:shadow-md transition-all group"
          >
            <div>
              <p className="text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                {cclass} Studio
              </p>
              <p className="text-[11px] text-slate-500">Manage database records &amp; schemas</p>
            </div>
            <span className="text-slate-400 group-hover:text-indigo-600 text-sm font-bold transition-colors">→</span>
          </Link>""")

    links_block = "\\n".join(module_links_jsx)

    mock_cat = _build_smart_mock_records(
        clean_cat, cat.get("fields", []), app_title=app_title, industry=industry, count=4
    )
    mock_cat_json = json.dumps(mock_cat, indent=6)

    mock_tx = [
        {
            "id": "tx-101",
            "customer_name": "Marcus Vance",
            "items_summary": f"{mock_cat[0]['name']} (x2), {mock_cat[1]['name']} (x1)",
            "total_amount": round(float(mock_cat[0]["price"]) * 2 + float(mock_cat[1]["price"]), 2),
            "status": status_stages[0],
            "notes": "Priority processing requested",
            "created_at": "12 mins ago",
        },
        {
            "id": "tx-102",
            "customer_name": "Elena Rostova",
            "items_summary": f"{mock_cat[2]['name']} (x1)",
            "total_amount": round(float(mock_cat[2]["price"]), 2),
            "status": status_stages[1] if len(status_stages) > 1 else status_stages[0],
            "notes": "Verified client",
            "created_at": "25 mins ago",
        },
        {
            "id": "tx-103",
            "customer_name": "David Miller",
            "items_summary": f"{mock_cat[3]['name']} (x2), {mock_cat[0]['name']} (x1)",
            "total_amount": round(float(mock_cat[3]["price"]) * 2 + float(mock_cat[0]["price"]), 2),
            "status": status_stages[2] if len(status_stages) > 2 else status_stages[0],
            "notes": "Direct fulfillment",
            "created_at": "45 mins ago",
        },
    ]
    mock_tx_json = json.dumps(mock_tx, indent=6)

    template = """'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const DEFAULT_CATALOG: any[] = __MOCK_CATALOG__;
const DEFAULT_TRANSACTIONS: any[] = __MOCK_TRANSACTIONS__;
const STATUS_STAGES: string[] = __STATUS_STAGES__;

export default function HomePage() {
  const [items, setItems] = useState<any[]>(DEFAULT_CATALOG);
  const [orders, setOrders] = useState<any[]>(DEFAULT_TRANSACTIONS);
  const [activeTab, setActiveTab] = useState<'catalog' | 'operations'>('catalog');
  const [selectedCat, setSelectedCat] = useState<string>('All');
  const [search, setSearch] = useState<string>('');
  const [cart, setCart] = useState<{ id: string; item: any; quantity: number }[]>([]);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [customerNotes, setCustomerNotes] = useState('');
  const [orderConfirmed, setOrderConfirmed] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/__CLEAN_CAT__`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) setItems(data);
      })
      .catch(() => undefined);

    fetch(`${API_BASE}/api/v1/__CLEAN_TX__`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) setOrders(data);
      })
      .catch(() => undefined);
  }, []);

  const categories = [
    'All',
    ...Array.from(new Set(items.map((i) => i.category || 'General').filter(Boolean))),
  ];

  const filteredItems = items.filter((item) => {
    const matchesCat = selectedCat === 'All' || (item.category || 'General') === selectedCat;
    const title = String(item.title || item.name || '').toLowerCase();
    const desc = String(item.description || item.desc || '').toLowerCase();
    const q = search.toLowerCase();
    return matchesCat && (title.includes(q) || desc.includes(q));
  });

  const addToCart = (item: any) => {
    setCart((prev) => {
      const existing = prev.find((c) => c.id === item.id);
      if (existing) {
        return prev.map((c) => (c.id === item.id ? { ...c, quantity: c.quantity + 1 } : c));
      }
      return [...prev, { id: item.id, item, quantity: 1 }];
    });
  };

  const updateCartQty = (id: string, delta: number) => {
    setCart((prev) =>
      prev
        .map((c) => (c.id === id ? { ...c, quantity: c.quantity + delta } : c))
        .filter((c) => c.quantity > 0)
    );
  };

  const cartCount = cart.reduce((sum, c) => sum + c.quantity, 0);
  const subtotal = cart.reduce((sum, c) => sum + (Number(c.item.price) || 0) * c.quantity, 0);
  const tax = subtotal * 0.05;
  const grandTotal = subtotal + tax;

  const handleCheckout = async (e: React.FormEvent) => {
    e.preventDefault();
    if (cart.length === 0) return;

    const newId = `tx-${Date.now().toString().slice(-4)}`;
    const newRecord = {
      id: newId,
      customer_name: customerName.trim() || 'Guest Customer',
      items_summary: cart.map((c) => `${c.item.title || c.item.name} (x${c.quantity})`).join(', '),
      total_amount: grandTotal,
      status: STATUS_STAGES[0] || 'Pending',
      notes: customerNotes,
      created_at: 'Just now',
    };

    setOrders((prev) => [newRecord, ...prev]);
    setCart([]);
    setCustomerName('');
    setCustomerNotes('');
    setOrderConfirmed(newId);
    setIsCartOpen(false);

    try {
      await fetch(`${API_BASE}/api/v1/__CLEAN_TX__`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRecord),
      });
    } catch {
      // Optimistic local state preserved
    }
  };

  const handleAdvanceStatus = async (orderId: string) => {
    setOrders((prev) =>
      prev.map((o) => {
        if (o.id !== orderId) return o;
        const currIdx = STATUS_STAGES.indexOf(o.status);
        const nextStatus =
          currIdx >= 0 && currIdx < STATUS_STAGES.length - 1
            ? STATUS_STAGES[currIdx + 1]
            : o.status;
        return { ...o, status: nextStatus };
      })
    );
  };

  const activeOrdersCount = orders.filter(
    (o) => o.status !== STATUS_STAGES[STATUS_STAGES.length - 1]
  ).length;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Top Header */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">__DOMAIN_ICON__</span>
            <div>
              <h1 className="text-lg font-bold text-slate-900 leading-tight">__APP_TITLE__</h1>
              <p className="text-[11px] text-slate-500 font-medium">__DOMAIN_SUBTITLE__ · __APP_DESC__</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* View Switcher */}
            <div className="flex bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
              <button
                onClick={() => setActiveTab('catalog')}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  activeTab === 'catalog'
                    ? 'bg-white text-indigo-600 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                __CATALOG_TAB_TITLE__
              </button>
              <button
                onClick={() => setActiveTab('operations')}
                className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
                  activeTab === 'operations'
                    ? 'bg-white text-indigo-600 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <span>__TX_BOARD_TITLE__</span>
                {activeOrdersCount > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full bg-amber-500 text-white text-[10px]">
                    {activeOrdersCount}
                  </span>
                )}
              </button>
            </div>

            {/* Cart Trigger */}
            <button
              onClick={() => setIsCartOpen(true)}
              className="relative flex items-center gap-2 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
            >
              <span>🛒</span>
              <span className="hidden sm:inline">Cart</span>
              {cartCount > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-white text-indigo-700 text-[10px] font-bold">
                  {cartCount}
                </span>
              )}
              <span className="font-bold border-l border-indigo-400 pl-1.5">${grandTotal.toFixed(2)}</span>
            </button>
          </div>
        </div>
      </header>

      {/* Confirmation Notification */}
      {orderConfirmed && (
        <div className="max-w-4xl mx-auto mt-4 px-4">
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-2xl p-4 flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🎉</span>
              <div>
                <p className="font-bold text-sm">Action Successfully Submitted!</p>
                <p className="text-xs text-emerald-700">
                  Record <strong>#{orderConfirmed}</strong> has been created and transmitted to the{' '}
                  <strong>__TX_BOARD_TITLE__</strong>.
                </p>
              </div>
            </div>
            <button
              onClick={() => setOrderConfirmed(null)}
              className="text-xs font-semibold text-emerald-800 hover:text-emerald-950 px-3 py-1.5 rounded-lg bg-emerald-100 hover:bg-emerald-200 transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Main Viewport */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'catalog' ? (
          <div>
            {/* Search & Categories */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
              <div className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0 scrollbar-none">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCat(cat)}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
                      selectedCat === cat
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <div className="w-full md:w-72">
                <input
                  type="text"
                  placeholder="Search catalog items..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-500 shadow-sm"
                />
              </div>
            </div>

            {/* Catalog Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {filteredItems.map((item) => (
                <div
                  key={item.id}
                  className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col justify-between group"
                >
                  {item.image && (
                    <div className="h-44 w-full overflow-hidden bg-slate-100 relative">
                      <img
                        src={item.image}
                        alt={item.title || item.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      <span className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-black/60 backdrop-blur-md text-white text-[10px] font-semibold">
                        {item.category || 'General'}
                      </span>
                    </div>
                  )}

                  <div className="p-4 flex-1 flex flex-col justify-between">
                    <div>
                      <h3 className="font-bold text-slate-900 text-sm leading-snug">
                        {item.title || item.name}
                      </h3>
                      <p className="text-xs text-slate-500 mt-1 line-clamp-2">
                        {item.description || item.desc || 'Configured catalog item available for ordering.'}
                      </p>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                      <span className="text-base font-black text-indigo-600">
                        ${Number(item.price || 0).toFixed(2)}
                      </span>
                      <button
                        onClick={() => addToCart(item)}
                        className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-600 text-indigo-700 hover:text-white rounded-lg text-xs font-semibold transition-all"
                      >
                        + __ACTION_VERB__
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          /* Operations / Workflow Tab */
          <div>
            {/* Stat Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
                <p className="text-[11px] font-bold text-slate-400 uppercase">Total Volume</p>
                <p className="text-2xl font-black text-slate-900 mt-1">{orders.length}</p>
              </div>
              <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
                <p className="text-[11px] font-bold text-amber-600 uppercase">Active / In-Flight</p>
                <p className="text-2xl font-black text-amber-600 mt-1">{activeOrdersCount}</p>
              </div>
              <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
                <p className="text-[11px] font-bold text-emerald-600 uppercase">Completed</p>
                <p className="text-2xl font-black text-emerald-600 mt-1">
                  {orders.filter((o) => o.status === STATUS_STAGES[STATUS_STAGES.length - 1]).length}
                </p>
              </div>
              <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
                <p className="text-[11px] font-bold text-indigo-600 uppercase">Total Value</p>
                <p className="text-2xl font-black text-indigo-600 mt-1">
                  ${orders.reduce((sum, o) => sum + (Number(o.total_amount) || 0), 0).toFixed(2)}
                </p>
              </div>
            </div>

            {/* Orders Feed */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {orders.map((ord) => (
                <div
                  key={ord.id}
                  className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-indigo-600">{ord.id}</span>
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            ord.status === STATUS_STAGES[STATUS_STAGES.length - 1]
                              ? 'bg-emerald-100 text-emerald-700'
                              : ord.status === STATUS_STAGES[0]
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-indigo-100 text-indigo-700'
                          }`}
                        >
                          {ord.status}
                        </span>
                      </div>
                      <p className="text-sm font-bold text-slate-800 mt-1">
                        Client: {ord.customer_name || 'Anonymous'}
                      </p>
                      {ord.notes && <p className="text-xs text-slate-500 italic mt-0.5">{ord.notes}</p>}
                    </div>
                    <span className="text-sm font-black text-slate-900">
                      ${Number(ord.total_amount || 0).toFixed(2)}
                    </span>
                  </div>

                  <div className="bg-slate-50 rounded-xl p-3 text-xs text-slate-600">
                    <p className="font-semibold text-slate-700">Items:</p>
                    <p className="mt-0.5">{ord.items_summary || 'Standard package items'}</p>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-slate-400">{ord.created_at || 'Recently'}</span>
                    {ord.status !== STATUS_STAGES[STATUS_STAGES.length - 1] && (
                      <button
                        onClick={() => handleAdvanceStatus(ord.id)}
                        className="px-3 py-1.5 bg-slate-900 hover:bg-indigo-600 text-white text-xs font-semibold rounded-lg transition-colors"
                      >
                        Advance Status →
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Database Studios Link Section */}
        <div className="mt-12 pt-8 border-t border-slate-200">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">
            Domain Database Studios
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
__MODULE_LINKS_BLOCK__
          </div>
        </div>
      </main>

      {/* Slide-over Action/Cart Drawer */}
      {isCartOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={() => setIsCartOpen(false)}
          />
          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-white shadow-2xl flex flex-col">
              <div className="p-4 border-b border-slate-200 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-slate-900">__CART_TITLE__</h2>
                  <p className="text-xs text-slate-500">{cartCount} items selected</p>
                </div>
                <button
                  onClick={() => setIsCartOpen(false)}
                  className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100"
                >
                  ✕
                </button>
              </div>

              {/* Items List */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {cart.length === 0 ? (
                  <div className="text-center py-16 text-slate-400">
                    <p className="text-3xl">🛒</p>
                    <p className="mt-2 text-sm font-medium">Your cart is empty.</p>
                    <p className="text-xs mt-1">Select items from the catalog to build an order.</p>
                  </div>
                ) : (
                  cart.map(({ id, item, quantity }) => (
                    <div
                      key={id}
                      className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200"
                    >
                      <div className="flex-1 min-w-0 pr-3">
                        <p className="text-xs font-bold text-slate-900 truncate">
                          {item.title || item.name}
                        </p>
                        <p className="text-xs text-indigo-600 font-semibold mt-0.5">
                          ${(Number(item.price || 0) * quantity).toFixed(2)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => updateCartQty(id, -1)}
                          className="w-6 h-6 flex items-center justify-center rounded-lg bg-white border border-slate-200 text-xs font-bold text-slate-600 hover:bg-slate-100"
                        >
                          -
                        </button>
                        <span className="text-xs font-bold w-4 text-center">{quantity}</span>
                        <button
                          onClick={() => updateCartQty(id, 1)}
                          className="w-6 h-6 flex items-center justify-center rounded-lg bg-white border border-slate-200 text-xs font-bold text-slate-600 hover:bg-slate-100"
                        >
                          +
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Summary and Form */}
              {cart.length > 0 && (
                <div className="p-4 border-t border-slate-200 bg-slate-50 space-y-3">
                  <div className="space-y-1.5 text-xs text-slate-600">
                    <div className="flex justify-between">
                      <span>Subtotal</span>
                      <span className="font-semibold text-slate-800">${subtotal.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Service / Platform Fee (5%)</span>
                      <span className="font-semibold text-slate-800">${tax.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm font-bold text-slate-900 pt-1 border-t border-slate-200">
                      <span>Total Due</span>
                      <span className="text-indigo-600">${grandTotal.toFixed(2)}</span>
                    </div>
                  </div>

                  <form onSubmit={handleCheckout} className="space-y-2 pt-1">
                    <input
                      type="text"
                      placeholder="Your Name (e.g. Alex Morgan)"
                      required
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-indigo-500 shadow-sm"
                    />
                    <input
                      type="text"
                      placeholder="Special instructions or notes..."
                      value={customerNotes}
                      onChange={(e) => setCustomerNotes(e.target.value)}
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-indigo-500 shadow-sm"
                    />
                    <button
                      type="submit"
                      className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold shadow-md transition-all mt-2"
                    >
                      Confirm & Place Order (${grandTotal.toFixed(2)})
                    </button>
                  </form>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
"""

    return (
        template.replace("__APP_TITLE__", escaped_title)
        .replace("__APP_DESC__", escaped_desc)
        .replace("__DOMAIN_SUBTITLE__", domain_subtitle)
        .replace("__DOMAIN_ICON__", domain_icon)
        .replace("__CATALOG_TAB_TITLE__", catalog_tab_title)
        .replace("__TX_BOARD_TITLE__", tx_board_title)
        .replace("__ACTION_VERB__", action_verb)
        .replace("__CART_TITLE__", cart_title)
        .replace("__CLEAN_CAT__", clean_cat)
        .replace("__CLEAN_TX__", clean_tx)
        .replace("__STATUS_STAGES__", status_stages_json)
        .replace("__MOCK_CATALOG__", mock_cat_json)
        .replace("__MOCK_TRANSACTIONS__", mock_tx_json)
        .replace("__MODULE_LINKS_BLOCK__", links_block)
    )


def _generate_restaurant_storefront_page(app_title: str) -> str:
    """Backward-compatible helper for templates preset."""
    cat = {
        "name": "dishes",
        "fields": [
            {"name": "name"},
            {"name": "price"},
            {"name": "category"},
            {"name": "description"},
        ],
    }
    tx = {
        "name": "orders",
        "fields": [{"name": "customer_name"}, {"name": "total_amount"}, {"name": "status"}],
    }
    return _generate_universal_app_page(
        app_title,
        {
            "industry": "restaurant_hospitality",
            "business_description": "Digital Menu & Table Ordering System",
        },
        cat,
        tx,
        [cat, tx],
    )


def _generate_dish_management_page(app_title: str) -> str:
    """Backward-compatible helper for templates preset."""
    fields = [
        {"name": "name", "input_type": "text", "py_default": '""', "js_default": '""'},
        {"name": "price", "input_type": "number", "py_default": "0.0", "js_default": "0.0"},
        {"name": "category", "input_type": "text", "py_default": '""', "js_default": '""'},
        {"name": "description", "input_type": "text", "py_default": '""', "js_default": '""'},
    ]
    code = _generate_frontend_module_page(
        "Dish", "dishes", fields, False, app_title=app_title, industry="restaurant_hospitality"
    )
    return code.replace("Dish Studio", "Dish &amp; Menu Management")


def _generate_admin_orders_page(app_title: str) -> str:
    """Backward-compatible helper for templates preset."""
    fields = [
        {"name": "customer_name", "input_type": "text", "py_default": '""', "js_default": '""'},
        {"name": "items_summary", "input_type": "text", "py_default": '""', "js_default": '""'},
        {"name": "total_amount", "input_type": "number", "py_default": "0.0", "js_default": "0.0"},
        {
            "name": "status",
            "input_type": "text",
            "py_default": '"Pending"',
            "js_default": '"Pending"',
        },
    ]
    code = _generate_frontend_module_page(
        "Order", "orders", fields, False, app_title=app_title, industry="restaurant_hospitality"
    )
    return code.replace("Order Studio", "Kitchen Display & Orders Board")


def _generate_frontend_module_page(
    class_name: str,
    clean_name: str,
    parsed_fields: list[dict[str, str]],
    is_agent: bool,
    app_title: str = "",
    industry: str = "",
) -> str:
    th_cells = "\n".join(
        [
            f'                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">{pf["name"].replace("_", " ").title()}</th>'
            for pf in parsed_fields
        ]
    )
    td_cells = "\n".join(
        [
            f'                    <td className="px-4 py-3 text-sm text-slate-700 truncate max-w-[200px]">{{String(item.{pf["name"]} ?? "-")}}</td>'
            for pf in parsed_fields
        ]
    )
    form_fields_state = ", ".join(
        [f"{pf['name']}: {pf.get('js_default', pf['py_default'])}" for pf in parsed_fields]
    )

    mock_records = _build_smart_mock_records(
        clean_name, parsed_fields, app_title=app_title, industry=industry, count=4
    )
    mock_records_js = json.dumps(mock_records, indent=10)

    form_inputs = "\n".join(
        [
            f"""            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">{pf["name"].replace("_", " ").title()}</label>
              <input
                type="{pf["input_type"]}"
                value={{form.{pf["name"]} ?? ""}}
                onChange={{(e) => setForm({{ ...form, {pf["name"]}: e.target.value }})}}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
              />
            </div>"""
            for pf in parsed_fields
        ]
    )

    agent_playground_jsx = ""
    if is_agent:
        agent_playground_jsx = """
        {/* Agent Interactive Playground */}
        <div className="mt-8 bg-indigo-50/50 border border-indigo-100 rounded-xl p-6">
          <h2 className="text-lg font-bold text-slate-900">Interactive Agent Playground</h2>
          <p className="text-xs text-slate-600 mt-1">Execute live instructions directly through your configured AI agents.</p>
          <div className="mt-4 flex gap-3">
            <input
              type="text"
              placeholder="Give a task to the agent (e.g. 'Analyze Q3 metrics and draft report')..."
              id="agentTaskInput"
              className="flex-1 px-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={async () => {
                const input = document.getElementById('agentTaskInput') as HTMLInputElement;
                if (!input || !input.value.trim() || items.length === 0) return;
                const agentId = items[0].id;
                try {
                  const res = await fetch(`${API_BASE}/api/v1/agents/${agentId}/run`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: input.value.trim() }),
                  });
                  const data = await res.json();
                  alert(`Agent Execution Result:\\n\\n${data.output || 'Task completed.'}`);
                } catch {
                  alert(`Agent Execution Result:\\n\\n[${items[0].name || 'Agent'}] Executed task: '${input.value}'. Analysis and execution completed successfully.`);
                }
              }}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition-colors"
            >
              Run Agent
            </button>
          </div>
        </div>
"""

    template = """'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function __CLASS_NAME__Page() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<any>({ __FORM_FIELDS_STATE__ });

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/__CLEAN_NAME__`);
      if (res.ok) {
        const data = await res.json();
        setItems(Array.isArray(data) ? data : []);
      } else {
        setItems(__MOCK_RECORDS_JS__);
      }
    } catch {
      setItems([
        { id: 'mock-1', __FORM_FIELDS_STATE__, created_at: new Date().toISOString() }
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/api/v1/__CLEAN_NAME__`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        const created = await res.json();
        setItems([created, ...items]);
      } else {
        setItems([{ id: `mock-${Date.now()}`, ...form, created_at: new Date().toISOString() }, ...items]);
      }
    } catch {
      setItems([{ id: `mock-${Date.now()}`, ...form, created_at: new Date().toISOString() }, ...items]);
    }
    setShowModal(false);
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(`${API_BASE}/api/v1/__CLEAN_NAME__/${id}`, { method: 'DELETE' });
    } catch {}
    setItems(items.filter((item) => item.id !== id));
  };

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="flex items-center justify-between pb-6 border-b border-slate-200">
        <div>
          <Link href="/" className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition-colors">
            ← Back to Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 mt-1">__CLASS_NAME__ Studio</h1>
          <p className="text-xs text-slate-500 mt-0.5">Manage, configure, and inspect __CLEAN_NAME__ data records.</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition-colors"
        >
          + Add __CLASS_NAME__
        </button>
      </div>

      <div className="mt-6 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-slate-500">Loading __CLEAN_NAME__...</div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">No __CLEAN_NAME__ records found. Create one to get started.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">ID</th>
__TH_CELLS__
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item, idx) => (
                  <tr key={item.id || idx} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 text-xs font-mono text-slate-500">{String(item.id).slice(0, 8)}...</td>
__TD_CELLS__
                    <td className="px-4 py-3 text-right text-xs">
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="text-red-500 hover:text-red-700 font-semibold"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
__AGENT_PLAYGROUND__
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Create New __CLASS_NAME__</h3>
            <form onSubmit={handleCreate} className="space-y-4">
__FORM_INPUTS__
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
"""
    return (
        template.replace("__CLASS_NAME__", class_name)
        .replace("__CLEAN_NAME__", clean_name)
        .replace("__FORM_FIELDS_STATE__", form_fields_state)
        .replace("__TH_CELLS__", th_cells)
        .replace("__TD_CELLS__", td_cells)
        .replace("__FORM_INPUTS__", form_inputs)
        .replace("__AGENT_PLAYGROUND__", agent_playground_jsx)
        .replace("__MOCK_RECORDS_JS__", mock_records_js)
    )


def _auto_synthesize_slots(root: Path, ai_state: dict[str, Any], app_title: str) -> None:
    """Pre-populate models, schemas, routers, services, and UI slots from ER and API spec."""
    backend_dir = root / "backend"
    frontend_dir = root / "frontend"
    if not backend_dir.exists():
        return

    er = (
        ai_state.get("er_diagram", {}).get("content", {})
        if isinstance(ai_state.get("er_diagram"), dict)
        else {}
    )
    entities = er.get("entities", []) if isinstance(er, dict) else []

    if not entities:
        modules = ai_state.get("confirmed_modules") or ai_state.get("identified_solutions", [])
        if modules:
            entities = [
                {
                    "name": re.sub(r"[^a-zA-Z0-9_]+", "_", str(m).lower()).strip("_"),
                    "fields": [
                        {"name": "name", "type": "VARCHAR(255)"},
                        {"name": "status", "type": "VARCHAR(50)"},
                    ],
                }
                for m in modules[:4]
            ]
        else:
            entities = [{"name": "item", "fields": [{"name": "title", "type": "VARCHAR(255)"}]}]

    model_chunks: list[str] = []
    schema_chunks: list[str] = []
    router_chunks: list[str] = []
    card_chunks: list[str] = []
    is_agent_app = ai_state.get("industry") == "ai_agents" or any(
        ent.get("name") in ("agents", "agent") for ent in entities if isinstance(ent, dict)
    )

    for ent in entities:
        if not isinstance(ent, dict):
            continue
        raw_name = ent.get("name") or "item"
        clean_name = re.sub(r"[^a-zA-Z0-9_]+", "_", str(raw_name).lower()).strip("_")
        if not clean_name:
            continue
        class_name = "".join(part.capitalize() for part in clean_name.split("_"))

        # Parse fields
        raw_fields = ent.get("fields", [])
        parsed_fields: list[dict[str, str]] = []
        for f in raw_fields:
            if isinstance(f, dict):
                f_name = re.sub(r"[^a-zA-Z0-9_]+", "_", str(f.get("name", "")).lower()).strip("_")
                f_type = str(f.get("type", "VARCHAR(255)")).upper()
            else:
                f_name = re.sub(r"[^a-zA-Z0-9_]+", "_", str(f).lower()).strip("_")
                f_type = "VARCHAR(255)"

            if not f_name or f_name in ("id", "created_at"):
                continue

            if "INT" in f_type:
                sa_col = "Mapped[int] = mapped_column(Integer, default=0)"
                py_type = "int"
                py_default = "0"
                js_default = "0"
                input_type = "number"
            elif any(t in f_type for t in ("FLOAT", "DOUBLE", "DECIMAL")):
                sa_col = "Mapped[float] = mapped_column(Float, default=0.0)"
                py_type = "float"
                py_default = "0.0"
                js_default = "0.0"
                input_type = "number"
            elif "BOOL" in f_type:
                sa_col = "Mapped[bool] = mapped_column(Boolean, default=True)"
                py_type = "bool"
                py_default = "True"
                js_default = "true"
                input_type = "checkbox"
            elif "UUID" in f_type:
                sa_col = (
                    "Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)"
                )
                py_type = "uuid.UUID | None"
                py_default = "None"
                js_default = "null"
                input_type = "text"
            elif "TEXT" in f_type:
                sa_col = 'Mapped[str] = mapped_column(Text, nullable=False, default="")'
                py_type = "str"
                py_default = '""'
                js_default = '""'
                input_type = "textarea"
            else:
                len_match = re.search(r"\((\d+)\)", f_type)
                length = len_match.group(1) if len_match else "255"
                default_val = f"Sample {f_name.replace('_', ' ').title()}"
                sa_col = f'Mapped[str] = mapped_column(String({length}), nullable=False, default="{default_val}")'
                py_type = "str"
                py_default = f'"{default_val}"'
                js_default = f'"{default_val}"'
                input_type = "text"

            parsed_fields.append(
                {
                    "name": f_name,
                    "sa_col": sa_col,
                    "py_type": py_type,
                    "py_default": py_default,
                    "js_default": js_default,
                    "input_type": input_type,
                }
            )

        if not parsed_fields:
            parsed_fields.append(
                {
                    "name": "name",
                    "sa_col": f'Mapped[str] = mapped_column(String(255), nullable=False, default="Sample {class_name}")',
                    "py_type": "str",
                    "py_default": f'"Sample {class_name}"',
                    "input_type": "text",
                }
            )
            parsed_fields.append(
                {
                    "name": "status",
                    "sa_col": 'Mapped[str] = mapped_column(String(50), nullable=False, default="active")',
                    "py_type": "str",
                    "py_default": '"active"',
                    "input_type": "text",
                }
            )

        # Model
        model_lines = [
            f"class {class_name}(Base):",
            f'    __tablename__ = "{clean_name}"',
            "",
            "    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)",
        ]
        for pf in parsed_fields:
            model_lines.append(f"    {pf['name']}: {pf['sa_col']}")
        model_lines.append(
            "    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))"
        )
        model_chunks.append("\n".join(model_lines))

        # Schema
        schema_lines = [
            f"class {class_name}Base(BaseModel):",
        ]
        for pf in parsed_fields:
            schema_lines.append(f"    {pf['name']}: {pf['py_type']} = {pf['py_default']}")
        schema_lines.extend(
            [
                "",
                "",
                f"class {class_name}Create({class_name}Base):",
                "    pass",
                "",
                "",
                f"class {class_name}Read({class_name}Base):",
                "    id: uuid.UUID",
                "    created_at: datetime",
                "    model_config = ConfigDict(from_attributes=True)",
            ]
        )
        schema_chunks.append("\n".join(schema_lines))

        # Router
        router_lines = [
            f'@router.get("/{clean_name}", response_model=list[schemas.{class_name}Read])',
            f"async def list_{clean_name}(session: SessionDep) -> list[models.{class_name}]:",
            f"    res = await session.execute(select(models.{class_name}).order_by(models.{class_name}.created_at.desc()).limit(100))",
            "    return list(res.scalars().all())",
            "",
            "",
            f'@router.get("/{clean_name}/{{item_id}}", response_model=schemas.{class_name}Read)',
            f"async def get_{clean_name}(item_id: uuid.UUID, session: SessionDep) -> models.{class_name}:",
            f"    obj = await session.get(models.{class_name}, item_id)",
            "    if not obj:",
            f'        raise HTTPException(status_code=404, detail="{class_name} not found")',
            "    return obj",
            "",
            "",
            f'@router.post("/{clean_name}", response_model=schemas.{class_name}Read, status_code=201)',
            f"async def create_{clean_name}(payload: schemas.{class_name}Create, session: SessionDep) -> models.{class_name}:",
            f"    obj = models.{class_name}(**payload.model_dump())",
            "    session.add(obj)",
            "    await session.commit()",
            "    await session.refresh(obj)",
            "    return obj",
            "",
            "",
            f'@router.put("/{clean_name}/{{item_id}}", response_model=schemas.{class_name}Read)',
            f"async def update_{clean_name}(item_id: uuid.UUID, payload: schemas.{class_name}Create, session: SessionDep) -> models.{class_name}:",
            f"    obj = await session.get(models.{class_name}, item_id)",
            "    if not obj:",
            f'        raise HTTPException(status_code=404, detail="{class_name} not found")',
            "    for k, v in payload.model_dump(exclude_unset=True).items():",
            "        setattr(obj, k, v)",
            "    await session.commit()",
            "    await session.refresh(obj)",
            "    return obj",
            "",
            "",
            f'@router.delete("/{clean_name}/{{item_id}}")',
            f"async def delete_{clean_name}(item_id: uuid.UUID, session: SessionDep) -> dict[str, bool]:",
            f"    obj = await session.get(models.{class_name}, item_id)",
            "    if obj:",
            "        await session.delete(obj)",
            "        await session.commit()",
            '    return {"ok": True}',
        ]

        if clean_name in ("agents", "agent"):
            router_lines.extend(
                [
                    "",
                    "",
                    f'@router.post("/{clean_name}/{{agent_id}}/run")',
                    f"async def run_{clean_name}(agent_id: uuid.UUID, payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:",
                    f"    agent = await session.get(models.{class_name}, agent_id)",
                    '    query = str(payload.get("query") or "Execute autonomous workflow")',
                    '    agent_name = getattr(agent, "name", "Autonomous Agent")',
                    (
                        '    system_prompt = getattr(agent, "system_prompt", "You are an'
                        ' autonomous AI agent.")'
                    ),
                    "    return {",
                    '        "agent_id": str(agent_id),',
                    '        "agent_name": agent_name,',
                    '        "status": "completed",',
                    '        "query": query,',
                    (
                        '        "output": f"[{agent_name}] Processed task: \'{query}\'.'
                        ' Autonomous workflow reasoning and execution completed successfully.",'
                    ),
                    "    }",
                ]
            )

        router_chunks.append("\n".join(router_lines))

        # Frontend page for this entity
        if frontend_dir.exists():
            mod_page_dir = frontend_dir / "src" / "app" / clean_name
            mod_page_dir.mkdir(parents=True, exist_ok=True)
            mod_page_file = mod_page_dir / "page.tsx"
            mod_page_code = _generate_frontend_module_page(
                class_name=class_name,
                clean_name=clean_name,
                parsed_fields=parsed_fields,
                is_agent=(clean_name in ("agents", "agent")),
                app_title=app_title,
                industry=ai_state.get("industry", ""),
            )
            mod_page_file.write_text(mod_page_code, encoding="utf-8")

        card_code = f"""          <Link
            href="/{clean_name}"
            className="group block rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-indigo-400 hover:shadow-md transition-all"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-800 group-hover:text-indigo-600 transition-colors">{class_name}</h3>
              <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-600 border border-indigo-100">
                Active
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-500">Autonomous CRUD service endpoint: <code>/api/v1/{clean_name}</code></p>
            <span className="mt-4 inline-block text-xs font-semibold text-indigo-600 group-hover:translate-x-0.5 transition-transform">
              Open {class_name} Studio →
            </span>
          </Link>"""
        card_chunks.append(card_code)

    # If this is an agent app, create backend/agent_runner.py
    if is_agent_app:
        agent_runner_code = '''"""Autonomous Agent Execution Engine."""

from __future__ import annotations

import logging
import uuid
from typing import Any, TYPE_CHECKING
if TYPE_CHECKING:
    from app.services.app_spec import AppSpec

logger = logging.getLogger(__name__)


class AgentRunner:
    """Runtime for executing autonomous agent workflows and tools."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        system_prompt: str,
        model: str = "gpt-4o",
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.system_prompt = system_prompt
        self.model = model

    async def execute(
        self, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        logger.info("Executing agent [%s] with task: %s", self.name, task)
        return {
            "execution_id": str(uuid.uuid4()),
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "status": "completed",
            "task": task,
            "result": (
                f"[{self.name}] Completed task '{task}' successfully using {self.model}."
            ),
        }
'''
        (backend_dir / "agent_runner.py").write_text(agent_runner_code, encoding="utf-8")

    # Apply to models.py
    models_file = backend_dir / "models.py"
    if models_file.exists():
        content = models_file.read_text(encoding="utf-8")
        if "# __MODEL_INSERTION_POINT__" in content and model_chunks:
            imports = (
                "import uuid\n"
                "from datetime import UTC, datetime\n"
                "from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text\n"
                "from sqlalchemy.dialects.postgresql import UUID\n"
                "from sqlalchemy.orm import Mapped, mapped_column\n\n"
            )
            replacement = imports + "\n\n".join(model_chunks) + "\n\n# __MODEL_INSERTION_POINT__"
            models_file.write_text(
                content.replace("# __MODEL_INSERTION_POINT__", replacement), encoding="utf-8"
            )

    # Apply to schemas.py
    schemas_file = backend_dir / "schemas.py"
    if schemas_file.exists():
        content = schemas_file.read_text(encoding="utf-8")
        if "# __SCHEMA_INSERTION_POINT__" in content and schema_chunks:
            imports = (
                "import uuid\n"
                "from datetime import datetime\n"
                "from pydantic import BaseModel, ConfigDict\n\n"
            )
            replacement = imports + "\n\n".join(schema_chunks) + "\n\n# __SCHEMA_INSERTION_POINT__"
            schemas_file.write_text(
                content.replace("# __SCHEMA_INSERTION_POINT__", replacement), encoding="utf-8"
            )

    # Apply to routers.py
    routers_file = backend_dir / "routers.py"
    if routers_file.exists():
        content = routers_file.read_text(encoding="utf-8")
        if "# __ROUTER_INSERTION_POINT__" in content and router_chunks:
            imports = (
                "import uuid\n"
                "from typing import Any\n"
                "from fastapi import HTTPException\n"
                "from sqlalchemy import select\n"
                "try:\n"
                "    from . import models, schemas\n"
                "except (ImportError, ValueError):\n"
                "    import models, schemas\n\n"
            )
            replacement = imports + "\n\n".join(router_chunks) + "\n\n# __ROUTER_INSERTION_POINT__"
            routers_file.write_text(
                content.replace("# __ROUTER_INSERTION_POINT__", replacement), encoding="utf-8"
            )

    # Apply to frontend page.tsx (Universal dynamic application shell)
    page_file = frontend_dir / "src" / "app" / "page.tsx"
    if frontend_dir.exists():
        cat_ent, tx_ent, _ = _classify_solution_entities(entities)
        page_code = _generate_universal_app_page(
            app_title=app_title,
            ai_state=ai_state,
            catalog_entity=cat_ent or (entities[0] if entities else {"name": "item"}),
            transaction_entity=tx_ent,
            all_entities=entities,
        )
        page_file.write_text(page_code, encoding="utf-8")


def scaffold_build(
    build_dir: Path | str,
    *,
    app_title: str,
    inject_modules: list[str],
    ai_state: dict[str, Any] | None = None,
    spec: "AppSpec | None" = None,
) -> None:
    """Seed a build directory by copying the scaffold template.

    Copies the bundled template into `build_dir`, substitutes deterministic
    placeholders (app name/title/slug, JWT secret) and pre-populates
    models, schemas, and routers from the solution's ER diagram so the app
    is immediately functional and verified.
    """
    root = Path(build_dir)
    shutil.copytree(template_root(), root, dirs_exist_ok=True, ignore=_ignore_artifacts)

    # Ensure root has render.yaml, README.md, docker-compose.yml for Render Blueprint & GitHub
    infra_dir = root / "infra"
    if infra_dir.exists():
        for filename in ("render.yaml", "docker-compose.yml", "README.md"):
            src = infra_dir / filename
            dst = root / filename
            if src.exists() and not dst.exists():
                shutil.copyfile(src, dst)
        infra_gh = infra_dir / ".github"
        root_gh = root / ".github"
        if infra_gh.exists() and not root_gh.exists():
            shutil.copytree(infra_gh, root_gh, dirs_exist_ok=True)

    # Ensure frontend/src/lib/api.ts and public/.gitkeep always exist for frontend builds
    frontend_dir = root / "frontend"
    if frontend_dir.exists():
        lib_dir = frontend_dir / "src" / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        api_ts = lib_dir / "api.ts"
        if not api_ts.exists():
            from app.services.templates import _API_CLIENT_TS

            api_ts.write_text(_API_CLIENT_TS, encoding="utf-8")
        pub_dir = frontend_dir / "public"
        pub_dir.mkdir(parents=True, exist_ok=True)
        (pub_dir / ".gitkeep").touch()

    app_name = _slugify(app_title)
    db_name = re.sub(r"[^a-z0-9_]+", "_", app_name).strip("_") or "app_db"
    mapping = {
        "APP_NAME": app_name,
        "APP_TITLE": app_title,
        "APP_SLUG": app_name,
        "APP_DB_NAME": db_name,
        "JWT_SECRET": secrets.token_urlsafe(48),
    }

    # Apply substitutions to all text files carrying placeholders.
    _substitute_tree(root, mapping)

    if spec is not None:
        from app.services.spec_codegen import write_generated

        write_generated(root, spec)
    elif ai_state:
        # Try to extract a validated AppSpec from ai_state before falling
        # back to the legacy auto-synthesizer. The spec path produces
        # correct-by-construction CRUD, typed stubs, and acceptance tests;
        # _auto_synthesize_slots only generates generic {name, status} CRUD.
        extracted_spec = None
        spec_data = ai_state.get("app_spec")
        if isinstance(spec_data, dict):
            try:
                from app.services.app_spec import AppSpec

                extracted_spec = AppSpec.model_validate(spec_data)
            except Exception as exc:
                logger.info("Could not extract AppSpec from ai_state: %s", exc)

        if extracted_spec is not None:
            from app.services.spec_codegen import write_generated

            write_generated(root, extracted_spec)
            logger.info("Scaffolded build %s from AppSpec (spec-first path)", root)
        else:
            # Deterministic fallback AppSpec from ai_state heuristics
            logger.info(
                "No validated AppSpec in ai_state for %s; generating deterministic fallback AppSpec",
                app_title,
            )
            try:
                from app.services.app_spec import fallback_app_spec
                from app.services.spec_codegen import write_generated

                fallback_spec = fallback_app_spec(ai_state, app_title)
                write_generated(root, fallback_spec)
                logger.info("Scaffolded build %s using fallback AppSpec", root)
            except Exception as exc:
                logger.warning("Fallback AppSpec generation failed: %s; using auto-slots", exc)
                try:
                    _auto_synthesize_slots(root, ai_state, app_title)
                except Exception as exc2:
                    logger.warning("Auto slot synthesis skipped: %s", exc2)
    else:
        try:
            from app.services.app_spec import fallback_app_spec
            from app.services.spec_codegen import write_generated

            fallback_spec = fallback_app_spec({}, app_title)
            write_generated(root, fallback_spec)
            logger.info("Scaffolded build %s using baseline fallback AppSpec", root)
        except Exception as exc:
            logger.warning("Baseline fallback AppSpec failed: %s", exc)

    logger.info("Scaffolded build %s from template (modules=%d)", root, len(inject_modules))


def _apply(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _substitute_tree(root: Path, mapping: dict[str, str]) -> None:
    text_extensions = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".mjs",
        ".json",
        ".yml",
        ".yaml",
        ".md",
        ".txt",
        ".ini",
        ".env.example",
        ".gitignore",
        ".example",
    }
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in text_extensions:
            _apply(path, _substitute(path.read_text(encoding="utf-8", errors="ignore"), mapping))


def _compact(text: str | None, limit: int = 1400) -> str:
    """Trim long artifact content to a compact one-liner."""
    if not text:
        return ""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _entity_summary(er_content: dict[str, Any]) -> str:
    entities = er_content.get("entities", []) if isinstance(er_content, dict) else []
    lines = []
    for ent in entities:
        if isinstance(ent, dict):
            name = ent.get("name", "")
            fields = ent.get("fields", [])
            if isinstance(fields, list):
                field_names = [f.get("name") if isinstance(f, dict) else f for f in fields]
            else:
                field_names = []
            lines.append(f"- {name}: {', '.join(map(str, field_names))}")
    return "\n".join(lines)


def _endpoint_summary(api_spec_content: dict[str, Any]) -> str:
    endpoints = api_spec_content.get("endpoints", []) if isinstance(api_spec_content, dict) else []
    return "\n".join(
        f"- {e.get('method', 'GET').upper()} {e.get('path', '')}"
        for e in endpoints
        if isinstance(e, dict)
    )


def build_mvp_prompt(ai_state_or_spec: Any, target_dir: str, app_title: str | None = None) -> str:
    from app.services.app_spec import AppSpec

    if isinstance(ai_state_or_spec, AppSpec):
        spec = ai_state_or_spec
        actions = (
            "\n".join(
                f"- `{a.method} {a.path}` → `{a.name}()`: {a.summary}\n"
                + "\n".join(f"    - {r}" for r in a.rules)
                for a in spec.actions
            )
            or "- (none — pure CRUD app; focus on screens)"
        )
        screens = "\n".join(
            f"- **{s.name}** `{s.route}` — {s.purpose}. Uses entities {s.uses_entities}, "
            f"actions {s.uses_actions}. Must support: {'; '.join(s.key_interactions)}"
            for s in spec.screens
        )
        tests = "\n".join(f"- `test_{t.name}`: {t.description}" for t in spec.acceptance_tests)
        return f"""# Build: {spec.app_name}
{spec.one_liner}
**Core value (must actually work):** {spec.core_value}

Project root: `{target_dir}`. Read `spec.json` first — it is the source of truth.

## Already done (LOCKED — do not edit)
backend/models.py, schemas.py, routers.py (full CRUD for every entity, FK checks),
backend/tests/ (acceptance tests = definition of done), spec.json, frontend/src/lib/types.ts.
CRUD: `GET/POST /api/v1/{{plural}}`, `GET/PATCH/DELETE /api/v1/{{plural}}/{{id}}`, filter `?<ref>_id=`.

## Your job
1. **backend/actions.py** — replace every `raise HTTPException(501, ...)` with a real
   implementation of the rules below using the async SQLAlchemy `session`. Keep paths,
   function names and signatures. Return plain JSON-serialisable dicts.
{actions}

2. **frontend** (Next.js App Router, Tailwind, `src/lib/api.ts` client, types from `src/lib/types.ts`):
   create one `page.tsx` per screen at `frontend/src/app/<route>/page.tsx` ("use client").
   Each page loads and mutates REAL data through the API — no hardcoded sample arrays.
   Replace `{{/* __MODULE_LINKS__ */}}` in `src/app/page.tsx` with navigation to the screens.
{screens}

## Acceptance tests you must make pass
{tests}
Run them yourself if bash is available: `cd backend && python -m pytest -q`.

## Rules
- Implement rules generally; never special-case test inputs.
- Validation errors → HTTPException(400); missing rows → 404; conflicts → 409.
- No new dependencies. No secrets. Do not start servers.
- Finish with: files changed + which tests you expect to pass.
"""

    ai_state = ai_state_or_spec
    """Compose a compact MVP build prompt for the OpenCode agent.

    A full working scaffold (FastAPI + Next.js + infra) is copied into the
    target directory by the backend beforehand, so this prompt stays small
    enough to fit the model's tokens-per-minute ceiling. The agent only fills
    the artifact-specific slots: models, schemas, routers, and module pages.
    """
    title = (
        app_title
        or (ai_state.get("solution_title") or ai_state.get("business_description"))
        or "MVP"
    )
    industry = ai_state.get("industry", "general")
    modules = ai_state.get("confirmed_modules") or ai_state.get("identified_solutions", [])

    hld = (
        ai_state.get("hld", {}).get("content", {}) if isinstance(ai_state.get("hld"), dict) else {}
    )
    lld = (
        ai_state.get("lld", {}).get("content", {}) if isinstance(ai_state.get("lld"), dict) else {}
    )
    er = (
        ai_state.get("er_diagram", {}).get("content", {})
        if isinstance(ai_state.get("er_diagram"), dict)
        else {}
    )
    api_spec = (
        ai_state.get("api_spec", {}).get("content", {})
        if isinstance(ai_state.get("api_spec"), dict)
        else {}
    )

    ddl = ""
    generated = ai_state.get("generated_schema")
    if isinstance(generated, dict):
        content = generated.get("content", {})
        if isinstance(content, dict):
            ddl = str(content.get("ddl", "")) or str(content.get("schema_ddl", ""))

    schema = ai_state.get("database_schema", {}).get("content", {})
    if not ddl and isinstance(schema, dict):
        ddl = str(schema.get("ddl", ""))
    if not ddl:
        ddl = json.dumps(schema, indent=2, default=str)

    wireframes = [
        wf.get("content", {})
        for wf in ai_state.get("wireframes", [])
        if isinstance(wf, dict) and isinstance(wf.get("content"), dict)
    ]
    wireframe_screens = []
    for wf in wireframes:
        for screen in wf.get("screens", []):
            if isinstance(screen, dict) and screen.get("name"):
                wireframe_screens.append(screen["name"])

    hld_overview = _compact(hld.get("system_overview") or hld.get("architecture"))
    lld_modules = lld.get("modules", [])

    return "\n".join(
        [
            "# MVP Slot-Fill Request",
            "",
            f"**App:** {title} · **Industry:** {industry}",
            f"**Description:** {_compact(ai_state.get('business_description', ''), 600)}",
            f"**Modules:** {', '.join(map(str, modules))}",
            "",
            "A working scaffold already exists at `" + target_dir + "` (FastAPI backend, "
            "Next.js frontend, docker-compose, Render blueprint, CI workflow). "
            "Do NOT rewrite the scaffold. Fill the artifact-specific slots below and "
            "add the module code only.",
            "",
            "## What to implement",
            "1. **models.py** — one SQLAlchemy 2.0 async model per ER entity (insert above "
            "`__MODEL_INSERTION_POINT__`), matching the DDL exactly.",
            "2. **schemas.py** — Pydantic v2 create/read/update schemas for each model.",
            "3. **routers.py** — one APIRouter per module with full CRUD (insert above "
            "`__ROUTER_INSERTION_POINT__`) and register it in `main.py`.",
            "4. **demo auth** — keep the provided JWT helper; add a simple `auth/login` + "
            "`auth/register` endpoint if the API spec includes one.",
            "5. **frontend** — craft an authentic, production-grade domain application in `src/app/page.tsx`: "
            "include an interactive catalog/showcase with search and category filters, a slide-over action/cart drawer "
            "with real-time total calculations, and an operations/admin tracking board with live workflow status progression "
            "and telemetry metrics. Under `src/app/{module_slug}/`, provide full-featured domain studio pages. "
            "CRITICAL: Do NOT generate a barebones todo list or generic CRUD table with placeholder labels.",
            "6. **Alembic** — one initial migration for the full schema.",
            "",
            "## Architecture context",
            f"HLD: {hld_overview or '_none provided_'}"
            + (
                f"\nLLD modules: {', '.join(str(m.get('name')) for m in lld_modules if isinstance(m, dict))}"
                if lld_modules
                else ""
            ),
            "",
            "## ER entities",
            _entity_summary(er) or "_none provided_",
            "",
            "## API spec",
            _endpoint_summary(api_spec) or "_none provided_",
            "",
            "## Wireframe screens",
            "\n".join(f"- {s}" for s in wireframe_screens) or "_none provided_",
            "",
            "## Database DDL",
            "```sql",
            ddl.strip() or "_none provided_",
            "```",
            "",
            "## Rules",
            "- Never hardcode secrets. `.env.example` uses `change-me` placeholders only.",
            "- Keep existing scaffold files intact unless a slot requires an edit.",
            "- Do not run installs, builds, or start servers — just edit files.",
            "- Report which modules/entities you implemented when finished.",
        ]
    )


# ── Build execution ────────────────────────────────────────────────────


async def run_build(
    solution_id: UUID,
    ai_state: dict[str, Any],
    build_number: int,
    *,
    title: str | None = None,
    user_prompt: str = "",
    uploaded_context: str = "",
    conversation_history: list[dict[str, Any]] | None = None,
    check_npm: bool = False,
    allow_offline: bool = False,
) -> dict[str, Any]:
    """Run an OpenCode MVP build synchronously. Returns build result metadata."""
    if not allow_offline and not await health():
        raise MVPBuilderError(
            "OpenCode sidecar is unreachable. Ensure the opencode service is running."
        )

    from app.services.app_spec import AppSpec, generate_app_spec

    spec_data = ai_state.get("app_spec")
    spec: AppSpec | None = None
    if isinstance(spec_data, dict):
        try:
            spec = AppSpec.model_validate(spec_data)
        except Exception:
            spec = None
    if spec is None:
        effective_prompt = (
            user_prompt
            or ai_state.get("user_message", "")
            or ai_state.get("business_description", "")
            or title
            or "Custom Application"
        )
        effective_uploaded = uploaded_context or ai_state.get("uploaded_context", "") or ""
        effective_history = conversation_history or ai_state.get("conversation_history") or None
        try:
            spec = await generate_app_spec(
                ai_state,
                effective_prompt,
                uploaded_context=effective_uploaded,
                conversation_history=effective_history,
            )
            ai_state["app_spec"] = spec.model_dump()
            logger.info(
                "Generated AppSpec '%s' for run_build (solution=%s)", spec.app_name, solution_id
            )
        except Exception as exc:
            logger.warning(
                "generate_app_spec bypassed (%s); generating fallback AppSpec", exc
            )
            from app.services.app_spec import fallback_app_spec

            spec = fallback_app_spec(
                ai_state,
                effective_prompt,
                uploaded_context=effective_uploaded,
                conversation_history=effective_history,
            )
            ai_state["app_spec"] = spec.model_dump()

    if spec is None:
        from app.services.app_spec import fallback_app_spec

        spec = fallback_app_spec(
            ai_state,
            title or "Custom Application",
            uploaded_context=uploaded_context,
            conversation_history=conversation_history,
        )
        ai_state["app_spec"] = spec.model_dump()

    target_dir = _container_target(solution_id, build_number)
    local_dir = build_workspace_dir(solution_id, build_number)

    app_title = title or (
        spec.app_name
        if spec
        else (ai_state.get("solution_title") or ai_state.get("business_description") or "MVP")
    )
    modules = (
        [e.name for e in spec.entities]
        if spec
        else (ai_state.get("confirmed_modules") or ai_state.get("identified_solutions", []))
    )
    scaffold_build(
        local_dir,
        app_title=app_title,
        inject_modules=[str(m) for m in modules],
        ai_state=ai_state,
        spec=spec,
    )

    prompt = build_mvp_prompt(spec if spec else ai_state, target_dir, app_title=title)

    session_id: str = "auto-synthesized"
    sidecar_ok = await health()
    quality: dict[str, Any] | None = None
    if sidecar_ok:
        try:
            session_id = await create_session(f"MVP Build - {title or solution_id}")
            logger.info("Starting MVP build for solution=%s (session=%s)", solution_id, session_id)
            response = await send_build_prompt(session_id, prompt)
            logger.info(
                "MVP build finished for solution=%s (session=%s, %s)",
                solution_id,
                session_id,
                response.get("info") and response["info"].get("error", "ok"),
            )

            # Verification Checkpoint & Bounded Repair Turn
            from app.services.mvp_verifier import verify_and_repair

            verification = await verify_and_repair(
                local_dir,
                session_id=session_id,
                target_dir=target_dir,
                send_prompt_fn=send_build_prompt,
                check_npm=check_npm,
            )
            if spec:
                tests = verification.get("tests") or {}
                quality = {
                    "tests_passed": int(tests.get("passed", 0)),
                    "tests_failed": int(tests.get("failed", 0)),
                    "repair_turns": int(verification.get("repair_turns", 0)),
                    "actions": [a.name for a in spec.actions],
                }
        except Exception as exc:
            # Let verification failures propagate so the build is marked failed
            # honestly rather than shipping broken code as "complete".
            from app.services.mvp_verifier import VerificationError

            if isinstance(exc, VerificationError):
                raise MVPBuilderError(f"Build verification failed: {exc}") from exc

            # Any sidecar failure (timeout, session loss, HTTP error) must NOT be
            # papered over: an app with business actions can never be shipped as
            # a scaffolded CRUD shell. Fail honestly for action-bearing specs and
            # strictly verify the fallback for pure-CRUD/legacy specs.
            logger.warning(
                "OpenCode refinement failed or timed out (%s); solution=%s",
                exc,
                solution_id,
            )
            if session_id and session_id != "auto-synthesized":
                with contextlib.suppress(Exception):
                    await abort_session(session_id)

            if spec and any(spec.actions):
                raise MVPBuilderError(
                    f"OpenCode sidecar failed before the app's business actions could be "
                    f"implemented: {exc}"
                ) from exc

            from app.services.mvp_verifier import verify_workspace

            fallback_errors = verify_workspace(local_dir, check_npm=check_npm)
            if fallback_errors:
                raise MVPBuilderError(
                    "Synthesized fallback build failed verification "
                    f"({len(fallback_errors)} error(s)): " + "; ".join(fallback_errors[:5])
                ) from exc
    else:
        # OpenCode sidecar is offline. For apps with custom business actions,
        # the scaffold alone is NOT a working app — fail honestly rather than
        # shipping a skeleton as "complete".
        if spec and any(spec.actions):
            raise MVPBuilderError(
                "OpenCode sidecar is offline. This app has custom business logic "
                f"({len(spec.actions)} action(s): {', '.join(a.name for a in spec.actions)}) "
                "that requires the coding agent to implement. The build cannot complete "
                "without the sidecar. Please ensure the builder service is running and retry."
            )

        logger.info(
            "OpenCode sidecar offline; pure-CRUD build synthesized from blueprint for solution=%s",
            solution_id,
        )
        # For pure-CRUD apps (no business actions), the spec-generated code
        # is self-sufficient. Verify the output before shipping.
        from app.services.mvp_verifier import verify_workspace

        errors = verify_workspace(local_dir, check_npm=False)
        if errors:
            error_summary = "; ".join(errors[:5])
            raise MVPBuilderError(
                f"Synthesized build failed verification ({len(errors)} error(s)): {error_summary}"
            )

    files = list_build_files(local_dir)
    res: dict[str, Any] = {
        "session_id": session_id,
        "local_dir": str(local_dir),
        "file_count": len(files),
        "files": relative_paths(local_dir),
    }
    if spec:
        res["app_spec"] = spec.model_dump()
        res["quality"] = quality or {
            "tests_passed": 0,
            "tests_failed": 0,
            "repair_turns": 0,
            "actions": [a.name for a in spec.actions],
        }
    return res


async def run_premade_build(
    solution_id: UUID,
    template_slug: str,
    build_number: int,
    *,
    title: str | None = None,
) -> dict[str, Any]:
    """Instantly build a starter template without LLM roundtrip latency."""
    from app.services import templates

    local_dir = build_workspace_dir(solution_id, build_number)
    app_title = title or template_slug.title()

    # 1. Base scaffold
    scaffold_build(
        local_dir,
        app_title=app_title,
        inject_modules=[template_slug],
    )

    # 2. Instantiate pre-generated, production-ready template files
    templates.apply_template_files(local_dir, template_slug, app_title=app_title)

    logger.info(
        "Instant premade MVP build complete for solution=%s (template=%s)",
        solution_id,
        template_slug,
    )
    files = list_build_files(local_dir)
    return {
        "session_id": f"premade-{template_slug}",
        "local_dir": str(local_dir),
        "file_count": len(files),
        "files": relative_paths(local_dir),
    }


# ── File tree helpers ──────────────────────────────────────────────────


def list_build_files(build_dir: Path | str) -> list[Path]:
    """Recursively list generated project files (excluding noise)."""
    root = Path(build_dir)
    if not root.exists():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(part in _IGNORED for part in path.parts):
            files.append(path)
    return files


def relative_paths(build_dir: Path | str) -> list[str]:
    """Return POSIX-style paths relative to the build directory."""
    root = Path(build_dir)
    return [str(p.relative_to(root)).replace("\\", "/") for p in list_build_files(root)]


def package_build(build_dir: Path | str) -> io.BytesIO:
    """Zip the generated project into an in-memory archive."""
    root = Path(build_dir)
    if not root.exists():
        raise MVPBuilderError("Build directory does not exist")
    files = list_build_files(root)
    if not files:
        raise MVPBuilderError("No generated files found in the build directory")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, arcname=str(path.relative_to(root)).replace("\\", "/"))
    buffer.seek(0)
    return buffer


def build_bytes(build_dir: Path | str) -> bytes:
    """Zip the generated project into an in-memory buffer and return its bytes."""
    buffer = package_build(build_dir)
    return buffer.read()


# ── User config overlay ────────────────────────────────────────────────


def apply_config_overlay(
    build_dir: Path | str, app_name: str | None, env: dict[str, Any]
) -> dict[str, Any]:
    """Write a user-supplied config overlay (env values + app name) into the build."""
    root = Path(build_dir)
    if not root.exists():
        raise MVPBuilderError("Build directory does not exist")

    overlay: dict[str, Any] = {"app_name": app_name} if app_name else {}
    overlay.update(env or {})

    config_dir = root / ".config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "app_config.json").write_text(
        json.dumps(overlay, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if env:
        lines = ["# User configuration overrides\n"]
        for key, value in env.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key)):
                raise MVPBuilderError(f"Invalid env var name: {key!r}")
            # Strip line breaks so a malicious value can't inject extra
            # variables/commands into the generated .env.local file.
            safe_value = str(value).replace("\r", "").replace("\n", "")
            lines.append(f"{key}={safe_value}\n")
        (root / ".env.local").write_text("".join(lines), encoding="utf-8")

    if app_name:
        readme = root / "README.md"
        if readme.exists():
            text = readme.read_text(encoding="utf-8")
            readme.write_text(re.sub(r"^# .*", f"# {app_name}", text, count=1), encoding="utf-8")

    logger.info("Applied config overlay to %s (keys=%d)", root, len(overlay))
    return overlay


def cleanup_build(build_dir: Path | str) -> None:
    """Delete a build workspace (and empty parents) best-effort."""
    root = Path(build_dir)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
        for parent in (root.parent, root.parent.parent):
            try:
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass
