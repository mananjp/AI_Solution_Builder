"""Deterministic domain inference from a natural-language product request.

The offline fallback path has to produce a *recognisable* app even when no LLM
is reachable. A fixed `item`/`category` CRUD makes every build look identical
apart from its title, which is exactly the "it only renamed my project"
failure mode. This module reads the request instead:

* a curated domain lexicon recognises common verticals and yields rich,
  realistic entities with meaningful fields;
* when no vertical matches, the nouns the user actually typed ("members",
  "trainers", "classes") are lifted out of the sentence and used as real
  entities, each with fields inferred from the noun and its modifiers.

Everything here is pure, deterministic and unit-testable.
"""

from __future__ import annotations

import re

# ── Field hints keyed by singular noun ─────────────────────────────
# Used when a noun is lifted straight out of the prompt: the noun decides the
# shape of its own record so a "member" does not end up with a `price` column.
_FIELD_HINTS: dict[str, list[tuple[str, str]]] = {
    "member": [
        ("full_name", "string"),
        ("email", "string"),
        ("phone", "string"),
        ("status", "string"),
    ],
    "trainer": [("full_name", "string"), ("email", "string"), ("specialization", "string")],
    "class": [("title", "string"), ("schedule", "string"), ("capacity", "int")],
    "subscription": [("plan_name", "string"), ("price", "float"), ("renews_on", "date")],
    "product": [("name", "string"), ("sku", "string"), ("price", "float"), ("stock", "int")],
    "supplier": [("name", "string"), ("email", "string"), ("phone", "string")],
    "movement": [("quantity", "int"), ("reason", "string"), ("occurred_on", "date")],
    "warehouse": [("name", "string"), ("location", "string")],
    "patient": [
        ("full_name", "string"),
        ("email", "string"),
        ("phone", "string"),
        ("date_of_birth", "date"),
    ],
    "doctor": [("full_name", "string"), ("email", "string"), ("specialization", "string")],
    "appointment": [("scheduled_for", "datetime"), ("status", "string"), ("reason", "string")],
    "customer": [("full_name", "string"), ("email", "string"), ("phone", "string")],
    "order": [("placed_on", "datetime"), ("status", "string"), ("total", "float")],
    "invoice": [("client_name", "string"), ("amount", "float"), ("issued_on", "date")],
    "expense": [("description", "string"), ("amount", "float"), ("incurred_on", "date")],
    "employee": [
        ("full_name", "string"),
        ("email", "string"),
        ("role", "string"),
        ("department_name", "string"),
        ("salary", "float"),
        ("status", "string"),
        ("hire_date", "date"),
    ],
    "department": [
        ("name", "string"),
        ("code", "string"),
        ("manager_name", "string"),
        ("budget", "float"),
        ("location", "string"),
    ],
    "leave_request": [
        ("employee_name", "string"),
        ("leave_type", "string"),
        ("start_date", "date"),
        ("end_date", "date"),
        ("status", "string"),
    ],
    "performance_review": [
        ("employee_name", "string"),
        ("reviewer", "string"),
        ("review_period", "string"),
        ("rating", "int"),
        ("feedback", "string"),
    ],
    "course": [("title", "string"), ("credits", "int"), ("instructor", "string")],
    "student": [("full_name", "string"), ("email", "string"), ("enrolled_on", "date")],
    "property": [("title", "string"), ("address", "string"), ("rent", "float")],
    "tenant": [("full_name", "string"), ("email", "string"), ("phone", "string")],
    "vehicle": [("plate", "string"), ("make", "string"), ("model", "string"), ("year", "int")],
    "booking": [("starts_at", "datetime"), ("status", "string"), ("guests", "int")],
    "room": [("number", "string"), ("capacity", "int"), ("nightly_rate", "float")],
    "ticket": [("title", "string"), ("priority", "string"), ("status", "string")],
    "article": [("title", "string"), ("body", "text"), ("published", "bool")],
    "blog": [("title", "string"), ("body", "text"), ("published", "bool")],
    "message": [("subject", "string"), ("body", "text"), ("is_read", "bool")],
    "contact": [("name", "string"), ("email", "string"), ("message", "text")],
    "project": [("title", "string"), ("status", "string"), ("due_date", "date")],
    "task": [("title", "string"), ("status", "string"), ("due_date", "date")],
    "menu_item": [
        ("name", "string"),
        ("flavor", "string"),
        ("price", "float"),
        ("description", "text"),
        ("image_url", "string"),
        ("is_available", "bool"),
    ],
    "icecream": [
        ("name", "string"),
        ("flavor", "string"),
        ("price", "float"),
        ("description", "text"),
        ("image_url", "string"),
        ("is_available", "bool"),
    ],
    "flavor": [
        ("name", "string"),
        ("price", "float"),
        ("description", "text"),
        ("image_url", "string"),
    ],
    "dessert": [
        ("name", "string"),
        ("price", "float"),
        ("description", "text"),
        ("image_url", "string"),
    ],
}

_DEFAULT_FIELDS = [("name", "string"), ("description", "text")]
_NAME_FIELDS = [("name", "string"), ("description", "string")]

# ── Vertical lexicon ───────────────────────────────────────────────
# Ordered most-specific first: the first matching vertical wins, so narrow
# domains (clinic) are not swallowed by broad ones (booking).
_LEXICON: list[tuple[tuple[str, ...], list[tuple[str, str, list[tuple[str, str]]]]]] = [
    (
        (
            "clinic",
            "hospital",
            "patient",
            "doctor",
            "appointment",
            "medical",
            "dentist",
            "pharmacy",
        ),
        [
            (
                "patient",
                "patients",
                [
                    ("full_name", "string"),
                    ("email", "string"),
                    ("phone", "string"),
                    ("date_of_birth", "date"),
                ],
            ),
            (
                "doctor",
                "doctors",
                [("full_name", "string"), ("email", "string"), ("specialization", "string")],
            ),
            (
                "appointment",
                "appointments",
                [("scheduled_for", "datetime"), ("status", "string"), ("reason", "string")],
            ),
        ],
    ),
    (
        ("gym", "fitness", "workout", "membership", "trainer"),
        [
            (
                "member",
                "members",
                [
                    ("full_name", "string"),
                    ("email", "string"),
                    ("phone", "string"),
                    ("status", "string"),
                ],
            ),
            (
                "trainer",
                "trainers",
                [("full_name", "string"), ("email", "string"), ("specialization", "string")],
            ),
            (
                "class",
                "classes",
                [("title", "string"), ("schedule", "string"), ("capacity", "int")],
            ),
            (
                "subscription",
                "subscriptions",
                [("plan_name", "string"), ("price", "float"), ("renews_on", "date")],
            ),
        ],
    ),
    (
        ("inventory", "warehouse", "stock", "supply chain"),
        [
            (
                "product",
                "products",
                [("name", "string"), ("sku", "string"), ("price", "float"), ("stock", "int")],
            ),
            (
                "supplier",
                "suppliers",
                [("name", "string"), ("email", "string"), ("phone", "string")],
            ),
            (
                "stock_movement",
                "stock_movements",
                [("quantity", "int"), ("reason", "string"), ("occurred_on", "date")],
            ),
        ],
    ),
    (
        ("employee", "hr", "human resource", "workforce", "payroll", "staff", "onboarding"),
        [
            (
                "employee",
                "employees",
                [
                    ("full_name", "string"),
                    ("email", "string"),
                    ("role", "string"),
                    ("department_name", "string"),
                    ("salary", "float"),
                    ("status", "string"),
                    ("hire_date", "date"),
                ],
            ),
            (
                "department",
                "departments",
                [
                    ("name", "string"),
                    ("code", "string"),
                    ("manager_name", "string"),
                    ("budget", "float"),
                    ("location", "string"),
                ],
            ),
            (
                "leave_request",
                "leave_requests",
                [
                    ("employee_name", "string"),
                    ("leave_type", "string"),
                    ("start_date", "date"),
                    ("end_date", "date"),
                    ("status", "string"),
                ],
            ),
            (
                "performance_review",
                "performance_reviews",
                [
                    ("employee_name", "string"),
                    ("reviewer", "string"),
                    ("review_period", "string"),
                    ("rating", "int"),
                    ("feedback", "string"),
                ],
            ),
        ],
    ),
    (
        (
            "ice cream",
            "icecream",
            "ice-cream",
            "icecreams",
            "gelato",
            "sorbet",
            "sundae",
            "dessert",
            "frozen yogurt",
            "parlor",
            "sweet shop",
        ),
        [
            (
                "menu_item",
                "menu_items",
                [
                    ("name", "string"),
                    ("flavor", "string"),
                    ("price", "float"),
                    ("description", "text"),
                    ("image_url", "string"),
                    ("is_available", "bool"),
                ],
            ),
            (
                "order",
                "orders",
                [
                    ("customer_name", "string"),
                    ("item_name", "string"),
                    ("quantity", "int"),
                    ("total_price", "float"),
                    ("status", "string"),
                ],
            ),
            (
                "customer_review",
                "customer_reviews",
                [
                    ("customer_name", "string"),
                    ("rating", "int"),
                    ("comment", "text"),
                ],
            ),
        ],
    ),
    (
        ("restaurant", "cafe", "catering", "menu", "dine", "bakery"),
        [
            (
                "menu_item",
                "menu_items",
                [("name", "string"), ("price", "float"), ("category", "string")],
            ),
            (
                "table_order",
                "table_orders",
                [("table_number", "int"), ("status", "string"), ("total", "float")],
            ),
        ],
    ),
    (
        (
            "portfolio",
            "personal site",
            "showcase",
            "resume",
            "cv",
            "designer",
            "developer portfolio",
        ),
        [
            (
                "project",
                "projects",
                [
                    ("title", "string"),
                    ("description", "text"),
                    ("category", "string"),
                    ("live_url", "string"),
                    ("github_url", "string"),
                    ("image_url", "string"),
                    ("featured", "bool"),
                ],
            ),
            (
                "skill",
                "skills",
                [
                    ("name", "string"),
                    ("category", "string"),
                    ("proficiency", "int"),
                ],
            ),
            (
                "experience",
                "experiences",
                [
                    ("company", "string"),
                    ("role", "string"),
                    ("period", "string"),
                    ("description", "text"),
                ],
            ),
            (
                "contact_message",
                "contact_messages",
                [
                    ("sender_name", "string"),
                    ("email", "string"),
                    ("subject", "string"),
                    ("message", "text"),
                ],
            ),
        ],
    ),
    (
        ("school", "college", "university", "student", "course", "lms", "exam", "grade"),
        [
            (
                "student",
                "students",
                [("full_name", "string"), ("email", "string"), ("enrolled_on", "date")],
            ),
            (
                "course",
                "courses",
                [("title", "string"), ("credits", "int"), ("instructor", "string")],
            ),
            ("enrollment", "enrollments", [("status", "string"), ("enrolled_on", "date")]),
        ],
    ),
    (
        ("property", "rental", "tenant", "landlord", "real estate", "listing", "airbnb"),
        [
            (
                "property",
                "properties",
                [("title", "string"), ("address", "string"), ("nightly_rate", "float")],
            ),
            (
                "tenant",
                "tenants",
                [("full_name", "string"), ("email", "string"), ("phone", "string")],
            ),
            (
                "booking",
                "bookings",
                [("starts_on", "date"), ("ends_on", "date"), ("status", "string")],
            ),
        ],
    ),
    (
        ("ecommerce", "e-commerce", "shop", "store", "cart", "checkout", "product catalog"),
        [
            ("product", "products", [("name", "string"), ("price", "float"), ("stock", "int")]),
            (
                "customer",
                "customers",
                [("full_name", "string"), ("email", "string"), ("phone", "string")],
            ),
            (
                "order",
                "orders",
                [("placed_on", "datetime"), ("status", "string"), ("total", "float")],
            ),
        ],
    ),
    (
        ("invoice", "billing", "expense", "finance", "payment", "accounting", "budget"),
        [
            (
                "invoice",
                "invoices",
                [("client_name", "string"), ("amount", "float"), ("issued_on", "date")],
            ),
            (
                "expense",
                "expenses",
                [("description", "string"), ("amount", "float"), ("incurred_on", "date")],
            ),
        ],
    ),
    (
        ("hotel", "hostel", "resort", "room booking", "front desk"),
        [
            (
                "room",
                "rooms",
                [("number", "string"), ("capacity", "int"), ("nightly_rate", "float")],
            ),
            ("guest", "guests", [("full_name", "string"), ("email", "string")]),
            (
                "booking",
                "bookings",
                [("check_in", "date"), ("check_out", "date"), ("status", "string")],
            ),
        ],
    ),
    (
        ("support", "ticket", "helpdesk", "help desk", "service desk"),
        [
            (
                "ticket",
                "tickets",
                [("title", "string"), ("priority", "string"), ("status", "string")],
            ),
            ("customer", "customers", [("full_name", "string"), ("email", "string")]),
        ],
    ),
    (
        (
            "architect",
            "architecture",
            "architectural",
            "atelier",
            "interior design",
            "landscape design",
            "urban design",
        ),
        [
            (
                "project",
                "projects",
                [
                    ("name", "string"),
                    ("category", "string"),
                    ("location", "string"),
                    ("year", "int"),
                    ("description", "text"),
                    ("image_url", "string"),
                ],
            ),
            (
                "inquiry",
                "inquiries",
                [
                    ("client_name", "string"),
                    ("email", "string"),
                    ("project_type", "string"),
                    ("message", "text"),
                ],
            ),
        ],
    ),
    (
        ("task", "project", "todo", "kanban", "sprint", "backlog"),
        [
            (
                "project",
                "projects",
                [("title", "string"), ("status", "string"), ("due_date", "date")],
            ),
            ("task", "tasks", [("title", "string"), ("status", "string"), ("due_date", "date")]),
        ],
    ),
]

# Words that describe the *app*, not a record type. Treating these as entities
# produces exactly the "My Inventory Management System" table nobody wants.
_STOP_NOUNS = {
    "system",
    "systems",
    "app",
    "application",
    "applications",
    "platform",
    "software",
    "website",
    "site",
    "web",
    "tool",
    "portal",
    "dashboard",
    "project",
    "projects",
    "management",
    "manager",
    "service",
    "services",
    "solution",
    "solutions",
    "business",
    "company",
    "organization",
    "organisation",
    "team",
    "user",
    "users",
    "thing",
    "things",
    "stuff",
    "data",
    "information",
    "content",
    "page",
    "pages",
    "feature",
    "features",
    "need",
    "needs",
    "want",
    "wants",
    "make",
    "build",
    "create",
    "generate",
    "help",
    "please",
    "with",
    "and",
    "for",
    "the",
    "that",
    "this",
    "me",
    "my",
    "our",
    "we",
    "i",
    "you",
    "your",
    "yours",
    "it",
    "its",
    "his",
    "her",
    "hers",
    "him",
    "they",
    "them",
    "their",
    "theirs",
    "who",
    "whom",
    "whose",
    "showcase",
    "showcases",
    "showcasing",
    "can",
    "should",
    "would",
    "will",
    "have",
    "has",
    "are",
    "is",
    "be",
    "do",
    "does",
    "able",
    "simple",
    "basic",
    "modern",
    "full",
    "stack",
    "frontend",
    "backend",
    "web app",
    "web application",
    "price",
    "prices",
    "pricing",
    "cost",
    "costs",
    "image",
    "images",
    "photo",
    "photos",
    "picture",
    "pictures",
    "landing",
    "vendor",
    "vendors",
    "storefront",
    "shopfront",
    "ui",
    "ux",
}

_PLURAL_RE = re.compile(r"ies$|ses$|xes$|zes$|ches$|shes$|s$", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*")

# Python keywords/builtins that cannot be used as a generated class or table
# name — "class" and "order" are both extremely common domain nouns.
_RESERVED_ENTITY_NAMES = {
    "class",
    "import",
    "def",
    "return",
    "lambda",
    "global",
    "pass",
    "from",
    "for",
    "while",
    "if",
    "else",
    "try",
    "except",
    "with",
    "as",
    "in",
    "is",
    "not",
    "and",
    "or",
    "None",
    "True",
    "False",
    "self",
    "property",
    "type",
    "id",
    "input",
    "list",
    "dict",
    "set",
    "str",
    "int",
    "float",
    "bool",
    "object",
    "super",
    "range",
    "min",
    "max",
    "sum",
    "len",
    "print",
    "next",
    "open",
    "format",
    "hash",
    "help",
    "filter",
    "map",
    "zip",
    "sorted",
}

# Common verbs/intent verbs that follow "track"/"manage" etc.
_STOP_VERBS = {
    "track",
    "manage",
    "handle",
    "build",
    "create",
    "make",
    "add",
    "generate",
    "want",
    "need",
    "please",
    "let",
    "allow",
    "enable",
    "support",
    "show",
    "display",
    "list",
    "view",
    "see",
    "get",
    "set",
    "use",
    "have",
    "help",
}


def singularize(word: str) -> str:
    """Best-effort inverse of :func:`pluralize` for entity naming."""
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ses") and len(w) > 4:
        return w[:-2]
    if w.endswith("xes") and len(w) > 4:
        return w[:-2]
    if w.endswith("zes") and len(w) > 4:
        return w[:-2]
    if w.endswith("ches") and len(w) > 4:
        return w[:-2]
    if w.endswith("shes") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _title_from_prompt(prompt: str) -> str:
    """Turn a chat sentence into a clean product name.

    ``"Create a clinic appointment booking system"`` -> ``"Clinic Appointment Booking"``
    ``"I need an inventory management system for a warehouse"`` -> ``"Inventory Management"``
    ``"I am an ice cream vendor build me a landing page..."`` -> ``"Ice Cream Vendor Landing Page"``
    """
    text = re.sub(r"\s+", " ", (prompt or "").strip())
    if not text:
        return "Custom App"

    # Check for explicit named patterns: "called XYZ", "named XYZ"
    named_match = re.search(
        r"(?:called|named)\s+[\"']?([^\W_][\w\-\s]{1,40}?)[\"']?(?:\s+(?:for|with|that|which|\.|\,)|$)",
        text,
        flags=re.IGNORECASE,
    )
    if named_match:
        name = named_match.group(1).strip()
        if name:
            return name.title()

    # Persona detection: "i am an ice cream vendor build me a landing page..."
    persona_match = re.search(
        r"^\s*(?:i\s+am\s+(?:an?\s+)?|we\s+are\s+(?:an?\s+)?|as\s+an?\s+|i\s+run\s+(?:an?\s+)?|i\s+have\s+(?:an?\s+)?)(?P<persona>[a-zA-Z\s]{2,35}?)(?:[.,;]|\s+(?:and\s+)?(?:please\s+)?(?:can\s+you\s+|could\s+you\s+|i\s+(?:want|need|would\s+like)\s+(?:to\s+)?|(?:build|create|make|generate|design|develop|produce)\s+(?:me\s+)?(?:an?\s+)?))",
        text,
        flags=re.IGNORECASE,
    )
    if persona_match:
        persona = persona_match.group("persona").strip()
        persona_words = [
            w
            for w in _TOKEN_RE.findall(persona)
            if w.lower() not in ("a", "an", "the", "i", "am", "are", "we", "this", "my")
        ]
        if persona_words:
            clean_persona = " ".join(persona_words[:4]).title()
            if re.search(r"\blanding\s+page\b", text, re.IGNORECASE):
                return f"{clean_persona} Landing Page"
            if re.search(r"\bstorefront\b|\bshop\b|\bparlor\b", text, re.IGNORECASE):
                return f"{clean_persona} Storefront"
            return clean_persona

    # Target beneficiary detection: "landing page for an architect showcasing..."
    target_match = re.search(
        r"\b(?:landing\s+page|portfolio|website|storefront|app)\s+for\s+(?:an?\s+)?(?P<target>[a-zA-Z\s]{3,30}?)(?:\s+(?:showcasing|with|to|that|who|\.|\,)|$)",
        text,
        flags=re.IGNORECASE,
    )
    if target_match:
        target = target_match.group("target").strip()
        t_words = [
            w for w in _TOKEN_RE.findall(target)
            if w.lower() not in ("a", "an", "the", "this", "my", "our")
        ]
        if t_words:
            clean_target = " ".join(t_words[:3]).title()
            if clean_target.lower() in ("architect", "architecture", "designer", "artist"):
                return f"{clean_target} Studio Portfolio"
            return f"{clean_target} Platform"

    # Drop the leading request frame so the name is the subject, not the verb.
    text = re.sub(
        r"^\s*(please\s+)?(can you\s+|could you\s+|i\s+(want|need|would like)\s+(to\s+)?|"
        r"(build|create|make|generate|design|develop|produce)\s+(me\s+)?(?:an\b|a\b|the\b)?\s*)+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Cut at the first clause boundary — the product name rarely spans one.
    text = re.split(r"[.;!?]|\bthat\b|\bwhich\b|\bwhere\b|\bwith\b|\bcovering\b", text, maxsplit=1)[0]

    words = [w for w in _TOKEN_RE.findall(text) if w]
    while words and words[0].lower() in {"a", "an", "the", "n"}:
        words.pop(0)
    if not words:
        return "Custom App"

    # Drop trailing scaffolding nouns that describe the artefact, not the product.
    while words and singularize(words[-1]) in {
        "system",
        "app",
        "application",
        "platform",
        "website",
        "web app",
        "tool",
        "portal",
        "software",
        "project",
    }:
        words.pop()

    # Drop a leading article or pronoun left behind once the request frame is removed
    while words and words[0].lower() in (
        "a",
        "an",
        "the",
        "my",
        "our",
        "this",
        "i",
        "am",
        "are",
        "we",
        "me",
        "for",
    ):
        words.pop(0)

    if not words:
        return "Custom App"
    name_words = words[:3]
    return " ".join(name_words).title().strip()


def _fields_for(noun: str) -> list[tuple[str, str]]:
    """Choose a believable field set for an entity lifted from the prompt."""
    key = singularize(noun)
    if key in _FIELD_HINTS:
        return list(_FIELD_HINTS[key])
    # Compound nouns ("stock_movement") and unknown nouns get a neutral record.
    if key.endswith("s"):
        return list(_NAME_FIELDS)
    return list(_DEFAULT_FIELDS)


# Domain-appropriate replacements for nouns that are legal English but illegal
# identifiers. A gym "class" should read as class_session, not class_record.
_RESERVED_ENTITY_RENAMES = {
    "class": "class_session",
    "property": "property_listing",
    "type": "category_type",
    "id": "identifier",
    "input": "input_request",
    "object": "stored_object",
}


def _safe_entity_name(noun: str) -> str:
    """Map a noun onto a name that is legal as a Python class and SQL table.

    ``class`` is a legitimate gym domain noun but an illegal identifier, so it
    becomes ``class_session`` rather than the generic ``class_rec`` the old
    reserved-word guard produced.
    """
    w = noun.lower()
    if w in _RESERVED_ENTITY_RENAMES:
        return _RESERVED_ENTITY_RENAMES[w]
    if w not in _RESERVED_ENTITY_NAMES:
        return w
    return f"{w}_record"


def _keyword_matches(keyword: str, text: str) -> bool:
    """True when `keyword` matches as a whole word or phrase in `text`."""
    kw = (keyword or "").strip().lower()
    if not kw:
        return False
    pattern = r"\b" + re.escape(kw) + r"\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def infer_entities(prompt: str, limit: int = 4) -> list[tuple[str, str, list[tuple[str, str]]]]:
    """Infer ``(singular, plural, fields)`` tuples for a product request.

    Vertical lexicon first; then real nouns from the sentence; a neutral pair only
    as a last resort so the returned list is never empty.
    """
    text = re.sub(r"\s+", " ", (prompt or "").strip().lower())
    if not text:
        return [
            ("item", "items", list(_DEFAULT_FIELDS)),
            ("category", "categories", [("name", "string")]),
        ]

    # 1. Curated vertical.
    for keywords, entities in _LEXICON:
        if any(_keyword_matches(k, text) for k in keywords):
            return [(_safe_entity_name(n), p, list(f)) for n, p, f in entities]

    # 2. Nouns the user actually typed, in the order they appear.
    found: list[tuple[str, str, list[tuple[str, str]]]] = []
    seen: set[str] = set()
    for raw in _TOKEN_RE.findall(text):
        w = raw.lower()
        if len(w) < 3 or w in _STOP_NOUNS or w in _STOP_VERBS:
            continue
        sing = singularize(w)
        if len(sing) < 3 or sing in seen or sing in _STOP_NOUNS:
            continue
        # Only accept a word that plausibly names a record: a known domain noun,
        # or a plural (users commonly list entities in the plural).
        if sing in _FIELD_HINTS or _PLURAL_RE.search(w):
            safe = _safe_entity_name(sing)
            seen.add(sing)
            found.append((safe, pluralize_local(safe), _fields_for(sing)))
        if len(found) >= limit:
            break

    if found:
        return found

    return [
        ("item", "items", list(_DEFAULT_FIELDS)),
        ("category", "categories", [("name", "string")]),
    ]


def pluralize_local(word: str) -> str:
    """Local pluraliser so this module has no import cycle with app_spec."""
    w = word.lower()
    if w.endswith(("s", "x", "z", "ch", "sh")):
        return w + "es"
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return w[:-1] + "ies"
    return w + "s"
