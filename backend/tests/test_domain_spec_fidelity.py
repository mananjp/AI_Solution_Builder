"""Domain detection and AppSpec fallback fidelity (no LLM, no DB).

Regression cover for a bad-build bug: a request for an "Employee Management
System" was built as an e-commerce app with modules named "productses" and
"orderses". Two independent defects combined to produce it.

1. ``_detect_domain`` tokenized the idiom "in order to" and scored its bare
   "order" token as an *exact* hit for the e-commerce domain (2.0), which
   outranked "employee" matching inside the plural token "employees" (1.5).
2. The AppSpec fallback appended "es" to any entity name already ending in
   "s", turning the already-plural "products" into "productses". Those names
   became module names, routes and table names.

The fallback also lacked any HR/employee branch, so an employee request with
no ER diagram degraded to the generic item/category CRUD, and its richness
caps (4 entities / 5 fields) truncated real diagrams into a thin toy.
"""

from app.core.llm import _detect_domain
from app.services.app_spec import fallback_app_spec, pluralize

# ── pluralize ────────────────────────────────────────────────────────────


class TestPluralize:
    def test_already_plural_names_are_untouched(self) -> None:
        # The exact regression: these became "productses" / "orderses".
        assert pluralize("products") == "products"
        assert pluralize("orders") == "orders"
        assert pluralize("employees") == "employees"
        assert pluralize("customers") == "customers"

    def test_singular_names_are_pluralized(self) -> None:
        assert pluralize("employee") == "employees"
        assert pluralize("order") == "orders"
        assert pluralize("product") == "products"
        assert pluralize("category") == "categories"
        assert pluralize("company") == "companies"
        assert pluralize("branch") == "branches"

    def test_sibilant_and_irregular_forms(self) -> None:
        assert pluralize("box") == "boxes"
        assert pluralize("dish") == "dishes"
        assert pluralize("quiz") == "quizzes"
        # Trailing "s" that is part of the stem, not a plural marker.
        assert pluralize("address") == "addresses"
        assert pluralize("campus") == "campuses"
        assert pluralize("person") == "people"

    def test_never_double_pluralizes(self) -> None:
        for name in ("product", "order", "employee", "category", "item", "invoice"):
            assert not pluralize(name).endswith("ses")


# ── domain detection ──────────────────────────────────────────────────────

HR = "HR & Workforce Management"
ECOM = "E-Commerce & Storefront Platform"
HEALTH = "Healthcare & Clinic Management System"
TASKS = "Project & Task Management System"
GENERIC = "Full-Stack Web Application"


class TestDomainDetection:
    def test_employee_requests_detect_hr(self) -> None:
        assert _detect_domain("Employee Management System")["app_type"] == HR
        assert _detect_domain("HR tool: employees, departments, leave, payroll")["app_type"] == HR

    def test_in_order_to_idiom_does_not_hijack_the_domain(self) -> None:
        # "in order to" is ubiquitous in generated prose; its "order" token used
        # to outscore the actual subject and force e-commerce.
        for text in (
            "Manage your employees in order to track attendance",
            "Build a system for employees in order to handle leave requests",
            "Create an employee management system. In order to support the team, track records.",
        ):
            assert _detect_domain(text)["app_type"] == HR, text

    def test_genuine_commerce_still_detects_ecommerce(self) -> None:
        assert _detect_domain("e-commerce store with cart and checkout")["app_type"] == ECOM
        assert _detect_domain("build an online shop to sell products")["app_type"] == ECOM
        assert _detect_domain("I need an order management system")["app_type"] == ECOM

    def test_other_domains_are_unaffected(self) -> None:
        assert _detect_domain("clinic with doctors and patients")["app_type"] == HEALTH
        assert _detect_domain("kanban board with tasks and sprints")["app_type"] == TASKS
        assert _detect_domain("a simple app")["app_type"] == GENERIC

    def test_misspelling_tolerance_is_preserved(self) -> None:
        assert _detect_domain("e-commerse storefront")["app_type"] == ECOM


# ── AppSpec fallback ──────────────────────────────────────────────────────


class TestFallbackAppSpec:
    def test_employee_request_does_not_build_products_or_orders(self) -> None:
        spec = fallback_app_spec({}, user_prompt="Employee Management System")
        names = {e.name for e in spec.entities}
        assert "employee" in names
        assert "products" not in names
        assert "orders" not in names

    def test_employee_spec_is_not_a_thin_toy(self) -> None:
        spec = fallback_app_spec({}, user_prompt="Employee Management System")
        assert len(spec.entities) >= 4
        assert all(len(e.fields) >= 3 for e in spec.entities)

    def test_plural_er_entity_names_are_not_double_pluralized(self) -> None:
        spec = fallback_app_spec(
            {
                "er_diagram": {
                    "content": {
                        "entities": [
                            {"name": "Products", "fields": [{"name": "title"}, {"name": "price"}]},
                            {"name": "Orders", "fields": [{"name": "status"}]},
                        ]
                    }
                }
            },
            user_prompt="Employee Management System",
        )
        plurals = [e.plural for e in spec.entities]
        assert "productses" not in plurals
        assert "orderses" not in plurals
        assert plurals == ["products", "orders"]

    def test_real_commerce_request_still_gets_commerce_entities(self) -> None:
        spec = fallback_app_spec(
            {}, user_prompt="Build a storefront to sell products in order to boost revenue"
        )
        assert "product" in {e.name for e in spec.entities}

    def test_fallback_respects_appspec_schema_limits(self) -> None:
        # The fallback emits one screen per entity plus a dashboard, and
        # AppSpec caps screens at 6, so the entity budget must stay at 5.
        spec = fallback_app_spec({}, user_prompt="Employee Management System")
        assert len(spec.screens) <= 6
        assert len(spec.entities) <= 6
